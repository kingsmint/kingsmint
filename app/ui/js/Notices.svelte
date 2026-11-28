<!-- What needs the user, above the panels: problems in the ledger (with the button that asks the agent to fix them)
     and an agent's question; and the sign while files are dragged over the window. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { installClaude, saveApp } from "./settings.js";
  import { ask } from "./tasks.js";
  import { installAgent, profiles } from "./terminal.js";

  let fixing = $state(false); // for 3 s after a click: one task per click
  async function fix(act = "fix") {
    fixing = true;
    try {
      await ask(act);
    } finally {
      setTimeout(() => (fixing = false), 3000);
    }
  }
</script>

{#if app.check}
  <p id="check" class="banner" title={app.check}>
    <span>{t("problems")}</span>
    <button type="button" disabled={fixing} onclick={fix}><wa-icon class="agent-icon" name="sparkles"></wa-icon> {t("fix")}</button>
  </p>
{/if}
{#if app.upgrade}
  <p id="upgrade" class="banner">
    <span>{t("upgradeLedger")}</span>
    <button type="button" disabled={fixing} onclick={() => fix("upgrade")}
      ><wa-icon class="agent-icon" name="sparkles"></wa-icon> {t("upgradeAsk")}</button
    >
  </p>
{/if}
{#if !profiles().length}
  <p id="no-agent" class="banner">
    <span>{t("noAgent")}</span>
    <button type="button" onclick={() => installAgent("claude")}>{t("installClaude")}</button>
    <button type="button" onclick={() => installAgent("codex")}>{t("installCodex")}</button>
  </p>
{/if}
<!-- the Claude app without the extension (until "Not now"), or with an older one -->
{#if app.current && (app.claude === "old" || (app.claude === "missing" && !app.appSettings.claudeNotNow))}
  <p id="claude-extension" class="banner">
    <span>{t(app.claude === "old" ? "claudeOld" : "claudeMissing")}</span>
    <button type="button" onclick={installClaude}>{t(app.claude === "old" ? "claudeUpdate" : "claudeAdd")}</button>
    {#if app.claude === "missing"}
      <button type="button" onclick={() => saveApp({ claudeNotNow: true })}>{t("notNow")}</button>
    {/if}
  </p>
{/if}
{#if app.agentNote}<p id="agent-note" class="banner">{app.agentNote}</p>{/if}
{#if app.dropping}
  <div id="dropping"><p>{t("dropping")}</p></div>
{/if}
