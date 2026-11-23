<!-- The right side of the sidebar's tab bar: + (a new agent or shell), pin (pinned beside the panels or floating over
     them), widen over the panels, hide. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";

  let { group } = $props();
  const s = app.sidebar;

  function menu(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const open = app.popup?.kind === "add" && app.popup.side;
    app.popup = open ? null : { kind: "add", group, side: true, x: r.left, y: r.bottom + 4 };
  }
  // a press on these buttons is not a drag of the group, and a click stays here (it would close the menus)
  const own = (run) => (e) => {
    e.stopPropagation();
    run(e);
  };
</script>

<div class="group-actions side-actions">
  <button class="add" title={t("newTab")} onpointerdown={own(() => {})} onclick={own(menu)}><wa-icon name="plus"></wa-icon></button>
  <button
    class:on={s.pinned}
    title={t(s.pinned ? "sideUnpin" : "sidePin")}
    onpointerdown={own(() => {})}
    onclick={own(() => ((s.pinned = !s.pinned), (s.wide = false)))}
  >
    <wa-icon name={s.pinned ? "pin" : "pin-off"}></wa-icon>
  </button>
  <button title={t(s.wide ? "sideNarrow" : "sideWide")} onpointerdown={own(() => {})} onclick={own(() => (s.wide = !s.wide))}>
    <wa-icon name={s.wide ? "minimize-2" : "maximize-2"}></wa-icon>
  </button>
  <button title={t("sideHide")} onpointerdown={own(() => {})} onclick={own(() => ((s.open = false), (s.wide = false)))}>
    <wa-icon name="panel-right-close"></wa-icon>
  </button>
</div>
