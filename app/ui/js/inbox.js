// Inbox: its Svelte component (Inbox.svelte) shows what `kingsmint scan` says of each statement, and the imported
// periods with their gaps. This module adds files (the native dialog, a drop on the window) and runs the inbox's actions.

import { app } from "./app.svelte.js";
import { t } from "./i18n.js";
import { pane } from "./rail.js";
import { assign } from "./state.js";
import { ask } from "./tasks.js";
import { invoke } from "./util.js";

// the component loads the inbox again
export const refreshInbox = () => app.current && document.dispatchEvent(new Event("km-inbox"));
export async function chooseFiles() {
  const paths = await window.__TAURI__.dialog.open({
    multiple: true,
    filters: [{ name: t("statements"), extensions: ["pdf", "PDF", "csv", "CSV"] }],
  });
  addFiles(paths);
}
export const INBOX_ACTIONS = {
  add: chooseFiles,
  reveal: () => invoke("inbox_reveal"),
  import: () => ask(app.imported ? "import" : "setup"),
  close: () => ask("close"),
};

// Moves a file of inbox/ to the Trash.
export async function removeFile(name) {
  await invoke("inbox_remove", { name }).catch((e) => assign({ inboxError: String(e) }));
  refreshInbox();
}

// Files dropped anywhere on the window go to inbox/.
export async function addFiles(paths) {
  if (!app.current || !paths?.length) return;
  try {
    const skipped = await invoke("inbox_add", { paths });
    assign({ inboxError: skipped.length ? t("notAdded", { files: skipped.join(", ") }) : "" });
  } catch (e) {
    assign({ inboxError: String(e) });
  }
  pane("inbox");
  refreshInbox();
}

// Files dropped on the window.
export function initInbox() {
  window.__TAURI__.webview.getCurrentWebview().onDragDropEvent((e) => {
    const t = e.payload.type;
    app.dropping = !!app.current && (t === "enter" || t === "over");
    if (t === "drop") addFiles(e.payload.paths);
  });
}
