// Settings: the ledger's, in its files (LedgerSettings.svelte), and the app's, on this computer.

import { app } from "./app.svelte.js";
import { reloadFava } from "./fava.js";
import { applyLang } from "./i18n.js";
import { refreshInbox } from "./inbox.js";
import { welcome } from "./ledger.js";
import { titles, visible } from "./panels.js";
import { assign, favas } from "./state.js";
import { retheme } from "./terminal.js";
import { invoke } from "./util.js";
import { applyZoom } from "./zoom.js";

export const APP_LANGUAGES = [
  ["en", "English"],
  ["sk", "Slovenčina"],
];

export function loadSettings() {
  document.dispatchEvent(new Event("km-settings")); // the ledger's: the component loads them again
}
// Saves a change of the app's settings ({ agent }, { fontSize }, { theme } or { mode }) on this computer.
export function saveApp(change) {
  app.appSettings = { ...app.appSettings, ...change };
  invoke("save_app_settings", { settings: { ...app.appSettings } });
  applyZoom();
  applyTheme();
}
// The app's themes (public/themes.css), each a light and a dark variant: [name, [[id, name of its dark variant]]], a
// theme whose dark variants differ little in one card. "default" is Web Awesome's.
export const APP_THEMES = [
  ["Web Awesome", [["default"]]],
  [
    "Catppuccin",
    [
      ["catppuccin", "Mocha"],
      ["catppuccin-macchiato", "Macchiato"],
      ["catppuccin-frappe", "Frappé"],
    ],
  ],
  [
    "Rosé Pine",
    [
      ["rose-pine", "Main"],
      ["rose-pine-moon", "Moon"],
    ],
  ],
  ["Gruvbox", [["gruvbox"]]],
  ["Solarized", [["solarized"]]],
  ["Everforest", [["everforest"]]],
  ["Nord", [["nord"]]],
];
// The theme and dark mode of the settings, known values only (the settings' file can hold anything)
export const themeName = () =>
  APP_THEMES.some(([, variants]) => variants.some(([id]) => id === app.appSettings.theme))
    ? app.appSettings.theme
    : "default";
export const modeName = () => (["light", "dark"].includes(app.appSettings.mode) ? app.appSettings.mode : "system");
// The page (dark.js) and Fava's frames take the theme and the mode; the terminals follow.
export function applyTheme() {
  const m = { kingsmint: true, theme: themeName(), mode: modeName() };
  window.km_set(m);
  retheme();
  favas.forEach((f) => f.contentWindow?.postMessage(m, app.serverOrigin));
}
// The kingsmint extension in the Claude app (claude_extension in main.rs): at start, and when the window comes back,
// after the user installed it in the Claude app.
export const checkClaude = async () => (app.claude = await invoke("claude_extension").catch(() => ""));
// The Claude app asks the user to install the extension this app ships.
export const installClaude = () => invoke("claude_extension_install").catch(console.error);
export function setLang(value) {
  assign({ lang: value, appSettings: { ...app.appSettings, lang: value } });
  invoke("save_app_settings", { settings: app.appSettings });
  applyLang();
  if (visible("inbox")) refreshInbox();
  if (visible("settings")) loadSettings();
  titles();
  if (!app.current) welcome();
}

// The app's settings' fields, and what follows a change of the ledger's language.
export function initSettings() {
  // the ledger's language changed: its agent's tasks, Fava (it picks its language when it draws a page), and the app
  document.body.addEventListener("km-ledger-language", (e) => {
    assign({ ledgerLang: e.detail.value });
    favas.forEach(reloadFava);
    if (app.ledgerLang !== app.lang) setLang(app.ledgerLang);
  });
}
