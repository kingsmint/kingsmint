// Panels (Dockview): Fava, the inbox, the overview, the reports and the settings; and in the agent's sidebar on the
// right (a second Dockview, one group), one tab per terminal. A terminal runs one program (an agent,
// or "" for a shell), which keeps running while another tab shows or the sidebar hides. `session` is the program's number; events of an
// ended program are ignored. An agent's terminal keeps its conversation's id (`conversation`), so it continues the
// same conversation after a restart. The layout, with each terminal's agent and session id and Fava's page, is saved per
// ledger, with the sidebar's.

import * as DV from "dockview-core";
import { flushSync, mount, unmount } from "svelte";
import { app } from "./app.svelte.js";
import Dashboard from "./Dashboard.svelte";
import FavaPanel from "./FavaPanel.svelte";
import { addFava, favaUrl, firstFava } from "./fava.js";
import GroupActions from "./GroupActions.svelte";
import { t } from "./i18n.js";
import { refreshInbox } from "./inbox.js";
import { railState } from "./rail.js";
import SideActions from "./SideActions.svelte";
import { loadSettings } from "./settings.js";
import { assign, dock, favas, lastFava, loaded, overviews, side, tabs } from "./state.js";
import TabHeader from "./TabHeader.svelte";
import TerminalPanel from "./TerminalPanel.svelte";
import { addTab, defaultProfile, newTab, showTab } from "./terminal.js";
import { byId, dark, invoke } from "./util.js";

export const PARTS = { inbox: "inbox", dashboard: "dashboard", reports: "reports", settings: "settings" }; // the pages that are in one panel only

export function save() {
  if (!loaded || !app.current || !dock) return;
  const layout = dock.toJSON();
  for (const [id, frame] of favas) {
    const url = favaUrl(frame);
    if (url && layout.panels[id]) layout.panels[id].params = { url };
  }
  const { open, pinned, width } = app.sidebar;
  invoke("save_tabs", {
    dir: app.current,
    tabs: { layout, side: side.toJSON(), sidebar: { open, pinned, width }, pins: app.pins },
  });
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

// One more overview beside the group's (direction), starting on `params`: the view, unit and period of the one split
export function addOverview({ group, direction, params } = {}) {
  const id = `overview-${crypto.randomUUID().slice(0, 8)}`;
  app.overview.id = id; // the new one is active: the rail's views go there (it is not in overviews yet)
  dock.addPanel({
    id,
    component: "overview",
    title: t("dashboard"),
    params,
    position: group ? { referenceGroup: group, direction } : undefined,
  });
}

// Fava (the view used last), the inbox or the settings: shows it, and adds it again after it was closed.
// A closed Fava comes back beside the overview, as in a new ledger's layout.
export function showPart(id) {
  if (id === "fava" && favas.size)
    return dock.getPanel(favas.has(lastFava) ? lastFava : firstFava().id).api.setActive();
  if (id === "fava") return addFava(dock.getPanel("dashboard") ? { group: dock.getPanel("dashboard").group } : {});
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

// a terminal's tab widens the sidebar over the panels, and back
export function maximize(api) {
  if (tabs.some((t) => t.api.id === api.id)) app.sidebar.wide = !app.sidebar.wide;
  else if (api.isMaximized()) api.exitMaximized();
  else api.maximize();
}

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
  if (!dock?.getPanel(api.id) && !side?.getPanel(api.id)) return;
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
  clone: (tab) => newTab(tab.profile),
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

// A Dockview in `element`: the panels, or the sidebar (`sidebar`: terminals only, in one group, so a tab moves only
// along the tab bar).
function makeView(element, sidebar) {
  const view = new DV.DockviewComponent(element, {
    // Tauri's file-drop handler (the inbox needs it) takes HTML5 drags in WKWebView: a tab would never drop
    dndStrategy: "pointer",
    // a panel's content stays where it is when the panel moves or hides: Fava does not load again, a terminal keeps its text
    defaultRenderer: "always",
    disableFloatingGroups: sidebar,
    theme: dark.matches ? DV.themeDark : DV.themeLight,
    createComponent: ({ name }) =>
      name === "term"
        ? svelte(TerminalPanel)
        : name === "fava"
          ? svelte(FavaPanel)
          : name === "overview"
            ? svelte(Dashboard)
            : { element: byId(PARTS[name]), init() {} },
    // Dockview asks createTabComponent only with a tab component's name; without one it draws its own tabs
    defaultTabComponent: "tab",
    createTabComponent: () => svelte(TabHeader),
    createRightHeaderActionComponent: () => svelte(sidebar ? SideActions : GroupActions),
  }).api;
  // a tab drops only in its own Dockview, and in the sidebar only into its tab bar
  view.onWillShowOverlay((e) => {
    const other = e.getData() && e.getData().viewId !== view.id;
    if (other || (sidebar && (e.kind === "edge" || (e.kind === "content" && e.position !== "center"))))
      e.preventDefault();
  });
  // the empty part of a tab bar is the window's title bar: it moves the window, a double click zooms it. Dockview would
  // drag the group from there; a group moves by its tabs.
  const bare = (e) => e.target.classList.contains("dv-void-container");
  const win = window.__TAURI__.window.getCurrentWindow();
  element.addEventListener(
    "pointerdown",
    (e) => {
      if (bare(e)) e.stopPropagation();
    },
    true,
  );
  element.addEventListener("mousedown", (e) => {
    if (e.button === 0 && e.detail === 1 && bare(e)) {
      e.preventDefault();
      win.startDragging();
    }
  });
  element.addEventListener("dblclick", (e) => {
    if (bare(e)) win.toggleMaximize();
  });
  view.onDidLayoutChange(() => {
    saveSoon();
    railState();
  });
  dark.addEventListener("change", () => view.updateOptions({ theme: dark.matches ? DV.themeDark : DV.themeLight }));
  return view;
}

export function makeDock() {
  assign({ dock: makeView(byId("dock"), false), side: makeView(byId("side-dock"), true) });
  // a closed part goes back out of the dock, where the code that fills it still finds it
  dock.onDidRemovePanel((p) => {
    if (PARTS[p.id]) byId("parts").append(byId(PARTS[p.id]));
  });
  dock.onDidActivePanelChange(({ panel: p }) => {
    if (favas.has(p?.id)) assign({ lastFava: p.id });
    if (overviews.has(p?.id)) app.overview.id = p.id;
    railState();
  });
}

// A ledger on the server's page: its saved layout, else the overview and Fava, with the first agent and a shell in the
// sidebar. A new ledger then goes to the inbox (applyState in ledger.js).
export async function loadLayout(dir) {
  assign({ loaded: false });
  if (!dock) makeDock();
  dock.clear();
  side.clear();
  assign({ tabs: [], active: null });
  const saved = await invoke("load_tabs", { dir });
  assign({ restoring: true });
  Object.assign(app.sidebar, saved?.sidebar ?? {}, { wide: false });
  app.pins = saved?.pins ?? [];
  if (Object.keys(saved?.side?.panels ?? {}).length) {
    try {
      side.fromJSON(saved.side);
    } catch (e) {
      invoke("log", { message: `sidebar: ${e}` });
      side.clear();
      assign({ tabs: [] });
    }
  }
  // a layout without panels (closed one by one, or saved by an older app after an error) gives the new layout
  if (Object.keys(saved?.layout?.panels ?? {}).length) {
    try {
      dock.fromJSON(saved.layout);
    } catch (e) {
      invoke("log", { message: `layout: ${e}` });
      dock.clear();
      assign({ tabs: tabs.filter((t) => side.getPanel(t.api.id)) });
    }
  }
  // the terminals of a layout from before the sidebar move into it, where their programs continue
  for (const tab of tabs.filter((t) => dock.getPanel(t.api.id))) {
    const { agent, profile, conversation } = tab,
      name = tab.api.title;
    dock.getPanel(tab.api.id).api.close();
    addTab({ agent, profile, conversation, name });
  }
  if (!dock.panels.length) {
    dock.addPanel({ id: "dashboard", component: "dashboard", title: t("dashboard") });
    dock.addPanel({ id: "fava", component: "fava", title: t("fava"), position: { referencePanel: "dashboard" } });
    dock.getPanel("dashboard").api.setActive();
  }
  if (!tabs.length) {
    assign({ restoring: !!saved?.tabs?.length }); // the tabs of an older app: they continue too
    (saved?.tabs?.length ? saved.tabs : [...new Set([defaultProfile(), ""])].map((profile) => ({ profile }))).forEach(
      addTab,
    );
  }
  assign({ restoring: false, loaded: true });
  // the rail's overview takes the view saved in its panel's parameters (Dashboard.svelte)
  document.dispatchEvent(new CustomEvent("km-overview", { detail: dock.getPanel("dashboard")?.params ?? {} }));
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
  overviews.forEach((_, id) => dock.getPanel(id)?.api.setTitle(t("dashboard")));
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
