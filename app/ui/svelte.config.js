// The Svelte compiler's options, for Vite and svelte-check. Web Awesome's elements (wa-button, ...) are interactive
// and handle the keyboard themselves; Svelte does not know them, so its two warnings for a click handler on a "static"
// element are dropped for them.
const A11Y_CLICK = new Set(["a11y_click_events_have_key_events", "a11y_no_static_element_interactions"]);

export default {
  compilerOptions: {
    warningFilter: (w) => !(A11Y_CLICK.has(w.code) && /<wa-/.test(w.frame ?? "")),
  },
};
