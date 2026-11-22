<!-- The right side of a group's header, as in Herdr: + always; split, maximize and close while the mouse is over the
     group. A split is one more of the active panel beside it or below it: Fava on the same page, the overview on the
     same view, a terminal with the same agent (a terminal's program runs once, so its content cannot show twice). The
     inbox and the settings do not split. -->
<script>
  import { app } from "./app.svelte.js";
  import { addFava, favaUrl } from "./fava.js";
  import { t } from "./i18n.js";
  import { addOverview, maximize } from "./panels.js";
  import { favas, overviews, tabs } from "./state.js";
  import { newTab } from "./terminal.js";

  let { group } = $props();
  let splittable = $state(false); // the active panel is Fava, an overview or a terminal
  let maximized = $state(false);

  $effect(() => {
    const enter = () => {
      const id = group.activePanel?.id;
      splittable = favas.has(id) || overviews.has(id) || tabs.some((x) => x.api.id === id);
      maximized = group.api.isMaximized();
    };
    group.element.addEventListener("mouseenter", enter);
    return () => group.element.removeEventListener("mouseenter", enter);
  });

  function split(direction) {
    const id = group.activePanel?.id,
      tab = tabs.find((x) => x.api.id === id);
    if (favas.has(id)) addFava({ group, direction, url: favaUrl(favas.get(id)) });
    else if (overviews.has(id)) addOverview({ group, direction, params: overviews.get(id)() });
    else if (tab) newTab(tab.agent, group, direction);
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
      <svg viewBox="0 0 16 16"><rect x="2.5" y="3.5" width="11" height="9" rx="1" /><path d="M8 3.5v9" /></svg>
    </button>
    <button class="hover" title={t("splitDown")} onpointerdown={own(() => {})} onclick={own(() => split("below"))}>
      <svg viewBox="0 0 16 16"><rect x="2.5" y="3.5" width="11" height="9" rx="1" /><path d="M2.5 8h11" /></svg>
    </button>
  {/if}
  <button
    class="hover"
    title={t(maximized ? "restore" : "maximize")}
    onpointerdown={own(() => {})}
    onclick={own(() => maximize(group.api))}
  >
    <svg viewBox="0 0 16 16"><path d="M9.5 2.5h4v4M6.5 13.5h-4v-4M13.5 2.5L9 7M2.5 13.5L7 9" /></svg>
  </button>
  <button class="hover" title={t("closeGroup")} onpointerdown={own(() => {})} onclick={own(() => setTimeout(() => group.api.close()))}>
    <svg viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" /></svg>
  </button>
  <button class="add" title={t("newTab")} onpointerdown={own(() => {})} onclick={own(menu)}>+</button>
</div>
