// Prototype shell: Fava of one ledger and terminals with a coding agent, in panels. The page comes from the app
// (tauri://localhost), Fava from the ledger's own server (server/server.py), on another origin.
// The ledger folder comes from KINGSMINT_LEDGER, the first argument, the last one opened, or the user picks it.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use portable_pty::{native_pty_system, Child as PtyChild, CommandBuilder, MasterPty, PtySize};
use std::io::{BufRead, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{Emitter, Manager, State};

const AGENTS: [&str; 3] = ["claude", "codex", "cursor-agent"];
/// The official installers of the agents a subscription brings: Claude (Pro, Max) and ChatGPT. (agent, sh, PowerShell)
const INSTALLERS: [(&str, &str, &str); 2] = [
    ("claude", "curl -fsSL https://claude.ai/install.sh | bash", "irm https://claude.ai/install.ps1 | iex"),
    ("codex", "curl -fsSL https://chatgpt.com/codex/install.sh | sh", "irm https://chatgpt.com/codex/install.ps1 | iex"),
];
const KINGSMINT_GIT: &str = "https://github.com/kingsmint/kingsmint";

struct Pty {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn PtyChild + Send + Sync>,
}

/// One open ledger and its server (the app's page and Fava). A new ledger replaces it; the old server is killed.
struct Ledger {
    dir: PathBuf,
    port: u16,
    server: Mutex<Option<Child>>,
    /// set under the `server` lock when another ledger replaces this one: a start still in `uv sync` starts no server
    closed: AtomicBool,
    error: Mutex<Option<String>>,
    /// the last lines of uv and the server on stderr: the start screen shows what is downloaded
    log: Mutex<Vec<String>>,
    /// the server's stdin, for requests (server/rpc.py); closing it ends the server
    requests: Mutex<Option<ChildStdin>>,
    /// the requests waiting for their answer, by id
    pending: Mutex<HashMap<u64, mpsc::Sender<Result<serde_json::Value, String>>>>,
    /// tells the page when the ledger's files change; dropped with the ledger
    watcher: Mutex<Option<notify::RecommendedWatcher>>,
}

/// Gives each answer on the server's stdout to the request waiting for it.
fn read_answers(l: &Ledger, from: impl Read) {
    for line in std::io::BufReader::new(from).lines().map_while(Result::ok) {
        let Ok(msg) = serde_json::from_str::<serde_json::Value>(&line) else {
            eprintln!("server: not an answer: {line}");
            continue;
        };
        let waiting = msg["id"].as_u64().and_then(|id| l.pending.lock().unwrap().remove(&id));
        if let Some(tx) = waiting {
            let answer = match msg.get("error") {
                Some(e) => Err(e.as_str().unwrap_or("error").to_string()),
                None => Ok(msg["result"].clone()),
            };
            tx.send(answer).ok();
        }
    }
    l.pending.lock().unwrap().clear(); // the server ended: the waiting requests get an error
}

/// Copies the lines of a child's stderr into the ledger's log and the app's output, until the child closes it.
fn log_lines(l: &Ledger, from: impl Read) {
    for line in std::io::BufReader::new(from).lines().map_while(Result::ok) {
        eprintln!("{line}");
        let mut log = l.log.lock().unwrap();
        if log.len() == 100 {
            log.remove(0);
        }
        log.push(line);
    }
}

struct App {
    ledger: Mutex<Option<Arc<Ledger>>>,
    /// one terminal per tab, by session number; a new ledger ends them all
    ptys: Mutex<HashMap<u64, Pty>>,
    /// the ledgers opened before, newest first, one path per line
    remembered: PathBuf,
    /// the tabs of each ledger, by folder: { "<dir>": { "tabs": [...], "active": n } }
    tabs_file: PathBuf,
    /// the app's own settings (default agent, font size)
    settings_file: PathBuf,
    /// server.py and the page it serves (dist/)
    resources: PathBuf,
    /// for events to the page from the app's threads
    handle: tauri::AppHandle,
}

fn recent(app: &App) -> Vec<String> {
    std::fs::read_to_string(&app.remembered).unwrap_or_default().lines().map(str::to_string).collect()
}

fn shell() -> String {
    if cfg!(windows) { "powershell.exe".into() } else { std::env::var("SHELL").unwrap_or("/bin/zsh".into()) }
}

/// A binary shipped next to the app's own (Tauri's externalBin: uv, jj), else the one on PATH.
fn sidecar(name: &str) -> PathBuf {
    let exe = std::env::current_exe().unwrap().with_file_name(if cfg!(windows) { format!("{name}.exe") } else { name.into() });
    if exe.is_file() { exe } else { name.into() }
}

/// A child process without a console window: on Windows, a windowed app opens one for each console program it starts
/// (uv, Python, kingsmint); their own children share the hidden console.
fn quiet(name: impl AsRef<std::ffi::OsStr>) -> Command {
    #[allow(unused_mut)]
    let mut cmd = Command::new(name);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd
}

fn uv() -> PathBuf {
    sidecar("uv")
}

/// An app started from Finder gets launchd's PATH, without Homebrew or the agents; take the login shell's PATH.
fn login_path() {
    if cfg!(windows) {
        return;
    }
    let out = Command::new(shell()).args(["-l", "-i", "-c", "printf '\\n@@%s@@' \"$PATH\""]).output();
    if let Ok(out) = out {
        let s = String::from_utf8_lossy(&out.stdout);
        if let Some(p) = s.rsplit("@@").nth(1) {
            std::env::set_var("PATH", p);
        }
    }
}

/// Adds the folders the agents' installers use to PATH, when missing: an agent installed from the app is found
/// before the user's shell profile has them, and the installers do not always add them.
fn agent_path() {
    let home = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).map(PathBuf::from);
    let mut dirs: Vec<PathBuf> = home.into_iter().map(|h| h.join(".local").join("bin")).collect();
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        dirs.push(PathBuf::from(local).join(r"Programs\OpenAI\Codex\bin"));
    }
    let mut path: Vec<PathBuf> = std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()).collect();
    for d in dirs {
        if !path.contains(&d) {
            path.push(d);
        }
    }
    std::env::set_var("PATH", std::env::join_paths(path).unwrap());
}

/// PATH for the terminal: the ledger's .venv first (`kingsmint`, `fava`, `bean-query` of the ledger's version), then the app's uv.
fn ledger_path(ledger: &Path) -> String {
    let bin = ledger.join(".venv").join(if cfg!(windows) { "Scripts" } else { "bin" });
    let mut parts = vec![bin];
    if let Some(d) = uv().parent().filter(|d| !d.as_os_str().is_empty()) {
        parts.push(d.to_path_buf());
    }
    parts.extend(std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()));
    std::env::join_paths(parts).unwrap().to_string_lossy().into_owned()
}

fn on_path(name: &str) -> bool {
    // npm installs the agents on Windows as .cmd scripts
    let exes: &[String] = if cfg!(windows) { &[format!("{name}.exe"), format!("{name}.cmd")] } else { &[name.to_string()] };
    std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()).any(|d| exes.iter().any(|e| d.join(e).is_file()))
}

/// `canonicalize`, without the `\\?\` prefix it adds on Windows: PowerShell, uv and the user's eyes want `C:\...`.
fn canonical(p: &Path) -> std::io::Result<PathBuf> {
    let c = p.canonicalize()?;
    Ok(match c.to_str().and_then(|s| s.strip_prefix(r"\\?\")) {
        Some(s) if cfg!(windows) && s.as_bytes().get(1) == Some(&b':') => PathBuf::from(s),
        _ => c,
    })
}

fn venv_bin(dir: &Path, name: &str) -> PathBuf {
    if cfg!(windows) { dir.join(".venv/Scripts").join(format!("{name}.exe")) } else { dir.join(".venv/bin").join(name) }
}

#[derive(Clone, Copy, PartialEq)]
enum Start {
    Existing,
    New,
    /// a new ledger filled with made-up statements (`kingsmint sample`)
    Sample,
}

/// `uv sync` installs the kingsmint version the ledger pins; a new ledger then records that version. The server runs
/// with the ledger's Python and exits when its stdin closes, so it leaves no orphan, also when the app is killed.
fn start_server(l: &Arc<Ledger>, start: Start, resources: &Path) {
    let fail = |e: String| *l.error.lock().unwrap() = Some(e);
    let run = |cmd: &mut Command, what: &str| {
        let mut child = cmd.current_dir(&l.dir).stderr(Stdio::piped()).spawn().map_err(|e| format!("cannot run {what}: {e}"))?;
        log_lines(l, child.stderr.take().unwrap());
        match child.wait() {
            Ok(st) if st.success() => Ok(()),
            Ok(st) => Err(format!("{what} failed ({st}) in {}", l.dir.display())),
            Err(e) => Err(format!("cannot run {what}: {e}")),
        }
    };
    eprintln!("kingsmint: {} sync in {}", uv().display(), l.dir.display());
    if let Err(e) = run(quiet(uv()).arg("sync"), "uv sync") {
        return fail(e);
    }
    if start != Start::Existing {
        if let Err(e) = run(quiet(venv_bin(&l.dir, "kingsmint")).args(["upgrade", "--done"]), "kingsmint upgrade --done") {
            return fail(e);
        }
        if start == Start::Sample {
            if let Err(e) = run(quiet(venv_bin(&l.dir, "kingsmint")).arg("sample"), "kingsmint sample") {
                return fail(e);
            }
        }
    }
    agent_files(&l.dir);
    let mut server = l.server.lock().unwrap();
    if l.closed.load(Ordering::SeqCst) {
        return; // another ledger was opened meanwhile
    }
    match quiet(uv())
        // the ledger's own packages only (Fava brings werkzeug), so a ledger of any kingsmint version runs the server
        .args(["run", "--no-sync", "python"])
        .arg(resources.join("server").join("server.py"))
        .args(["main.beancount", &l.port.to_string()])
        .arg(resources.join("dist"))
        .env("KINGSMINT_JJ", sidecar("jj"))
        // a new ledger: the server turns on its versions, with this first one
        .env("KINGSMINT_FIRST_VERSION", match start { Start::Existing => "", Start::Sample => "Sample ledger", Start::New => "New ledger" })
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .current_dir(&l.dir)
        .spawn()
    {
        Ok(mut c) => {
            let (stderr, log) = (c.stderr.take().unwrap(), l.clone());
            std::thread::spawn(move || log_lines(&log, stderr));
            let (stdout, answers) = (c.stdout.take().unwrap(), l.clone());
            std::thread::spawn(move || read_answers(&answers, stdout));
            *l.requests.lock().unwrap() = c.stdin.take();
            *server = Some(c)
        }
        Err(e) => fail(format!("cannot start the server: {e}")),
    }
}

/// What an agent in the ledger needs: kingsmint's skills, copied from the version the ledger runs (an older
/// kingsmint has no `kingsmint skills`; its agent goes without), and the Claude Code plugin of kingsmint off in this
/// ledger, so Claude Code does not see a second set of skills from another version.
fn agent_files(dir: &Path) {
    let _ = quiet(venv_bin(dir, "kingsmint")).arg("skills").current_dir(dir).status();
    if !dir.join(".claude/skills/kingsmint-import").exists() {
        return; // no copies: the plugin stays the only source
    }
    let path = dir.join(".claude/settings.local.json");
    let mut settings: serde_json::Value = std::fs::read(&path).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or_else(|| serde_json::json!({}));
    if settings.pointer("/enabledPlugins/kingsmint@kingsmint") != Some(&serde_json::Value::Bool(false)) && settings.is_object() {
        if !settings["enabledPlugins"].is_object() {
            settings["enabledPlugins"] = serde_json::json!({});
        }
        settings["enabledPlugins"]["kingsmint@kingsmint"] = false.into();
        std::fs::write(&path, serde_json::to_vec_pretty(&settings).unwrap()).ok();
    }
}

/// Kills `uv run`; its Python exits when its stdin closes, which happens here.
fn kill_server(l: &Ledger) {
    let mut server = l.server.lock().unwrap();
    l.closed.store(true, Ordering::SeqCst);
    l.requests.lock().unwrap().take();
    if let Some(mut f) = server.take() {
        f.kill().ok();
        f.wait().ok();
    }
}

fn open(app: &App, dir: &Path, start: Start) -> Result<String, String> {
    let dir = canonical(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    if !dir.join("main.beancount").is_file() {
        return Err(format!("No main.beancount in {}; pick a ledger folder, or create a new ledger", dir.display()));
    }
    if let Some(old) = app.ledger.lock().unwrap().take() {
        kill_server(&old);
    }
    kill_ptys(app);
    let port = TcpListener::bind(("127.0.0.1", 0)).unwrap().local_addr().unwrap().port();
    let l = Arc::new(Ledger { dir: dir.clone(), port, server: Mutex::new(None), closed: AtomicBool::new(false), error: Mutex::new(None), log: Mutex::new(vec![]),
                         requests: Mutex::new(None), pending: Mutex::new(HashMap::new()), watcher: Mutex::new(None) });
    watch(&l, app.handle.clone());
    *app.ledger.lock().unwrap() = Some(l.clone());
    let resources = app.resources.clone();
    std::thread::spawn(move || start_server(&l, start, &resources));
    if let Some(p) = app.remembered.parent() {
        std::fs::create_dir_all(p).ok();
    }
    let path = dir.display().to_string();
    let mut list: Vec<String> = recent(app).into_iter().filter(|d| *d != path).take(7).collect();
    list.insert(0, path);
    std::fs::write(&app.remembered, list.join("\n")).ok();
    Ok(dir.display().to_string())
}

fn copy_dir(from: &Path, to: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(to)?;
    for e in std::fs::read_dir(from)? {
        let e = e?;
        let dest = to.join(e.file_name());
        if e.file_type()?.is_dir() {
            copy_dir(&e.path(), &dest)?;
        } else if !dest.exists() {
            std::fs::copy(e.path(), dest)?;
        }
    }
    Ok(())
}

/// Errors of the page, printed to the app's output (the page's console is not visible without devtools).
#[tauri::command]
fn log(message: String) {
    eprintln!("page: {message}");
}

#[tauri::command]
fn agents() -> Vec<&'static str> {
    AGENTS.into_iter().filter(|a| on_path(a)).collect()
}

static REQUESTS: AtomicU64 = AtomicU64::new(1);

/// A request to the open ledger's server (server/rpc.py): `method` with `params`, as JSON; its result or its error.
#[tauri::command]
async fn rpc(method: String, params: serde_json::Value, app: State<'_, App>) -> Result<serde_json::Value, String> {
    let l = app.ledger.lock().unwrap().clone().ok_or("No ledger is open")?;
    tauri::async_runtime::spawn_blocking(move || request(&l, &method, params)).await.map_err(|e| e.to_string())?
}

/// Sends a request to the server and waits for its answer.
fn request(l: &Ledger, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
    let id = REQUESTS.fetch_add(1, Ordering::Relaxed);
    let (tx, rx) = mpsc::channel();
    l.pending.lock().unwrap().insert(id, tx);
    let line = serde_json::json!({ "id": id, "method": method, "params": params }).to_string() + "\n";
    let sent = match l.requests.lock().unwrap().as_mut() {
        Some(stdin) => stdin.write_all(line.as_bytes()).and_then(|_| stdin.flush()).map_err(|e| e.to_string()),
        None => Err("The ledger's server is not running".into()),
    };
    if let Err(e) = sent {
        l.pending.lock().unwrap().remove(&id);
        return Err(e);
    }
    // a check of a large ledger takes a while; an ended server drops the sender, which ends the wait at once
    rx.recv_timeout(Duration::from_secs(300)).map_err(|_| format!("{method}: the ledger's server did not answer"))?
}

/// The folders whose changes do not change the ledger's state: tools, versions, imported statements' copies.
const UNWATCHED: [&str; 5] = [".venv", ".git", ".jj", "documents", "node_modules"];

/// Watches the ledger's files. After a change, once nothing changed for 300 ms (an import writes many files), it asks
/// the server for the ledger's state (the server checks the ledger and reloads Fava) and sends it to the page as
/// `ledger-changed`, with the ledger's folder, so the page ignores the state of a ledger it no longer shows. The
/// thread holds the ledger weakly and ends when the ledger, with its watcher, is dropped.
fn watch(l: &Arc<Ledger>, handle: tauri::AppHandle) {
    use notify::Watcher;
    let (tx, rx) = mpsc::channel();
    let dir = l.dir.clone();
    let relevant = move |e: &notify::Event| {
        e.paths.iter().any(|p| p.strip_prefix(&dir).ok().and_then(|r| r.components().next())
            .is_some_and(|c| !UNWATCHED.contains(&c.as_os_str().to_string_lossy().as_ref())))
    };
    let watcher = notify::recommended_watcher(move |e: notify::Result<notify::Event>| {
        if e.is_ok_and(|e| relevant(&e)) {
            tx.send(()).ok();
        }
    });
    let mut watcher = match watcher {
        Ok(w) => w,
        Err(e) => return eprintln!("kingsmint: cannot watch the ledger: {e}"),
    };
    if let Err(e) = watcher.watch(&l.dir, notify::RecursiveMode::Recursive) {
        return eprintln!("kingsmint: cannot watch {}: {e}", l.dir.display());
    }
    *l.watcher.lock().unwrap() = Some(watcher);
    let weak = Arc::downgrade(l);
    std::thread::spawn(move || {
        while rx.recv().is_ok() {
            while rx.recv_timeout(Duration::from_millis(300)).is_ok() {}
            let Some(l) = weak.upgrade() else { break };
            match request(&l, "state", serde_json::json!({})) {
                Ok(state) => drop(handle.emit("ledger-changed", serde_json::json!({ "dir": l.dir.display().to_string(), "state": state }))),
                Err(e) => eprintln!("kingsmint: state: {e}"),
            }
        }
    });
}

/// The last lines of uv and the server, while the start screen waits for the server.
#[tauri::command]
fn setup_log(app: State<App>) -> Vec<String> {
    app.ledger.lock().unwrap().as_ref().map(|l| l.log.lock().unwrap().clone()).unwrap_or_default()
}

/// The open ledger's folder, or none yet.
#[tauri::command]
fn ledger_dir(app: State<App>) -> Option<String> {
    app.ledger.lock().unwrap().as_ref().map(|l| l.dir.display().to_string())
}

/// Ledgers opened before that still exist, newest first.
#[tauri::command]
fn recent_ledgers(app: State<App>) -> Vec<String> {
    recent(&app).into_iter().filter(|d| Path::new(d).join("main.beancount").is_file()).collect()
}

#[tauri::command]
fn open_ledger(dir: String, app: State<App>) -> Result<String, String> {
    open(&app, Path::new(&dir), Start::Existing)
}

/// Creates a ledger from the bundled template in an empty folder.
// shortcut: repeats kingsmint_new_ledger of desktop/server/main.py; EUR until the agent proposes the currency at
// the first import; move it to a `kingsmint new` command when the app stays
#[tauri::command]
fn new_ledger(dir: String, title: String, language: String, app: State<App>, handle: tauri::AppHandle) -> Result<String, String> {
    let d = PathBuf::from(&dir);
    let busy = std::fs::read_dir(&d)
        .map_err(|e| format!("{dir}: {e}"))?
        .flatten()
        .any(|e| !matches!(e.file_name().to_str(), Some("inbox" | "banks" | ".DS_Store")));
    if busy {
        return Err(format!("{dir} is not empty; pick an empty folder (inbox/ with statements and banks/ with parsers are fine)"));
    }
    make_ledger(&d, &title, &language, &handle)?;
    open(&app, &d, Start::New)
}

/// The sample ledger, in the app's data folder: made once per language, then opened again as it is. One whose
/// statements were never imported (its first start failed, for example in `uv sync`) is made again.
#[tauri::command]
fn sample_ledger(language: String, app: State<App>, handle: tauri::AppHandle) -> Result<String, String> {
    let d = handle.path().app_data_dir().map_err(|e| e.to_string())?.join(format!("sample-{language}"));
    if has_statement(&d.join("documents")) {
        return open(&app, &d, Start::Existing);
    }
    if !d.join("main.beancount").is_file() {
        std::fs::create_dir_all(&d).map_err(|e| format!("{}: {e}", d.display()))?;
        make_ledger(&d, if language == "sk" { "Ukážka" } else { "Sample" }, &language, &handle)?;
    }
    open(&app, &d, Start::Sample)
}

/// A statement was imported: documents/ holds a file (not .keep, which the template ships), as server/inbox.py says.
/// Symbolic links are not followed: a link to a folder above would never end.
fn has_statement(dir: &Path) -> bool {
    std::fs::read_dir(dir).into_iter().flatten().flatten().any(|e| {
        let hidden = e.file_name().to_string_lossy().starts_with('.');
        let Ok(kind) = e.file_type() else { return false };
        !hidden && (kind.is_file() || kind.is_dir() && has_statement(&e.path()))
    })
}

/// Copies the template into `d` and fills in the owner, language and kingsmint source.
fn make_ledger(d: &Path, title: &str, language: &str, handle: &tauri::AppHandle) -> Result<(), String> {
    let (agent_language, code, locale) = match language {
        "sk" => ("Slovak", "sk", "sk_SK"),
        _ => ("English", "en", "en_US"),
    };
    let title = title.trim();
    if title.is_empty() {
        return Err("Enter the owner's name".into());
    }
    // the title goes into a quoted beancount string; the same rule as the ledger's settings (ledger_settings.save)
    if title.contains(['"', '\\', '\n', '\r']) {
        return Err(format!("The name cannot contain \", \\ or a line break: {title}"));
    }
    let template = handle.path().resource_dir().map_err(|e| e.to_string())?.join("template");
    copy_dir(&template, d).map_err(|e| format!("cannot copy the template: {e}"))?;
    let edit = |name: &str, pairs: &[(&str, &str)]| -> Result<(), String> {
        let f = d.join(name);
        let mut text = std::fs::read_to_string(&f).map_err(|e| format!("{name}: {e}"))?;
        for (k, v) in pairs {
            text = text.replace(k, v);
        }
        std::fs::write(&f, text).map_err(|e| format!("{name}: {e}"))
    };
    let title_q = format!("\"{title}\"");
    edit("main.beancount", &[("\"TITLE\"", &title_q), ("\"CURRENCY\"", "\"EUR\""), ("'CURRENCY'", "'EUR'"),
                             ("\"LOCALE\"", &format!("\"{locale}\"")), ("\"LANGUAGE_CODE\"", &format!("\"{code}\""))])?;
    edit("CLAUDE.md", &[("in LANGUAGE", &format!("in {agent_language}"))])?;
    // the app and the ledger use the same kingsmint release; a development build (cargo run) uses the checkout it
    // was built from, as the setup skill does for a plugin from a checkout, so the ledger has the unreleased changes
    let source = if cfg!(debug_assertions) {
        let checkout = canonical(&Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")).map_err(|e| e.to_string())?;
        // forward slashes: a backslash is an escape in a TOML string, and uv takes C:/... too
        format!("{{ path = \"{}\", editable = true }}", checkout.display().to_string().replace('\\', "/"))
    } else {
        // the release's wheel, not a git source: uv then needs no git, which a Mac without the Command Line Tools and
        // Windows lack; and its bytes stay as uv.lock's hash says, which GitHub does not promise for its archives.
        // KINGSMINT_REV: a test build of an unreleased commit (workflow app.yml), which has no wheel: the commit's
        // archive, which `kingsmint upgrade --done` leaves as it is
        let v = env!("CARGO_PKG_VERSION");
        match option_env!("KINGSMINT_REV") {
            Some(rev) => format!("{{ url = \"{KINGSMINT_GIT}/archive/{rev}.tar.gz\" }}"),
            None => format!("{{ url = \"{KINGSMINT_GIT}/releases/download/v{v}/kingsmint-{v}-py3-none-any.whl\" }}"),
        }
    };
    edit("pyproject.toml", &[("{ git = \"KINGSMINT_SOURCE\" }", &source)])
}

#[tauri::command]
fn app_settings(app: State<App>) -> serde_json::Value {
    std::fs::read(&app.settings_file).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or_default()
}

#[tauri::command]
fn save_app_settings(settings: serde_json::Value, app: State<App>) -> Result<(), String> {
    std::fs::write(&app.settings_file, serde_json::to_vec_pretty(&settings).unwrap()).map_err(|e| e.to_string())
}

/// Copies statements (PDF, CSV) into inbox/; returns the names it skipped. An existing file of the same name stays.
#[tauri::command]
fn inbox_add(paths: Vec<String>, app: State<App>) -> Result<Vec<String>, String> {
    let dir = app.ledger.lock().unwrap().as_ref().map(|l| l.dir.join("inbox")).ok_or("No ledger is open")?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let mut skipped = vec![];
    for p in paths.iter().map(PathBuf::from) {
        let name = p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let ext = p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
        if !p.is_file() || !matches!(ext.as_str(), "pdf" | "csv") {
            skipped.push(format!("{name} (not a PDF or CSV statement)"));
        } else if dir.join(&name).exists() {
            skipped.push(format!("{name} (already in inbox/)"));
        } else {
            std::fs::copy(&p, dir.join(&name)).map_err(|e| format!("{name}: {e}"))?;
        }
    }
    Ok(skipped)
}

/// Moves a file from inbox/ to the Trash, so the user can get it back.
// shortcut: only files directly in inbox/ (scan also lists subfolders); search subfolders when users keep them there
#[tauri::command]
fn inbox_remove(name: String, app: State<App>) -> Result<(), String> {
    let dir = app.ledger.lock().unwrap().as_ref().map(|l| l.dir.join("inbox")).ok_or("No ledger is open")?;
    // a plain file name only, so the page cannot remove a file outside inbox/
    if Path::new(&name).file_name() != Some(name.as_ref()) {
        return Err(format!("{name}: not a file name"));
    }
    trash::delete(dir.join(&name)).map_err(|e| format!("{name}: {e}"))
}

/// Opens inbox/ in Finder (Explorer, the file manager).
#[tauri::command]
fn inbox_reveal(app: State<App>) -> Result<(), String> {
    let dir = app.ledger.lock().unwrap().as_ref().map(|l| l.dir.join("inbox")).ok_or("No ledger is open")?;
    std::fs::create_dir_all(&dir).ok();
    system_open(dir.as_os_str())
}

/// Opens a link from a terminal in the system's browser. Only web links: `open` would also start apps and files.
#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if !url.starts_with("https://") && !url.starts_with("http://") {
        return Err(format!("not a web link: {url}"));
    }
    system_open(url.as_ref())
}

fn system_open(what: &std::ffi::OsStr) -> Result<(), String> {
    let opener = if cfg!(target_os = "macos") { "open" } else if cfg!(windows) { "explorer" } else { "xdg-open" };
    Command::new(opener).arg(what).spawn().map(|_| ()).map_err(|e| e.to_string())
}

/// Waits until the server answers (the first start installs Python and kingsmint, which can take minutes; the server
/// listens once Fava has loaded the ledger) and returns its URL.
#[tauri::command]
async fn server_url(app: State<'_, App>) -> Result<String, String> {
    let l = app.ledger.lock().unwrap().clone().ok_or("No ledger is open")?;
    let start = Instant::now();
    while TcpStream::connect(("127.0.0.1", l.port)).is_err() {
        if let Some(e) = l.error.lock().unwrap().clone() {
            return Err(e);
        }
        if let Some(st) = l.server.lock().unwrap().as_mut().and_then(|c| c.try_wait().ok().flatten()) {
            return Err(format!("The server exited ({st}); run `uv run fava main.beancount` in the ledger to see why"));
        }
        if start.elapsed() > Duration::from_secs(600) {
            return Err("The server did not start in 10 minutes".into());
        }
        tauri::async_runtime::spawn_blocking(|| std::thread::sleep(Duration::from_millis(300))).await.ok();
    }
    Ok(format!("http://127.0.0.1:{}/", l.port))
}

fn kill_ptys(app: &App) {
    let ptys: Vec<Pty> = app.ptys.lock().unwrap().drain().map(|(_, p)| p).collect();
    for mut p in ptys {
        p.child.kill().ok();
    }
}

static SESSIONS: AtomicU64 = AtomicU64::new(1);

#[derive(Clone, serde::Serialize)]
struct PtyData<'a> {
    session: u64,
    data: &'a [u8],
}

/// The saved tabs of a ledger (names, agents, Claude Code session ids), or null.
#[tauri::command]
fn load_tabs(dir: String, app: State<App>) -> serde_json::Value {
    let all: serde_json::Value = std::fs::read(&app.tabs_file).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or_default();
    all.get(&dir).cloned().unwrap_or_default()
}

#[tauri::command]
fn save_tabs(dir: String, tabs: serde_json::Value, app: State<App>) -> Result<(), String> {
    let mut all: serde_json::Value = std::fs::read(&app.tabs_file).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or_default();
    if !all.is_object() {
        all = serde_json::json!({});
    }
    all[dir] = tabs;
    std::fs::write(&app.tabs_file, serde_json::to_vec_pretty(&all).unwrap()).map_err(|e| e.to_string())
}

#[tauri::command]
fn pty_kill(session: u64, app: State<App>) {
    let pty = app.ptys.lock().unwrap().remove(&session);
    if let Some(mut p) = pty {
        p.child.kill().ok();
    }
}

/// `'text'` for sh or PowerShell, with single quotes inside escaped.
fn quote(text: &str) -> String {
    if cfg!(windows) { format!("'{}'", text.replace('\'', "''")) } else { format!("'{}'", text.replace('\'', "'\\''")) }
}

/// The command line of an agent. Claude Code gets the tab's session id: a new tab starts that session, a restored
/// tab continues it (and starts it when it was never used, so `--resume` finds nothing).
fn agent_command(agent: &str, claude: Option<&str>, name: &str, resume: bool) -> Result<String, String> {
    let Some(id) = claude.filter(|_| agent == "claude") else { return Ok(agent.to_string()) };
    if id.len() != 36 || !id.chars().all(|c| c.is_ascii_hexdigit() || c == '-') {
        return Err(format!("bad session id {id}"));
    }
    let start = format!("claude --session-id {id} -n {}", quote(name));
    let resume_cmd = format!("claude --resume {id} -n {}", quote(name));
    // Windows PowerShell 5.1 has no `||`
    Ok(match (resume, cfg!(windows)) {
        (false, _) => start,
        (true, false) => format!("{resume_cmd} || {start}"),
        (true, true) => format!("{resume_cmd}; if (-not $?) {{ {start} }}"),
    })
}

/// Starts `agent` (or a plain shell when empty) in the ledger folder and returns its session number. Output goes to
/// the `pty-data` event, the end to `pty-exit`, both with the session, so a tab ignores what an older program wrote.
#[tauri::command]
#[allow(clippy::too_many_arguments)]
fn pty_start(agent: String, cols: u16, rows: u16, claude: Option<String>, name: String, resume: bool, install: bool,
             app: State<App>, handle: tauri::AppHandle) -> Result<u64, String> {
    if !agent.is_empty() && !AGENTS.contains(&agent.as_str()) {
        return Err(format!("unknown agent {agent}"));
    }
    let (dir, port) = app.ledger.lock().unwrap().as_ref().map(|l| (l.dir.clone(), l.port)).ok_or("No ledger is open")?;
    let pair = native_pty_system()
        .openpty(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
        .map_err(|e| e.to_string())?;
    let mut cmd = CommandBuilder::new(shell());
    if !agent.is_empty() {
        // when the agent exits, the tab ends too (no shell after it): the app's tasks type into agent tabs only
        let mut line = agent_command(&agent, claude.as_deref(), &name, resume)?;
        if install {
            // the agent's installer first, in the tab, so the user sees it; then the agent, which asks to sign in
            let (_, sh, ps) = INSTALLERS.iter().find(|i| i.0 == agent).ok_or(format!("no installer for {agent}"))?;
            line = if cfg!(windows) { format!("{ps}; if ($?) {{ {line} }}") } else { format!("{sh} && {line}") };
        }
        if cfg!(windows) {
            cmd.args(["-NoLogo", "-Command", &line]);
        } else {
            cmd.args(["-l", "-i", "-c", &line]);
        }
    }
    cmd.cwd(&dir);
    cmd.env("PATH", ledger_path(&dir));
    cmd.env("TERM", "xterm-256color");
    cmd.env("COLORTERM", "truecolor");
    // the agent's links to Fava (skill `explain`); the app opens them in its Fava panel
    cmd.env("KINGSMINT_FAVA_URL", format!("http://127.0.0.1:{port}/ledger/"));
    let child = pair.slave.spawn_command(cmd).map_err(|e| e.to_string())?;
    drop(pair.slave);
    let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
    let writer = pair.master.take_writer().map_err(|e| e.to_string())?;
    let session = SESSIONS.fetch_add(1, Ordering::Relaxed);
    app.ptys.lock().unwrap().insert(session, Pty { master: pair.master, writer, child });
    std::thread::spawn(move || {
        let mut buf = [0u8; 16384];
        while let Ok(n) = reader.read(&mut buf) {
            if n == 0 || handle.emit("pty-data", PtyData { session, data: &buf[..n] }).is_err() {
                break;
            }
        }
        handle.state::<App>().ptys.lock().unwrap().remove(&session);
        handle.emit("pty-exit", session).ok();
    });
    Ok(session)
}

#[tauri::command]
fn pty_write(session: u64, data: String, app: State<App>) -> Result<(), String> {
    match app.ptys.lock().unwrap().get_mut(&session) {
        Some(p) => p.writer.write_all(data.as_bytes()).map_err(|e| e.to_string()),
        None => Ok(()),
    }
}

#[tauri::command]
fn pty_resize(session: u64, cols: u16, rows: u16, app: State<App>) -> Result<(), String> {
    match app.ptys.lock().unwrap().get(&session) {
        Some(p) => p.master.resize(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 }).map_err(|e| e.to_string()),
        None => Ok(()),
    }
}

fn main() {
    login_path();
    agent_path();
    // Python on Windows reads and writes pipes in the ANSI code page (cp1250), which garbles the server's and
    // kingsmint's UTF-8 text; the server, kingsmint and the terminals inherit this
    #[cfg(windows)]
    std::env::set_var("PYTHONUTF8", "1");
    // Beancount has no wheel for Windows on ARM, and building it needs a C compiler; Windows 11 on ARM runs x64 Python,
    // whose wheels exist. The ledger's environment, the server and `uv run` in the terminals all take it.
    #[cfg(all(windows, target_arch = "aarch64"))]
    if std::env::var_os("UV_PYTHON").is_none() {
        std::env::set_var("UV_PYTHON", "cpython-3.13-windows-x86_64-none");
    }
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let config = app.path().app_config_dir()?;
            std::fs::create_dir_all(&config).ok();
            let remembered = config.join("ledger");
            let tabs_file = config.join("tabs.json");
            let settings_file = config.join("settings.json");
            // a development build (cargo run) uses the files of the checkout, which change without a new build
            let resources = if cfg!(debug_assertions) {
                canonical(&Path::new(env!("CARGO_MANIFEST_DIR")).join(".."))?
            } else {
                app.path().resource_dir()?
            };
            let state = App { ledger: Mutex::new(None), ptys: Mutex::new(HashMap::new()), remembered, tabs_file, settings_file, resources,
                              handle: app.handle().clone() };
            let start = std::env::var_os("KINGSMINT_LEDGER")
                .or_else(|| std::env::args_os().nth(1))
                .map(PathBuf::from)
                .or_else(|| recent(&state).first().map(PathBuf::from));
            if let Some(dir) = start {
                open(&state, &dir, Start::Existing).ok(); // a moved or deleted ledger: the user picks again
            }
            app.manage(state);
            // the app's own page shows the start screen and waits for the server; then it goes to the server's page
            let window = tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::default())
                .title("Kingsmint")
                .inner_size(1440.0, 900.0)
                .min_inner_size(900.0, 500.0);
            #[cfg(target_os = "macos")]
            let window = window
                .title_bar_style(tauri::TitleBarStyle::Overlay)
                .hidden_title(true)
                .traffic_light_position(tauri::LogicalPosition::new(14.0, 30.0));
            let window = window.build()?;
            // the trackpad's two-finger swipe goes back and forward, as in Safari; Tauri has no option for it
            #[cfg(target_os = "macos")]
            window.with_webview(|w| unsafe {
                let view = &*(w.inner() as *const objc2::runtime::AnyObject);
                let _: () = objc2::msg_send![view, setAllowsBackForwardNavigationGestures: true];
            })?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![log, setup_log, rpc, agents, ledger_dir, recent_ledgers, open_ledger, new_ledger, sample_ledger, server_url, app_settings, save_app_settings, inbox_add, inbox_remove, inbox_reveal, open_url, load_tabs, save_tabs, pty_start, pty_write, pty_resize, pty_kill])
        .build(tauri::generate_context!())
        .expect("cannot build the app")
        .run(|handle, event| {
            if let tauri::RunEvent::Exit = event {
                let app = handle.state::<App>();
                let ledger = app.ledger.lock().unwrap().take();
                if let Some(l) = ledger {
                    kill_server(&l);
                }
                kill_ptys(&app);
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(not(windows))]
    fn claude_command() {
        let id = "0b9c8f8e-1d2a-4c3b-9a8f-7e6d5c4b3a21";
        assert_eq!(quote("it's"), r"'it'\''s'");
        assert_eq!(agent_command("codex", Some(id), "x", true).unwrap(), "codex");
        assert_eq!(agent_command("claude", None, "x", true).unwrap(), "claude");
        assert_eq!(agent_command("claude", Some(id), "dane", false).unwrap(), format!("claude --session-id {id} -n 'dane'"));
        assert_eq!(agent_command("claude", Some(id), "dane", true).unwrap(),
                   format!("claude --resume {id} -n 'dane' || claude --session-id {id} -n 'dane'"));
        assert!(agent_command("claude", Some("x; rm -rf ~"), "x", false).is_err());
    }

    #[test]
    #[cfg(windows)]
    fn claude_command_powershell() {
        let id = "0b9c8f8e-1d2a-4c3b-9a8f-7e6d5c4b3a21";
        assert_eq!(quote("it's"), "'it''s'");
        assert_eq!(agent_command("claude", Some(id), "dane", true).unwrap(),
                   format!("claude --resume {id} -n 'dane'; if (-not $?) {{ claude --session-id {id} -n 'dane' }}"));
    }
}
