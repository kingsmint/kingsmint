// History: the popup of the ledger's versions (VersionHistory.svelte) under the rail's button.
import { app } from "./app.svelte.js";

export const showHistory = () => (app.historyOpen = true);
export const closeHistory = () => (app.historyOpen = false);

// A click outside the popup or Escape closes it; clicks inside stop at the popup.
export function initHistory() {
  addEventListener("click", closeHistory);
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeHistory();
  });
}
