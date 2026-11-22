// The page's handles on Dockview, its terminals and Fava's frames, which several modules use. They stay plain values,
// not Svelte state: a state would wrap them in proxies, and tabs.includes(tab) would no longer find a tab. A module
// cannot assign another module's binding, so the others change them with assign({ name: value }), which also sets
// the fields of the Svelte state (app.svelte.js).
import { app } from "./app.svelte.js";

export let dock = null; // the Dockview API
export let tabs = []; // the terminals
export let active = null; // the terminal used last
export let loaded = false; // the layout of the open ledger is loaded; saving before would overwrite it
export let restoring = false; // the panels fromJSON makes: their programs continue (resume)
export let lastFava = null; // the Fava panel used last: the rail and ⌘2 show it
export const favas = new Map(); // Fava's panels (one or more views of the ledger): panel id → iframe
export const overviews = new Map(); // the overviews (the rail's "dashboard" and its splits): panel id → its state now

export function assign(values) {
  for (const [k, v] of Object.entries(values)) {
    if (k in SETTERS) SETTERS[k](v);
    else if (k in app) app[k] = v;
    else throw new Error(`no state ${k}`);
  }
}
const SETTERS = {
  dock: (v) => (dock = v),
  tabs: (v) => (tabs = v),
  active: (v) => (active = v),
  loaded: (v) => (loaded = v),
  restoring: (v) => (restoring = v),
  lastFava: (v) => (lastFava = v),
};
