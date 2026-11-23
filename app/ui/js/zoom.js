// Zoom of the content (Fava, terminal, inbox, settings), like a browser's, with Chrome's steps; remembered in the
// app's settings. The rail stays: macOS keeps the window buttons where they are, so a zoomed rail would leave them
// beside its middle.
import { app } from "./app.svelte.js";
import { assign, favas, tabs } from "./state.js";
import { fitTab } from "./terminal.js";
import { invoke } from "./util.js";

export const ZOOMS = [0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
export const fontSize = () => Math.round((app.appSettings.fontSize ?? 13) * (app.appSettings.zoom ?? 1));
export function applyZoom() {
  const z = app.appSettings.zoom ?? 1;
  document.documentElement.style.setProperty("--zoom", z);
  favas.forEach(zoomFrame);
  tabs.forEach((t) => (t.term.options.fontSize = fontSize()));
  setTimeout(() => tabs.forEach(fitTab), 50); // the terminal fits its new size
}
// Fava's frame is scaled from outside: it lays out a viewport of the pane's size / z, so it always fills the pane
export function zoomFrame(frame) {
  const z = app.appSettings.zoom ?? 1;
  Object.assign(frame.style, {
    width: `${100 / z}%`,
    height: `${100 / z}%`,
    transform: `scale(${z})`,
    transformOrigin: "0 0",
  });
}
export function zoom(step) {
  const now = app.appSettings.zoom ?? 1;
  const i = ZOOMS.findIndex((z) => z >= now - 0.001);
  const next = step === 0 ? 1 : ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? ZOOMS.length - 1 : i) + step))];
  assign({ appSettings: { ...app.appSettings, zoom: next } });
  invoke("save_app_settings", { settings: app.appSettings });
  applyZoom();
}
