// Added to Fava's pages by the ledger's server (themed() in server/server.py). The app's page does not reach into
// Fava's frame, so this script tells it by postMessage what happens there, and the page acts (js/fava.js):
// drag:  a press on the empty part of Fava's header, which moves the window; zoom: a double click there
// key:   one of the app's shortcuts while Fava has the focus
// open:  ⌘-click on a link (a split beside this view), middle click (a tab behind it)
// url:   Fava's current page, saved with the layout
// Back and forward stay in this frame: the mouse's side buttons, and the arrows before Fava's title.
(() => {
  if (parent === window) return;
  const send = (m) => parent.postMessage({ kingsmint: true, ...m }, "*"); // the page checks this frame and its origin
  const bare = (e) =>
    e.target.closest("header") &&
    !e.target.closest("a, button, input, select, textarea, label, [role=button], [tabindex]");
  addEventListener("mousedown", (e) => {
    if (e.button === 0 && e.detail === 1 && bare(e)) {
      e.preventDefault();
      send({ type: "drag" });
    }
  });
  addEventListener("dblclick", (e) => bare(e) && send({ type: "zoom" }));

  // the keys of shortcut() in js/shortcuts.js, with ⌘
  const KEYS = new Set(["+", "=", "-", "0", "1", "2", "3", "j"]);
  const CODES = new Set(["Equal", "Minus", "Digit0", "KeyT", "BracketLeft", "BracketRight"]);
  addEventListener(
    "keydown",
    (e) => {
      if (!e.metaKey || !(KEYS.has(e.key) || CODES.has(e.code))) return;
      e.preventDefault();
      send({ type: "key", key: e.key, code: e.code, metaKey: true, shiftKey: e.shiftKey });
    },
    true,
  );

  addEventListener("mouseup", (e) => {
    if (e.button === 3) history.back();
    if (e.button === 4) history.forward();
  });
  // the arrows, in Fava's header, which Svelte draws after load (and may draw again)
  const arrows = () => {
    const h1 = document.querySelector("body > header > h1");
    if (!h1 || document.getElementById("km-nav")) return;
    const nav = document.createElement("span");
    nav.id = "km-nav";
    nav.innerHTML =
      "<style>#km-nav{display:inline-flex;gap:2px;margin-left:6px}#km-nav button{border:0;background:none;color:inherit;" +
      "font-size:18px;line-height:1;padding:4px 7px;border-radius:4px;cursor:pointer;opacity:.85}#km-nav button:hover{opacity:1;" +
      'background:rgba(255,255,255,.15)}</style><button type="button" title="Back (⌘[)">‹</button><button type="button" title="Forward (⌘])">›</button>';
    const [back, forward] = nav.querySelectorAll("button");
    back.onclick = () => history.back();
    forward.onclick = () => history.forward();
    h1.before(nav);
  };
  new MutationObserver(arrows).observe(document, { childList: true, subtree: true });

  const link = (e) => {
    const a = e.target.closest("a[href]");
    if (!a || !(e.metaKey || e.button === 1) || a.origin !== location.origin) return;
    e.preventDefault();
    e.stopPropagation(); // before Fava's router
    send({ type: "open", url: a.pathname + a.search, background: e.button === 1 });
  };
  addEventListener("click", link, true);
  addEventListener("auxclick", link, true);

  // Fava's router moves by pushState
  const where = () => send({ type: "url", url: location.pathname + location.search });
  for (const f of ["pushState", "replaceState"]) {
    const original = history[f];
    history[f] = function (...args) {
      const r = original.apply(this, args);
      where();
      return r;
    };
  }
  addEventListener("popstate", where);
  where();
})();
