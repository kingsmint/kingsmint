// The app's commands are allowed only where a capability lists them (capabilities/default.json): the app's own page,
// not Fava's frames on the ledger's server. This makes the allow-<command> permissions for them.
const COMMANDS: &[&str] = &["log", "setup_log", "rpc", "agents", "agent_version", "ledger_dir", "recent_ledgers", "open_ledger", "new_ledger",
    "sample_ledger", "server_url", "app_settings", "save_app_settings",
    "inbox_add", "inbox_remove", "inbox_reveal", "open_url", "feedback", "check_updates",
    "claude_extension", "claude_extension_install", "load_tabs", "save_tabs", "conversations", "pty_start", "pty_write", "pty_resize", "pty_kill"];

fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(tauri_build::AppManifest::new().commands(COMMANDS)))
        .expect("tauri build");
}
