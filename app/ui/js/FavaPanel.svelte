<!-- The content of a Fava panel: an iframe on Fava's page in params.url, from the ledger's server. -->
<script>
  import { untrack } from "svelte";
  import { app } from "./app.svelte.js";
  import { forget } from "./fava.js";
  import { favas } from "./state.js";
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

<div class="fava-pane"><iframe bind:this={frame} title="Fava"></iframe></div>
