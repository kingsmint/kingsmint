// The rail: the inbox, the overview and three of its views, the views pinned with ★, the reports, Fava, the settings,
// and the agent's sidebar. A click shows the panel; one that was closed comes back. A view goes in the overview active
// last, as a step of its history; ⌘-click opens it in a new overview beside. The agent's button shows the sidebar, or
// hides it.

import { app } from "./app.svelte.js";
import { addOverview, PARTS, saveSoon, shown, showPart, visible } from "./panels.js";
import { active, dock, overviews, tabs } from "./state.js";
import { defaultAgent, newTab, showTab } from "./terminal.js";

export function pane(id) {
  if (!dock) return;
  if (id !== "side") return showPart(id);
  if (app.sidebar.open) {
    app.sidebar.open = false;
    return;
  }
  const tab = active ?? tabs.find((t) => t.agent) ?? tabs[0];
  tab ? showTab(tab) : newTab(defaultAgent());
}
export function railState() {
  app.shown = {
    ...Object.fromEntries(["fava", ...Object.keys(PARTS)].map((v) => [v, visible(v)])),
    overview: [...overviews.keys()].some(shown),
    side: app.sidebar.open,
  };
}

// the overview's views on the rail
export const VIEWS = {
  overview: { name: "overview" },
  txns: { name: "txns" },
  spending: { name: "account", account: "Expenses" },
  runway: { name: "runway" },
};
// which of them an overview's view belongs to: a transaction to the transactions, an expense account to the spending
export const railKey = (view) =>
  view.name === "txns" || view.name === "txn"
    ? "txns"
    : view.name === "account" && view.account?.startsWith("Expenses")
      ? "spending"
      : view.name === "runway"
        ? "runway"
        : "overview";
// `key`: a view of VIEWS, or a pinned view
export function showView(key, split = false) {
  if (!dock) return;
  const id = overviews.has(app.overview.id) ? app.overview.id : "dashboard";
  const view = VIEWS[key] ?? key;
  const panel = dock.getPanel(id);
  if (split && panel)
    return addOverview({ group: panel.group, direction: "right", params: { ...overviews.get(id)?.(), view } });
  document.dispatchEvent(new CustomEvent("km-go", { detail: { panel: id, view } }));
}

// A pinned view: its label and the view, without the days chosen in a chart (the period is the overview's). Saved with
// the ledger's layout (panels.js), as its views name the ledger's accounts.
export const PINS_ON_RAIL = 3; // the rest are in the rail's "…" menu, so the rail fits a small window
export const pinKey = (view) => JSON.stringify({ ...view, days: undefined });
export const pinOf = (view) => app.pins.findIndex((p) => pinKey(p.view) === pinKey(view));
export function togglePin(view, label) {
  const i = pinOf(view);
  if (i >= 0) app.pins.splice(i, 1);
  else app.pins.push({ label, view: JSON.parse(pinKey(view)) });
  saveSoon();
}
export function renamePin(i, label) {
  if (!label.trim()) return;
  app.pins[i].label = label.trim();
  saveSoon();
}
export function unpin(i) {
  app.pins.splice(i, 1);
  saveSoon();
}
