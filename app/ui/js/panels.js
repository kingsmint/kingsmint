// Panels (Dockview): Fava, the inbox, the settings, and one panel per terminal. A terminal runs one program (an agent,
// or "" for a shell), which keeps running while another panel shows. `session` is the program's number; events of an
// ended program are ignored. A Claude Code terminal has its own session id (`claude`), so it continues the same
// conversation after a restart. The layout, with each terminal's agent and session id and Fava's page, is saved per
// ledger.

import * as DV from "dockview-core";
import { flushSync, mount, unmount } from "svelte";
import { app } from "./app.svelte.js";
import FavaPanel from "./FavaPanel.svelte";
import { addFava, favaUrl, firstFava } from "./fava.js";
import GroupActions from "./GroupActions.svelte";
import { t } from "./i18n.js";
import { refreshInbox } from "./inbox.js";
import { railState } from "./rail.js";
import { loadSettings } from "./settings.js";
import { active, assign, dock, favas, lastFava, loaded, tabs } from "./state.js";
import TabHeader from "./TabHeader.svelte";
import TerminalPanel from "./TerminalPanel.svelte";
import { addTab, defaultAgent, newTab, showTab } from "./terminal.js";
import { byId, dark, invoke } from "./util.js";

export const PARTS = { inbox: "inbox", reports: "reports", settings: "settings" }; // the pages that are in one panel only

export function save() {
  if (!loaded || !app.current || !dock) return;
  const layout = dock.toJSON();
  for (const [id, frame] of favas) {
    const url = favaUrl(frame);
    if (url && layout.panels[id]) layout.panels[id].params = { url };
  }
  invoke("save_tabs", { dir: app.current, tabs: { layout } });
}
export let saveTimer;
export const saveSoon = () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 500);
};

// A part of Dockview (a panel's content, a tab, a group's header) made by a Svelte component, with Dockview's
// parameters as its props.
function svelte(Component) {
  const element = document.createElement("div");
  element.style.height = "100%";
  let instance;
  return {
    element,
    init(params) {
      instance = mount(Component, { target: element, props: params });
      flushSync(); // its effects now, as Dockview expects: a terminal or Fava is known once its panel is added
    },
    dispose() {
      if (instance) unmount(instance);
    },
  };
}

// Fava (the view used last), the inbox or the settings: shows it, and adds it again after it was closed.
// A closed Fava comes back left of the terminals, as in a new ledger's layout: Fava | agent.
export function showPart(id) {
  if (id === "fava" && favas.size)
    return dock.getPanel(favas.has(lastFava) ? lastFava : firstFava().id).api.setActive();
  if (id === "fava") {
    const term = active?.api ?? tabs.at(-1)?.api;
    return addFava(term ? { group: term.group, direction: "left" } : {});
  }
  let panel = dock.getPanel(id);
  if (!panel) {
    const near = firstFava() ?? dock.getPanel("inbox") ?? dock.getPanel("settings");
    panel = dock.addPanel({
      id,
      component: id,
      title: t(id),
      position: near ? { referencePanel: near.id } : undefined,
    });
  }
  panel.api.setActive();
  if (id === "inbox") refreshInbox();
  if (id === "settings") loadSettings();
}
export const shown = (id) => !!dock?.getPanel(id)?.api.isVisible;
export const visible = (id) => (id === "fava" ? [...favas.keys()].some(shown) : shown(id)); // "fava": any view of Fava

export const maximize = (api) => (api.isMaximized() ? api.exitMaximized() : api.maximize());

// The tab's title turns into a field (TabHeader.svelte).
export const rename = (tab) => (app.renaming = tab.api.id);

// Right-click on a tab
export function tabMenu(api, x, y) {
  const isTerm = tabs.some((t) => t.api.id === api.id);
  app.popup = { kind: "tab", api, x, y, isTerm, isFava: favas.has(api.id), terminals: tabs.length };
}
// An action of the tab's menu on the panel `api`.
export function tabAction(api, act) {
  app.popup = null;
  if (!dock?.getPanel(api.id)) return;
  if (act === "maximize") return maximize(api);
  if (act === "close") return api.close();
  if (act === "clone" && favas.has(api.id)) return addFava({ group: api.group, url: favaUrl(favas.get(api.id)) });
  const tab = tabs.find((t) => t.api.id === api.id);
  if (tab) TAB_ACTIONS[act](tab);
}
export const TAB_ACTIONS = {
  // after the terminal started: it takes the focus then, which would end the rename at once
  rename: async (tab) => {
    await showTab(tab);
    rename(tab);
  },
  clone: (tab) => newTab(tab.agent),
  // a Claude Code tab continues its conversation
  restart: (tab) => {
    if (tab.session) invoke("pty_kill", { session: tab.session });
    tab.session = null;
    showTab(tab);
  },
  others: (tab) => {
    tabs.filter((t) => t !== tab).forEach((t) => t.api.close());
    showTab(tab);
  },
};

export function makeDock() {
  const created = new DV.DockviewComponent(byId("dock"), {
    // Tauri's file-drop handler (the inbox needs it) takes HTML5 drags in WKWebView: a tab would never drop
    dndStrategy: "pointer",
    // a panel's content stays where it is when the panel moves or hides: Fava does not load again, a terminal keeps its text
    defaultRenderer: "always",
    theme: dark.matches ? DV.themeDark : DV.themeLight,
    createComponent: ({ name }) =>
      name === "term"
        ? svelte(TerminalPanel)
        : name === "fava"
          ? svelte(FavaPanel)
          : { element: byId(PARTS[name]), init() {} },
    // Dockview asks createTabComponent only with a tab component's name; without one it draws its own tabs
    defaultTabComponent: "tab",
    createTabComponent: () => svelte(TabHeader),
    createRightHeaderActionComponent: () => svelte(GroupActions),
  }).api;
  assign({ dock: created });
  // a closed part goes back out of the dock, where the code that fills it still finds it
  // the empty part of a tab bar is the window's title bar: it moves the window, a double click zooms it. Dockview would
  // drag the group from there; a group moves by its tabs.
  const bare = (e) => e.target.classList.contains("dv-void-container");
  const win = window.__TAURI__.window.getCurrentWindow();
  byId("dock").addEventListener(
    "pointerdown",
    (e) => {
      if (bare(e)) e.stopPropagation();
    },
    true,
  );
  byId("dock").addEventListener("mousedown", (e) => {
    if (e.button === 0 && e.detail === 1 && bare(e)) {
      e.preventDefault();
      win.startDragging();
    }
  });
  byId("dock").addEventListener("dblclick", (e) => {
    if (bare(e)) win.toggleMaximize();
  });
  dock.onDidRemovePanel((p) => {
    if (PARTS[p.id]) byId("parts").append(byId(PARTS[p.id]));
  });
  dock.onDidLayoutChange(() => {
    saveSoon();
    railState();
  });
  dock.onDidActivePanelChange((p) => {
    if (favas.has(p?.id)) assign({ lastFava: p.id });
    railState();
  });
  dark.addEventListener("change", () => dock.updateOptions({ theme: dark.matches ? DV.themeDark : DV.themeLight }));
}

// A ledger on the server's page: its saved layout, else Fava with the first agent and a shell beside it.
export async function loadLayout(dir) {
  assign({ loaded: false });
  if (!dock) makeDock();
  dock.clear();
  assign({ tabs: [], active: null });
  const saved = await invoke("load_tabs", { dir });
  assign({ restoring: true });
  let ok = false;
  // a layout without panels (closed one by one, or saved by an older app after an error) gives the new layout
  if (Object.keys(saved?.layout?.panels ?? {}).length) {
    try {
      dock.fromJSON(saved.layout);
      ok = true;
    } catch (e) {
      invoke("log", { message: `layout: ${e}` });
      dock.clear();
      assign({ tabs: [] });
    }
  }
  if (!ok) {
    dock.addPanel({ id: "fava", component: "fava", title: t("fava") });
    assign({ restoring: !!saved?.tabs?.length }); // the tabs of an older app: they continue too
    (saved?.tabs?.length ? saved.tabs : [...new Set([defaultAgent(), ""])].map((agent) => ({ agent }))).forEach(addTab);
  }
  assign({ restoring: false, loaded: true });
  titles();
  railState();
  // a saved layout can show the inbox or the settings at once: they load as when they are opened
  if (visible("inbox")) refreshInbox();
  if (visible("settings")) loadSettings();
}
// the parts' titles in the app's language
export const titles = () => {
  Object.keys(PARTS).forEach((id) => dock?.getPanel(id)?.api.setTitle(t(id)));
  favas.forEach((_, id) => dock.getPanel(id)?.api.setTitle(t("fava")));
};

// The tab menu, and what closes the menus.
export function initPanels() {
  addEventListener("click", () => (app.popup = null));
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") app.popup = null;
  });
  // no browser menu (Reload, Inspect Element) outside text fields
  addEventListener("contextmenu", (e) => {
    if (!e.target.closest("input, [contenteditable=true]")) e.preventDefault();
  });
}
