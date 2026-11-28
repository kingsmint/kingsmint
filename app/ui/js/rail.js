// The rail: the inbox, the overview and three of its views, the views pinned with ★, the reports, Fava, the settings,
// and the agent's sidebar. A click shows the panel; one that was closed comes back. A view goes in the overview active
// last, as a step of its history; ⌘-click opens it in a new overview beside. The agent's button shows the sidebar, or
// hides it.

import { app } from "./app.svelte.js";
import { addOverview, PARTS, saveSoon, shown, showPart, visible } from "./panels.js";
import { saveApp } from "./settings.js";
import { active, dock, overviews, tabs } from "./state.js";
import { defaultProfile, newTab, showTab } from "./terminal.js";

export function pane(id) {
  if (!dock) return;
  if (id !== "side") return showPart(id);
  if (app.sidebar.open) {
    app.sidebar.open = false;
    return;
  }
  const tab = active ?? tabs.find((t) => t.agent) ?? tabs[0];
  tab ? showTab(tab) : newTab(defaultProfile());
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
// col: Trends' period. trends: false matches a view without it (a pin made before Trends), but a pin keeps it, so a
// Categories pin opens as Categories whatever the app's setting
export const pinKey = (view) =>
  JSON.stringify({ ...view, days: undefined, col: undefined, trends: view.trends || undefined });
export const pinOf = (view) => app.pins.findIndex((p) => pinKey(p.view) === pinKey(view));
export function togglePin(view, label) {
  const i = pinOf(view);
  if (i >= 0) app.pins.splice(i, 1);
  else app.pins.push({ label, view: JSON.parse(JSON.stringify({ ...view, days: undefined, col: undefined })) });
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

// The rail's order and the items hidden from it: the app's settings, as they are the user's habits, not the ledger's.
// "pins" is the pinned views, as one item. An item that a newer app adds goes where it is by default.
export const RAIL = ["inbox", "overview", "txns", "spending", "runway", "pins", "reports", "fava", "side"];
export const RAIL_LABELS = {
  inbox: "inbox",
  overview: "overview",
  txns: "transactions",
  spending: "expenses",
  runway: "runway",
  pins: "pinnedViews",
  reports: "reports",
  fava: "fava",
  side: "agent",
};
export function railOrder() {
  const order = (app.appSettings.rail?.order ?? []).filter((k) => RAIL.includes(k));
  RAIL.forEach((k, i) => order.includes(k) || order.splice(Math.min(i, order.length), 0, k));
  return order;
}
export const railHidden = () => app.appSettings.rail?.hidden ?? [];
const setRail = (order, hidden) => saveApp({ rail: { order, hidden } });
// `key` before or after `to`
export function moveRail(key, to, after) {
  const order = railOrder().filter((k) => k !== key);
  order.splice(order.indexOf(to) + (after ? 1 : 0), 0, key);
  setRail(order, railHidden());
}
export const hideRail = (key, hide) =>
  setRail(railOrder(), hide ? [...railHidden(), key] : railHidden().filter((k) => k !== key));
export const resetRail = () => setRail(RAIL, []);
