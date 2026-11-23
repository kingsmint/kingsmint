// The rail: Fava, the inbox, the overview, the reports, the settings, and the agent's sidebar. A click shows the panel;
// one that was closed comes back. The agent's button shows the sidebar, or hides it.

import { app } from "./app.svelte.js";
import { PARTS, showPart, visible } from "./panels.js";
import { active, dock, tabs } from "./state.js";
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
    side: app.sidebar.open,
  };
}
