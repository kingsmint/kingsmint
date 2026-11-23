<!-- The tab of a panel: a dot for a terminal (pulsing while its program writes, steady when it wrote while hidden),
     the title, ×. A double click maximizes the panel's group and back; the right click opens the tab's menu. The
     title turns into a field while app.renaming is this panel (the menu's Rename). -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { maximize, tabMenu } from "./panels.js";
  import { tabs } from "./state.js";

  let { api, title: first } = $props();
  // after this click's handler: closing disposes this component, which must not happen inside its own handler
  const close = () => setTimeout(() => api.close());
  // svelte-ignore state_referenced_locally
  let title = $state(first); // then from onDidTitleChange
  let busy = $state(false);
  let unread = $state(false);
  let label = $state();
  const editing = $derived(app.renaming === api.id);

  $effect(() => {
    const off = api.onDidTitleChange((e) => (title = e.title));
    // the terminal of this tab, if it is one: its program wrote in the last 1.5 s, or while the tab was hidden
    const timer = setInterval(() => {
      const tab = tabs.find((x) => x.api.id === api.id);
      busy = !!tab && Date.now() - tab.last < 1500;
      unread = !!tab?.unread;
    }, 500);
    return () => {
      off.dispose();
      clearInterval(timer);
    };
  });

  $effect(() => {
    if (editing) label?.select();
  });

  function done(keep) {
    if (!editing) return;
    app.renaming = null;
    api.setTitle((keep && label.value.trim()) || title);
    tabs.find((x) => x.api.id === api.id)?.term.focus();
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="tab-btn"
  class:busy
  class:unread
  ondblclick={() => maximize(api)}
  onauxclick={(e) => e.button === 1 && close()}
  oncontextmenu={(e) => {
    e.preventDefault();
    e.stopPropagation();
    tabMenu(api, e.clientX, e.clientY);
  }}
>
  <i class="dot"></i>
  {#if editing}
    <input
      class="label"
      bind:this={label}
      value={title}
      onpointerdown={(e) => e.stopPropagation()}
      onkeydown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") done(true);
        if (e.key === "Escape") done(false);
      }}
      onblur={() => done(true)}
    />
  {:else}
    <span class="label">{title}</span>
  {/if}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <span
    class="close"
    title={t("tabClose")}
    onpointerdown={(e) => e.stopPropagation()}
    onclick={(e) => {
      e.stopPropagation();
      close();
    }}><wa-icon name="x"></wa-icon></span
  >
</div>
