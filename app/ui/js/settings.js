// Settings: the ledger's, in its files (LedgerSettings.svelte), and the app's, on this computer.

import { app } from "./app.svelte.js";
import { reloadFava } from "./fava.js";
import { applyLang } from "./i18n.js";
import { refreshInbox } from "./inbox.js";
import { welcome } from "./ledger.js";
import { titles, visible } from "./panels.js";
import { assign, favas } from "./state.js";
import { invoke } from "./util.js";
import { applyZoom } from "./zoom.js";

export const APP_LANGUAGES = [
  ["en", "English"],
  ["sk", "Slovenčina"],
];

export function loadSettings() {
  document.dispatchEvent(new Event("km-settings")); // the ledger's: the component loads them again
}
// Saves a change of the app's settings ({ agent } or { fontSize }) on this computer.
export function saveApp(change) {
  app.appSettings = { ...app.appSettings, ...change };
  invoke("save_app_settings", { settings: { ...app.appSettings } });
  applyZoom();
}
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
