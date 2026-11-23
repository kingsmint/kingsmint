// The rail: the inbox, the overview and three of its views, the reports, Fava, the settings, and the agent's sidebar. A
// click shows the panel; one that was closed comes back. A view goes in the overview active last, as a step of its
// history; ⌘-click opens it in a new overview beside. The agent's button shows the sidebar, or hides it.

import { app } from "./app.svelte.js";
import { addOverview, PARTS, shown, showPart, visible } from "./panels.js";
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
export function showView(key, split = false) {
  if (!dock) return;
  const id = overviews.has(app.overview.id) ? app.overview.id : "dashboard";
  const view = VIEWS[key];
  const panel = dock.getPanel(id);
  if (split && panel)
    return addOverview({ group: panel.group, direction: "right", params: { ...overviews.get(id)?.(), view } });
  document.dispatchEvent(new CustomEvent("km-go", { detail: { panel: id, view } }));
}
