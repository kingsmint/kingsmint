// The page's state that its views show: a Svelte state, so a component that reads a field draws again when it
// changes. Set a field directly (app.lang = "sk") or with assign() in state.js.
export const app = $state({
  installed: [], // the agents found on PATH
  current: null, // the open ledger's folder
  serverOrigin: "", // the ledger's server, which serves Fava: http://127.0.0.1:<port>
  home: "", // the user's home folder, for ~ in paths
  imported: true, // the ledger has an imported statement; false: a new ledger, which the inbox starts
  appSettings: {}, // the app's settings, on this computer
  lang: "en", // the app's language
  ledgerLang: "en", // the open ledger's: tasks for its agent
  inboxSeen: "", // the inbox and check the inbox panel shows
  inboxError: "", // an error of the last inbox action, shown once
  recent: [], // the ledgers opened before that still exist, newest first
  welcomeError: "", // why a ledger did not open, on the start screen
  menuError: "", // the same, in the ledger menu
  menuOpen: false, // the ledger menu shows
  historyOpen: false, // the versions' popup shows
  // the agent's sidebar on the right (Sidebar.svelte): shown, pinned beside the panels or floating over them (it hides
  // on a click elsewhere), wide over the panels, its width in px; saved with the ledger's layout
  sidebar: { open: true, pinned: true, wide: false, width: 420 },
  shown: { fava: true, inbox: false, dashboard: false, reports: false, settings: false, side: true }, // the rail's panels that show
  waiting: [], // the statements waiting in inbox/
  reports: 0, // the ledger's reports (reports/*.toml): the rail shows Reports once there is one
  check: null, // what `kingsmint check` said: "" when the ledger is fine, null while it is not known
  agentNote: "", // an agent's question that only the user answers, above the panels
  dropping: false, // files are dragged over the window
  popup: null, // the open menu: { kind: "tab", api, x, y, isTerm, isFava, terminals } or { kind: "add", group, side, x, y }
  cover: null, // over the panels: "welcome" (no ledger open), "status" (the wait for the server), or null
  status: { message: "", failed: false, log: [] }, // the wait: the message, and the last lines of uv
  renaming: null, // the panel whose tab title is a field (the tab menu's Rename)
});
