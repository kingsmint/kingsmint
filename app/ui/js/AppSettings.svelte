<!-- The app's settings, on this computer: the agent of new tabs and the terminals' font size; a check for a newer
     version; and the kingsmint extension in the Claude app, when that app is on this computer. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { installClaude, saveApp } from "./settings.js";
  import { invoke } from "./util.js";

  const agents = $derived([...app.installed, ""]);
  const agent = $derived(app.appSettings.agent ?? app.installed[0] ?? "");
</script>

<form class="inbox-page wa-stack wa-gap-m" id="settings-app" onsubmit={(e) => e.preventDefault()}>
  <header>
    <h2>{t("app")}</h2>
    <p class="muted">{t("appNote")}</p>
  </header>
  <div class="wa-grid fields">
    <wa-select label={t("newTabs")} value={agent} onchange={(e) => saveApp({ agent: e.target.value })}>
      {#if agent && !agents.includes(agent)}<wa-option value={agent}>{agent}</wa-option>{/if}
      {#each agents as a (a)}<wa-option value={a}>{a || t("shell")}</wa-option>{/each}
    </wa-select>
    <wa-input
      type="number"
      min="10"
      max="20"
      label={t("fontSize")}
      value={app.appSettings.fontSize ?? 13}
      onchange={(e) => saveApp({ fontSize: Math.min(20, Math.max(10, +e.target.value || 13)) })}
    ></wa-input>
  </div>
  <div>
    <wa-button size="small" appearance="filled" onclick={() => invoke("check_updates")}
      ><wa-icon slot="start" name="refresh-cw"></wa-icon>{t("checkUpdates")}</wa-button
    >
  </div>
  {#if app.claude}
    <header>
      <h2>{t("claude")}</h2>
      <p class="muted">{t("claudeNote")}</p>
    </header>
    <p>{t({ missing: "claudeMissing", old: "claudeOld", current: "claudeCurrent" }[app.claude])}</p>
    <div>
      <wa-button size="small" appearance="filled" onclick={installClaude}
        >{t({ missing: "claudeAdd", old: "claudeUpdate", current: "claudeAgain" }[app.claude])}</wa-button
      >
    </div>
  {/if}
</form>
