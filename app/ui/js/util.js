// What every module uses: the app's commands (Tauri), elements by id, and the system's dark mode.
export const { invoke } = window.__TAURI__.core;
export const { listen } = window.__TAURI__.event;
export const byId = (id) => document.getElementById(id);
export const show = (id, on) => (byId(id).hidden = !on);
export const dark = matchMedia("(prefers-color-scheme: dark)");
// A request to the open ledger's server, on its stdin (server/rpc.py): its result, or an error
export const rpc = (method, params = {}) => invoke("rpc", { method, params });
// use:focusField on a Web Awesome field: focus once it has rendered. Svelte's autofocus calls focus() at once, before
// wa-input has its inner <input>, which throws and leaves the field without focus.
export const focusField = (el) =>
  void customElements
    .whenDefined(el.localName)
    .then(() => el.updateComplete)
    .then(() => el.isConnected && el.focus());
