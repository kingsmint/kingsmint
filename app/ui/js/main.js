// The app's page: each module's init() wires its part of the page, in this order, then the app opens the ledger.
import "@fontsource/fira-sans/400.css";
import "@fontsource/fira-sans/500.css";
import "@fontsource/fira-mono/400.css";
import "@fontsource/fira-mono/700.css";
import "@xterm/xterm/css/xterm.css";
import "../style.css";

import { mount } from "svelte";
import AppSettings from "./AppSettings.svelte";
import Cover from "./Cover.svelte";
import Dashboard from "./Dashboard.svelte";
import { initFava } from "./fava.js";
import { initHistory } from "./history.js";
import Inbox from "./Inbox.svelte";
import { applyLang, systemLang } from "./i18n.js";
import { initInbox } from "./inbox.js";
import LedgerMenu from "./LedgerMenu.svelte";
import LedgerSettings from "./LedgerSettings.svelte";
import { initLedger, opened, welcome } from "./ledger.js";
import Notices from "./Notices.svelte";
import Popups from "./Popups.svelte";
import { initPanels, save } from "./panels.js";
import Rail from "./Rail.svelte";
import Reports from "./Reports.svelte";
import Sidebar from "./Sidebar.svelte";
import { checkClaude, initSettings } from "./settings.js";
import { initShortcuts } from "./shortcuts.js";
import { assign } from "./state.js";
import { agentMenu, initTerminal } from "./terminal.js";
import { byId, invoke } from "./util.js";
import VersionHistory from "./VersionHistory.svelte";
import { applyZoom } from "./zoom.js";

initPanels();
initFava();
initTerminal();
initLedger();
initInbox();
initSettings();
initHistory();
initShortcuts();
// Svelte sets wa-button's disabled as a property once the element is defined; before, as an attribute, where
// disabled="false" disables it too. Web Awesome's loader defines an element only when it finds one in the page, and
// the buttons are all in the components, so the page defines it first.
await import(/* @vite-ignore */ "/vendor/@awesome.me/webawesome/dist-cdn/components/button/button.js");
// <wa-icon name="…">: Lucide's icons, which scripts/ui.sh copies into the app; Font Awesome's would come from its CDN
const { registerIconLibrary } = await import(
  /* @vite-ignore */ "/vendor/@awesome.me/webawesome/dist-cdn/webawesome.loader.js"
);
registerIconLibrary("default", { resolver: (name) => `/vendor/lucide-static/icons/${name}.svg` });
mount(Rail, { target: byId("rail") });
mount(Sidebar, { target: document.querySelector("main") });
mount(Notices, { target: byId("work"), anchor: byId("dock") });
mount(Cover, { target: byId("work") });
mount(Popups, { target: byId("popups") });
mount(AppSettings, { target: byId("settings-app-root") });
mount(LedgerMenu, { target: byId("menu-root") });
mount(Inbox, { target: byId("inbox") });
mount(Dashboard, { target: byId("dashboard") });
mount(Reports, { target: byId("reports") });
mount(LedgerSettings, { target: byId("settings-ledger") });
mount(VersionHistory, { target: byId("history-root") });
// Fava's page, saved with the layout when the app closes or goes to another ledger
addEventListener("pagehide", save);

// the app's settings and language, then the open ledger (or the start screen)
await agentMenu();
const settings = (await invoke("app_settings")) || {};
assign({ appSettings: settings, lang: settings.lang || systemLang() });
applyLang();
applyZoom();
checkClaude();
addEventListener("focus", checkClaude);
const dir = await invoke("ledger_dir");
dir ? opened(dir) : welcome();
