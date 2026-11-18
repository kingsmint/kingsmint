<!-- Over the panels: the start screen while no ledger is open, and the wait for a ledger's server, with what uv
     downloads (the first start installs Python and the ledger's packages) or why it failed. -->
<script>
  import { app } from "./app.svelte.js";
  import Welcome from "./Welcome.svelte";
</script>

{#if app.cover}
  <section id="cover">
    {#if app.cover === "welcome"}
      <div id="welcome"><Welcome /></div>
    {:else}
      <div id="status" class="wa-stack wa-gap-m" class:failed={app.status.failed}>
        <wa-spinner></wa-spinner>
        <p id="message">{app.status.message}</p>
        {#if app.status.log.length}<pre id="setup-log">{app.status.log.join("\n")}</pre>{/if}
      </div>
    {/if}
  </section>
{/if}
