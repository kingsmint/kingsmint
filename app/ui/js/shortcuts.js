// The app's keyboard shortcuts, on its page and in Fava's frames (fava.js).
import { app } from "./app.svelte.js";
import { pane, showView } from "./rail.js";
import { active, dock, tabs } from "./state.js";
import { defaultProfile, newTab, showTab } from "./terminal.js";
import { zoom } from "./zoom.js";

export function shortcut(e) {
  if (!e.metaKey) return;
  if (e.key === "+" || e.key === "=" || e.code === "Equal") {
    e.preventDefault();
    return zoom(1);
  }
  if (e.key === "-" || e.code === "Minus") {
    e.preventDefault();
    return zoom(-1);
  }
  if (e.key === "0" || e.code === "Digit0") {
    e.preventDefault();
    return zoom(0);
  }
  // ⌘1-9 in the order of the rail: inbox, the overview's views, Fava, the pinned views; ⌘J shows or hides the agent's sidebar
  const pin = (i) => app.pins[i] && (() => showView(app.pins[i].view));
  const rail = {
    1: () => pane("inbox"),
    2: "overview",
    3: "txns",
    4: "spending",
    5: "runway",
    6: () => pane("fava"),
    7: pin(0),
    8: pin(1),
    9: pin(2),
  }[e.key];
  if (rail) {
    e.preventDefault();
    typeof rail === "string" ? showView(rail) : rail();
  }
  // ⌘N: a cash payment, in the overview's transactions (Dashboard.svelte)
  if (e.code === "KeyN" && !e.shiftKey) {
    e.preventDefault();
    showView("txns");
    document.dispatchEvent(new Event("km-cash"));
  }
  if (e.key === "j") {
    e.preventDefault();
    pane("side");
  }
  if (e.code === "KeyT" && dock) {
    e.preventDefault();
    if (active) newTab(active.profile, active.agent);
    else newTab(defaultProfile());
  }
  // ⌘[ and ⌘]: back and forward in Fava; the window's history holds the frame's pages
  if (!e.shiftKey && (e.code === "BracketLeft" || e.code === "BracketRight")) {
    e.preventDefault();
    e.code === "BracketLeft" ? history.back() : history.forward();
  }
  if (e.shiftKey && (e.code === "BracketLeft" || e.code === "BracketRight") && active) {
    e.preventDefault();
    const i = tabs.indexOf(active) + (e.code === "BracketRight" ? 1 : -1);
    showTab(tabs[(i + tabs.length) % tabs.length]);
  }
}

// The shortcuts on the app's page (Fava's frames get them in fava.js).
export function initShortcuts() {
  addEventListener("keydown", shortcut);
}
