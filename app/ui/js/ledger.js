// The open ledger: the start screen, the ledger menu, the wait for its server, and its state.

import { app } from "./app.svelte.js";
import { t } from "./i18n.js";
import { refreshInbox } from "./inbox.js";
import { loadLayout, save, visible } from "./panels.js";
import { pane } from "./rail.js";
import { setLang } from "./settings.js";
import { assign } from "./state.js";
import { invoke, listen, rpc } from "./util.js";

export const basename = (dir) => dir.split(/[\\/]/).filter(Boolean).pop();
export const tilde = (dir) => (app.home && dir.startsWith(app.home) ? `~${dir.slice(app.home.length)}` : dir);

// Initials and a color from the path, like JetBrains project icons.
export function badgeOf(dir) {
  const words = basename(dir)
    .split(/[\s._-]+/)
    .filter(Boolean);
  let h = 0;
  for (const c of dir) h = (h * 31 + c.charCodeAt(0)) % 360;
  return {
    text: (words.length > 1 ? words[0][0] + words[1][0] : basename(dir).slice(0, 2)).toUpperCase(),
    color: `hsl(${h} 45% 45%)`,
  };
}

// After a ledger is open: wait for its server (the first start installs Python and kingsmint), then show the ledger's
// layout. The page stays: Fava's frames come from the new server.
export async function opened(dir) {
  if (app.current) save(); // the layout of the ledger before, with its Fava pages
  assign({ current: dir, loaded: false });
  closeMenu();
  window.__TAURI__.window.getCurrentWindow().setTitle(`${basename(dir)} — Kingsmint`);
  app.status = { message: t("preparing"), failed: false, log: [] };
  app.cover = "status";
  assign({ imported: true, ledgerLang: "en" });
  // the last lines of uv (Downloading fava (11.2MiB), ...), so the user sees what the first start downloads
  const setupLog = async () => {
    const lines = await invoke("setup_log").catch(() => []);
    if (app.current !== dir) return;
    app.status.log = lines.slice(-6);
  };
  const timer = setInterval(setupLog, 500);
  try {
    const url = await invoke("server_url");
    if (app.current !== dir) return; // another ledger was opened meanwhile
    assign({ serverOrigin: new URL(url).origin });
    // one language: the app shows the open ledger's (its agent's) language
    rpc("settings").then(
      (d) => {
        assign({ ledgerLang: d.settings.language });
        if (app.current === dir && app.ledgerLang !== app.lang) setLang(app.ledgerLang);
      },
      () => {},
    );
    await loadLayout(dir);
    app.cover = null;
    rpc("state").then(applyState, (e) => console.error(e));
    document.dispatchEvent(new Event("km-ledger")); // the Svelte views of the ledger load
  } catch (e) {
    app.status = { ...app.status, message: String(e), failed: true };
    await setupLog();
  } finally {
    clearInterval(timer);
  }
}

// The start screen, only while no ledger is open.
export async function welcome(error = "") {
  assign({ welcomeError: error, recent: await invoke("recent_ledgers") });
  app.cover = "welcome";
}

export const fail = (e) => (app.current ? showMenu(String(e)) : welcome(String(e)));
export const openDir = (dir) => invoke("open_ledger", { dir }).then(opened, fail);
export const pick = () => window.__TAURI__.dialog.open({ directory: true });
export async function openPicked() {
  const dir = await pick();
  if (dir) openDir(dir);
}
export async function create(title, language) {
  if (!title.trim()) return fail(t("enterName"));
  const dir = await pick();
  if (dir) invoke("new_ledger", { dir, title, language }).then(opened, fail);
}

export async function showMenu(error = "") {
  assign({ menuError: error, recent: await invoke("recent_ledgers"), menuOpen: true });
}
export function closeMenu() {
  app.menuOpen = false;
}

export const sample = () => {
  closeMenu();
  invoke("sample_ledger", { language: app.lang }).then(opened, fail);
};

// The ledger's state: a dot on its badge in the rail; problems also above the panels, with the button that fixes them.
export function ledgerState(check) {
  app.check = check;
}

// The ledger's state: statements waiting, the check's problems, a first import. The app sends it after the ledger's
// files changed (ledger-changed); the page asks for it when the ledger opens.
function applyState(status) {
  const { inbox, check } = status;
  if (app.imported !== status.imported) {
    const first = app.imported && !status.imported;
    assign({ imported: status.imported });
    if (first)
      pane("inbox"); // a new ledger starts in the inbox, which says what to do
    else {
      if (visible("inbox")) refreshInbox();
      pane("dashboard"); // the first import: what it brought
    }
  }
  app.waiting = inbox;
  const seen = `${inbox.join("\n")}\0${check}\0${app.imported}`;
  if (seen !== app.inboxSeen) {
    assign({ inboxSeen: seen });
    if (visible("inbox")) refreshInbox();
  }
  ledgerState(check);
}

// The start screen's and the ledger menu's buttons, and the home folder for ~ in paths.
export function initLedger() {
  ledgerState(null);
  // the state of the ledger shown only: a change of the ledger before may arrive after another one opened
  listen("ledger-changed", (e) => e.payload.dir === app.current && app.serverOrigin && applyState(e.payload.state));
  window.__TAURI__.path.homeDir().then((h) => assign({ home: h.replace(/[\\/]$/, "") }));
  // a click outside closes it (clicks inside stop at the menu); clicks into Fava's iframe blur this window instead
  addEventListener("click", () => app.menuOpen && closeMenu());
  addEventListener("blur", () => {
    if (app.menuOpen && document.activeElement?.tagName === "IFRAME") closeMenu();
  });
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && app.menuOpen) closeMenu();
  });
}
