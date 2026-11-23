<!-- The right side of a group's header, as in Herdr: + always; split, maximize and close while the mouse is over the
     group. A split is one more of the active panel beside it or below it: Fava on the same page, the overview on the
     same view. The inbox and the settings do not split; the terminals are in the agent's sidebar (SideActions.svelte). -->
<script>
  import { app } from "./app.svelte.js";
  import { addFava, favaUrl } from "./fava.js";
  import { t } from "./i18n.js";
  import { addOverview, maximize } from "./panels.js";
  import { favas, overviews } from "./state.js";

  let { group } = $props();
  let splittable = $state(false); // the active panel is Fava or an overview
  let maximized = $state(false);

  $effect(() => {
    const enter = () => {
      const id = group.activePanel?.id;
      splittable = favas.has(id) || overviews.has(id);
      maximized = group.api.isMaximized();
    };
    group.element.addEventListener("mouseenter", enter);
    return () => group.element.removeEventListener("mouseenter", enter);
  });

  function split(direction) {
    const id = group.activePanel?.id;
    if (favas.has(id)) addFava({ group, direction, url: favaUrl(favas.get(id)) });
    else if (overviews.has(id)) addOverview({ group, direction, params: overviews.get(id)() });
  }

  function menu(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const open = app.popup?.kind === "add" && app.popup.group === group;
    app.popup = open ? null : { kind: "add", group, x: r.left, y: r.bottom + 4 };
  }

  // a press on these buttons is not a drag of the group, and a click stays here (it would close the menus)
  const own = (run) => (e) => {
    e.stopPropagation();
    run(e);
  };
</script>

<div class="group-actions">
  {#if splittable}
    <button class="hover" title={t("splitRight")} onpointerdown={own(() => {})} onclick={own(() => split("right"))}>
      <wa-icon name="columns-2"></wa-icon>
    </button>
    <button class="hover" title={t("splitDown")} onpointerdown={own(() => {})} onclick={own(() => split("below"))}>
      <wa-icon name="rows-2"></wa-icon>
    </button>
  {/if}
  <button
    class="hover"
    title={t(maximized ? "restore" : "maximize")}
    onpointerdown={own(() => {})}
    onclick={own(() => maximize(group.api))}
  >
    <wa-icon name={maximized ? "minimize-2" : "maximize-2"}></wa-icon>
  </button>
  <button class="hover" title={t("closeGroup")} onpointerdown={own(() => {})} onclick={own(() => setTimeout(() => group.api.close()))}>
    <wa-icon name="x"></wa-icon>
  </button>
  <button class="add" title={t("newTab")} onpointerdown={own(() => {})} onclick={own(menu)}><wa-icon name="plus"></wa-icon></button>
</div>
