<!-- What needs the user, above the panels: problems in the ledger (with the button that asks the agent to fix them)
     and an agent's question; and the sign while files are dragged over the window. -->
<script>
  import AgentIcon from "./AgentIcon.svelte";
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { ask } from "./tasks.js";

  let fixing = $state(false); // for 3 s after a click: one task per click
  async function fix() {
    fixing = true;
    try {
      await ask("fix");
    } finally {
      setTimeout(() => (fixing = false), 3000);
    }
  }
</script>

{#if app.check}
  <p id="check" class="banner" title={app.check}>
    <span>{t("problems")}</span>
    <button type="button" disabled={fixing} onclick={fix}><AgentIcon /> {t("fix")}</button>
  </p>
{/if}
{#if app.agentNote}<p id="agent-note" class="banner">{app.agentNote}</p>{/if}
{#if app.dropping}
  <div id="dropping"><p>{t("dropping")}</p></div>
{/if}
