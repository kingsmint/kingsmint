<!-- The app's settings, on this computer: the agent of new tabs and the terminals' font size. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { saveApp } from "./settings.js";

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
</form>
