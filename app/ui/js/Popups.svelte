<!-- The menus that open at the mouse: a tab's menu (right-click on a tab) and the "+" of a group's header. A click
     elsewhere or Escape closes them (initPanels). -->
<script>
  import { app } from "./app.svelte.js";
  import { addFava } from "./fava.js";
  import { t } from "./i18n.js";
  import { tabAction } from "./panels.js";
  import { newTab } from "./terminal.js";

  const p = $derived(app.popup);
  const close = () => (app.popup = null);
</script>

{#if p?.kind === "tab"}
  <div id="tab-menu" class="popup" style:left="{Math.min(p.x, innerWidth - 190)}px" style:top="{p.y + 2}px">
    {#if p.isTerm}<button type="button" onclick={() => tabAction(p.api, "rename")}>{t("rename")}</button>{/if}
    {#if p.isTerm || p.isFava}<button type="button" onclick={() => tabAction(p.api, "clone")}>{t("clone")}</button>{/if}
    {#if p.isTerm}<button type="button" onclick={() => tabAction(p.api, "restart")}>{t("restart")}</button>{/if}
    <button type="button" onclick={() => tabAction(p.api, "maximize")}
      >{t(p.api.isMaximized() ? "restore" : "maximize")}</button
    >
    <hr />
    <button type="button" onclick={() => tabAction(p.api, "close")}>{t("close")}</button>
    {#if p.isTerm}
      <button type="button" disabled={p.terminals < 2} onclick={() => tabAction(p.api, "others")}>{t("closeOthers")}</button>
    {/if}
  </div>
{:else if p?.kind === "add"}
  <!-- the buttons can be at the window's right edge -->
  <div id="add-menu" class="popup" style:left="{Math.min(p.x, innerWidth - 160)}px" style:top="{p.y}px">
    {#each [...app.installed, ""] as agent (agent)}
      <button
        type="button"
        onclick={() => {
          close();
          newTab(agent, p.group);
        }}>{agent || "shell"}</button
      >
    {/each}
    <button
      type="button"
      onclick={() => {
        close();
        addFava({ group: p.group });
      }}>Fava</button
    >
  </div>
{/if}
