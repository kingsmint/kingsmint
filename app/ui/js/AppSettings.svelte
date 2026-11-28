<!-- The app's settings, on this computer: the agent of new tabs, the terminals' font size, the theme and dark mode; a check for a newer
     version; and the kingsmint extension in the Claude app, when that app is on this computer. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { APP_THEMES, installClaude, modeName, saveApp, themeName } from "./settings.js";
  import { invoke } from "./util.js";

  const agents = $derived([...app.installed, ""]);
  const agent = $derived(app.appSettings.agent ?? app.installed[0] ?? "");
  // Web Awesome's default theme on a card: its palette and colors, not the ones <html> has from an app's theme
  const DEFAULT = "wa-palette-default wa-brand-blue wa-neutral-gray wa-success-green wa-warning-yellow wa-danger-red";
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
  <header>
    <h2>{t("theme")}</h2>
  </header>
  <wa-radio-group
    label={t("mode")}
    orientation="horizontal"
    value={modeName()}
    onchange={(e) => saveApp({ mode: e.target.value })}
  >
    {#each ["system", "light", "dark"] as m (m)}<wa-radio appearance="button" value={m}>{t(`mode-${m}`)}</wa-radio>{/each}
  </wa-radio-group>
  <!-- a card per theme, with its light and its dark variant in their colors: a radio, so arrows move between them.
       The chosen card offers the theme's dark variants. -->
  <div class="themes wa-grid" role="radiogroup" aria-label={t("theme")}>
    {#each APP_THEMES as [name, variants] (name)}
      {@const chosen = variants.some(([v]) => v === themeName())}
      {@const id = chosen ? themeName() : variants[0][0]}
      <label class="theme">
        <input
          type="radio"
          name="theme"
          class="wa-visually-hidden"
          checked={chosen}
          onchange={() => saveApp({ theme: id })}
        />
        <wa-card>
          <strong>{name}</strong>
          <span class="variants" aria-hidden="true">
            {#each ["wa-light", "wa-dark"] as mode (mode)}
              <span class="variant {mode} {id === 'default' ? DEFAULT : `km-theme km-${id}`}">
                <span class="swatches">
                  {#each ["brand", "success", "warning", "danger"] as v (v)}<i
                      style:background="var(--wa-color-{v}-fill-loud)"
                    ></i>{/each}
                </span>
                <span class="sample">
                  <span>{t("themeSample")}</span>
                  <span class="neg">−12,40</span>
                </span>
              </span>
            {/each}
          </span>
          {#if chosen && variants.length > 1}
            <wa-radio-group
              size="s"
              orientation="horizontal"
              label={t("darkVariant")}
              value={id}
              onchange={(e) => saveApp({ theme: e.target.value })}
            >
              {#each variants as [v, label] (v)}<wa-radio appearance="button" value={v}>{label}</wa-radio>{/each}
            </wa-radio-group>
          {/if}
        </wa-card>
      </label>
    {/each}
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
