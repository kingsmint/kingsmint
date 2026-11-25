<!-- The content of a Fava panel: an iframe on Fava's page in params.url, from the ledger's server. A page the
     overview opened (a statement, Edit in Fava) has a bar above it, the way back to the overview. -->
<script>
  import { untrack } from "svelte";
  import { app } from "./app.svelte.js";
  import { forget } from "./fava.js";
  import { t } from "./i18n.js";
  import { showPart } from "./panels.js";
  import { dock, favas } from "./state.js";
  import { zoomFrame } from "./zoom.js";

  let { api, params } = $props();
  let frame;

  // once: a change of the app's state (the zoom, the server) must not load the frame again
  $effect(() => {
    const id = api.id;
    untrack(() => {
      favas.set(id, frame);
      zoomFrame(frame);
      frame.src = new URL(params?.url || "/fava/", app.serverOrigin).href;
    });
    return () => forget(id, frame);
  });
</script>

{#snippet back(from)}
  <!-- the press is not dockview's (it would make this panel active again); the switch after the click is done -->
  <div class="fava-back">
    <button
      type="button"
      class="more"
      onpointerdown={(e) => e.preventDefault()}
      onclick={() =>
        setTimeout(() => {
          const panel = dock.getPanel(from);
          if (panel && from !== "dashboard") panel.api.setActive();
          else showPart("dashboard"); // the rail's overview, also when the split it came from is closed
          delete app.favaBack[api.id];
        })}><wa-icon name="arrow-left"></wa-icon> {t("backToOverview")}</button
    >
  </div>
{/snippet}

<div class="fava-pane">
  {#if app.favaBack[api.id]}{@render back(app.favaBack[api.id])}{/if}
  <iframe bind:this={frame} title="Fava"></iframe>
</div>
