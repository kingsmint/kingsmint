// The app's theme and dark mode, on the app's page and in Fava (the server adds this script to Fava's pages).
// Dark mode: the app's setting (km_mode: "system", "light" or "dark"), with "system" the system's; Web Awesome's
// class, and Fava's own switch for its colors that fava.css does not map. Theme: km_theme, one of themes.css or
// "default" (Web Awesome's). The app's page sends both to Fava's frames (settings.js applyTheme, fava.js), and each
// page keeps them for the next, which so takes them before it draws.
// km_dark: `matches` and a "change" event, for the app's modules (util.js dark).
const km_scheme = matchMedia("(prefers-color-scheme: dark)");
const km_dark = new EventTarget();
window.km_dark = km_dark; // a const of a classic script is no property of window
km_dark.matches = false;
const km_saved = (key, fallback) => {
  try {
    return localStorage[key] || fallback;
  } catch {
    return fallback;
  }
};
let km_mode = km_saved("km_mode", "system");
const km_applyScheme = () => {
  const on = km_mode === "dark" || (km_mode !== "light" && km_scheme.matches);
  document.documentElement.classList.toggle("wa-dark", on);
  document.documentElement.dataset.colorScheme = on ? "dark" : "light";
  if (on !== km_dark.matches) {
    km_dark.matches = on;
    km_dark.dispatchEvent(new Event("change"));
  }
};
const km_applyTheme = (name) => {
  const html = document.documentElement;
  html.classList.remove(...[...html.classList].filter((c) => c.startsWith("km-")));
  if (name && name !== "default") html.classList.add("km-theme", `km-${name}`);
};
// a change of the app's settings (settings.js applyTheme): kept for the next page
const km_set = ({ theme, mode }) => {
  try {
    localStorage.km_theme = theme;
    localStorage.km_mode = mode;
  } catch {}
  km_mode = mode;
  km_applyTheme(theme);
  km_applyScheme();
};
window.km_set = km_set;
km_applyTheme(km_saved("km_theme", "default"));
km_applyScheme();
km_scheme.addEventListener("change", km_applyScheme);
addEventListener("message", (e) => {
  if (e.source !== parent || parent === window || !e.data?.kingsmint || !("theme" in e.data)) return;
  km_set(e.data);
});
