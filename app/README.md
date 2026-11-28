# Kingsmint app (prototype)

A desktop app in Tauri: Fava of a ledger, an inbox for statements, and terminals with a coding agent
(Claude Code, Codex, Cursor, pi) in the ledger folder: the pages in panels (Dockview) that the user arranges, the
terminals as tabs of a sidebar on the right, pinned beside the panels or floating over them. Versions of the
ledger are kept with jj.

The window shows the app's own page (`dist/`, built by Vite from `ui/`, on `tauri://localhost`). Fava comes from the
ledger's own server, `server/server.py`, on `http://127.0.0.1:<port>/fava`: another origin, so a script in Fava's
frame (Fava, its extensions, a ledger's document) cannot call the app's commands. The server adds `bridge.js` to
Fava's pages, which tells the page by messages what happens in a frame (drag the window, the app's shortcuts,
⌘-click into a split, the current page). The page's views of the ledger (inbox, overview, reports, settings, history) are
Svelte components in `ui/js/*.svelte`; they get the data with the app's command `rpc`, which the app sends to the
server's stdin as a line of JSON (`server/rpc.py`). The app (Rust)
keeps the window, the terminals, the native dialogs, the files the user adds, and watches the ledger's files: after a
change it asks the server for the ledger's state and sends it to the page (`ledger-changed`). The app starts the
server in the ledger with the ledger's Python (`uv run`, with no packages of its own: Fava brings werkzeug, which serves it), so Fava and
the kingsmint extensions are the ledger's version, and a ledger of an older kingsmint works too. `capabilities/default.json` allows the app's commands for its own page only, and `build.rs` lists them.

Run it (macOS, Linux):

```sh
scripts/fetch-sidecars.sh   # once: uv and jj, shipped with the app
scripts/ui.sh               # after a change in ui/: builds dist/ with Vite
cd src-tauri && cargo run
```

Bundle: `cd src-tauri && cargo tauri build` (runs `scripts/ui.sh` itself).
The icon's source is `src-tauri/icons/icon.svg`; after a change, render it to a 1024 px PNG and run
`cargo tauri icon <png> -o icons`.
