// Fava's panels: an iframe per view of the ledger, links that open in them, and the messages of bridge.js in Fava's
// pages (public/bridge.js), which tell what happens in a frame.

import { app } from "./app.svelte.js";
import { t } from "./i18n.js";
import { shortcut } from "./shortcuts.js";
import { dock, favas, lastFava } from "./state.js";
import { invoke } from "./util.js";

// A Fava panel closed: its frame is gone.
export function forget(id, frame) {
  favas.delete(id);
  paths.delete(frame);
}
// Fava's current page in each frame, as bridge.js tells it
const paths = new WeakMap();
export const favaUrl = (frame) => paths.get(frame);
// Loads the frame's page again: Fava picks its language when it draws a page
export const reloadFava = (frame) => (frame.src = new URL(favaUrl(frame) || "/fava/", app.serverOrigin).href);
// One more view of Fava: in the group, or in a new group beside it (direction); on the page of url. An inactive one
// opens behind the active tab, as a browser's ⌘-click.
export function addFava({ group, direction, url, inactive = false } = {}) {
  const id = `fava-${crypto.randomUUID().slice(0, 8)}`;
  dock.addPanel({
    id,
    component: "fava",
    title: t("fava"),
    params: { url },
    position: group ? { referenceGroup: group, direction } : undefined,
    inactive,
  });
  return id;
}
export const firstFava = () => dock.getPanel([...favas.keys()][0]);
// Shows Fava's page `path` in the panel `id`, or in a new view beside the group `group` when there is none
export function showFava(id, path, group) {
  if (!favas.has(id)) return addFava({ group, direction: "right", url: path });
  favas.get(id).src = new URL(path, app.serverOrigin).href;
  dock.getPanel(id).api.setActive();
}

// Fava's page `path` in the Fava view used last, as one step of the window's history ({ fava: id }): back goes to
// where the step came from (the overview), not to the frame's page before, which location.replace() drops.
// `from`: the overview's panel, to which the Fava panel then shows a way back (a swipe is not obvious)
export function stepToFava(path, from) {
  const id = favas.has(lastFava) ? lastFava : [...favas.keys()][0];
  if (!id) {
    const added = addFava({ url: path }); // a new view: its first page is no step back
    if (from) app.favaBack[added] = from;
    return;
  }
  if (from) app.favaBack[id] = from;
  history.pushState({ fava: id }, "");
  favas.get(id).contentWindow.location.replace(new URL(path, app.serverOrigin).href);
  dock.getPanel(id).api.setActive();
}

// A link in a terminal: an account's page without a filter (the agent's most common link) opens the overview's
// detail of it (Dashboard.svelte, which falls back to Fava without data); another page of this ledger's server (Fava,
// /ledger/) opens in the Fava view used last, any other link in the system's browser
export function openLink(_e, uri) {
  const url = new URL(uri, location.href);
  if (url.origin !== app.serverOrigin) return invoke("open_url", { url: url.href });
  const account = url.pathname.match(/^\/ledger\/account\/([^/]+)\/?$/)?.[1];
  if (account && !url.searchParams.has("filter") && !url.hash) {
    const detail = {
      account: decodeURIComponent(account),
      time: url.searchParams.get("time") ?? "",
      path: url.pathname + url.search,
    };
    return document.dispatchEvent(new CustomEvent("km-account", { detail }));
  }
  showFava(favas.has(lastFava) ? lastFava : [...favas.keys()][0], url.pathname + url.search + url.hash);
}

// A message of bridge.js, only from a Fava frame on the server's origin.
// shortcut: back and forward use the window's history, which holds the pages of all Fava views in one list, so ‹ goes
// back in the view that moved last; keep a list per view when users work with several views side by side
function message(e) {
  const m = e.data;
  const [id, frame] = [...favas].find(([, f]) => f.contentWindow === e.source) ?? [];
  if (!frame || e.origin !== app.serverOrigin || !m?.kingsmint) return;
  const win = window.__TAURI__.window.getCurrentWindow();
  if (m.type === "drag") win.startDragging();
  if (m.type === "zoom") win.toggleMaximize();
  if (m.type === "key") shortcut({ ...m, preventDefault() {} });
  if (m.type === "url" && m.url.startsWith("/fava/")) paths.set(frame, m.url);
  // ⌘-click opens the link beside this view: in the Fava view of another group, else in a new split on the right, so
  // this page stays in sight. A middle click opens it in a new tab behind this one, as in a browser.
  if (m.type === "open" && m.url.startsWith("/fava/")) {
    const group = dock.getPanel(id)?.group;
    if (m.background) return addFava({ group, url: m.url, inactive: true });
    const other = [lastFava, ...favas.keys()].find((o) => favas.has(o) && dock.getPanel(o).group !== group);
    showFava(other, m.url, group);
  }
}

// The messages of bridge.js in Fava's frames.
export function initFava() {
  addEventListener("message", message);
}
