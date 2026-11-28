<!-- The app's settings, on this computer: the agent (a profile) of new tabs and tasks, and the one of the open ledger;
     the agents' profiles; the terminals' font size; the theme and dark mode; a check for a newer version; and the
     kingsmint extension in the Claude app, when that app is on this computer. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { APP_THEMES, installClaude, modeName, saveApp, themeName } from "./settings.js";
  import { AGENTS, installAgent, profiles } from "./terminal.js";
  import { invoke } from "./util.js";

  const all = $derived(profiles());
  const agent = $derived(app.appSettings.agent ?? app.installed[0] ?? "");
  // Web Awesome's default theme on a card: its palette and colors, not the ones <html> has from an app's theme
  const DEFAULT = "wa-palette-default wa-brand-blue wa-neutral-gray wa-success-green wa-warning-yellow wa-danger-red";
  const own = $derived(app.appSettings.profiles ?? []);
  const ledgers = $derived(app.appSettings.ledgerProfiles ?? {});
  const FOLLOW = "-"; // the ledger takes the app's
  // the variable that gives an agent its own folder (CONFIG_VARS in main.rs); Cursor's agent has none
  const VARS = { claude: "CLAUDE_CONFIG_DIR", codex: "CODEX_HOME", pi: "PI_CODING_AGENT_DIR" };

  const label = (id) => (id === "" ? t("shell") : (all.find((p) => p.id === id)?.name ?? id));
  function setLedger(value) {
    const { [app.current]: _, ...rest } = ledgers;
    saveApp({ ledgerProfiles: value === FOLLOW ? rest : { ...rest, [app.current]: value } });
  }
  const change = (id, field, value) =>
    saveApp({ profiles: own.map((p) => (p.id === id ? { ...p, [field]: value.trim() } : p)) });
  function add() {
    const type = app.installed[0] ?? "claude";
    const id = `p-${crypto.randomUUID().slice(0, 8)}`; // never an agent's name, which the found ones have
    saveApp({ profiles: [...own, { id, name: `${AGENTS[type]} 2`, agent: type, path: "", config: "" }] });
  }
  const remove = (id) => saveApp({ profiles: own.filter((p) => p.id !== id) });
</script>

{#snippet version(p)}
  {#await invoke("agent_version", { agent: p.agent, path: p.path || null })}
    <span class="muted">…</span>
  {:then v}
    <span class="mono">{v.path}</span> <span class="muted">{v.version}</span>
  {:catch e}
    <span class="error">{e}</span>
  {/await}
{/snippet}

<form class="inbox-page wa-stack wa-gap-m" id="settings-app" onsubmit={(e) => e.preventDefault()}>
  <header>
    <h2>{t("app")}</h2>
    <p class="muted">{t("appNote")}</p>
  </header>
  <div class="wa-grid fields">
    <wa-select label={t("newTabs")} hint={t("newTabsNote")} value={agent} onchange={(e) => saveApp({ agent: e.target.value })}>
      {#if agent && !all.some((p) => p.id === agent)}<wa-option value={agent}>{agent}</wa-option>{/if}
      {#each [...all.map((p) => p.id), ""] as id (id)}<wa-option value={id}>{label(id)}</wa-option>{/each}
    </wa-select>
    {#if app.current}
      <wa-select
        label={t("ledgerAgent")}
        hint={t("ledgerAgentNote")}
        value={ledgers[app.current] ?? FOLLOW}
        onchange={(e) => setLedger(e.target.value)}
      >
        <wa-option value={FOLLOW}>{t("ledgerAgentApp", { agent: label(agent) })}</wa-option>
        {#each [...all.map((p) => p.id), ""] as id (id)}<wa-option value={id}>{label(id)}</wa-option>{/each}
      </wa-select>
    {/if}
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

  <header>
    <h2>{t("profiles")}</h2>
    <p class="muted">{t("profilesNote")}</p>
  </header>
  {#each app.installed as a (a)}
    <p class="note"><strong>{AGENTS[a] ?? a}</strong> · {@render version({ agent: a })}</p>
  {/each}
  {#each own as p (p.id)}
    <div class="wa-stack wa-gap-xs">
      <div class="wa-grid fields">
        <wa-input label={t("profileName")} value={p.name} onchange={(e) => change(p.id, "name", e.target.value)}></wa-input>
        <wa-select label={t("agent")} value={p.agent} onchange={(e) => change(p.id, "agent", e.target.value)}>
          {#each Object.entries(AGENTS) as [key, name] (key)}<wa-option value={key}>{name}</wa-option>{/each}
        </wa-select>
        <wa-input
          label={t("profilePath")}
          placeholder={p.agent}
          hint={t("profilePathNote")}
          value={p.path ?? ""}
          onchange={(e) => change(p.id, "path", e.target.value)}
        ></wa-input>
        <wa-input
          label={t("profileConfig")}
          placeholder={VARS[p.agent] ? "~/.claude-private" : ""}
          hint={VARS[p.agent] ? t("profileConfigNote", { variable: VARS[p.agent] }) : t("profileConfigNone")}
          disabled={!VARS[p.agent]}
          value={p.config ?? ""}
          onchange={(e) => change(p.id, "config", e.target.value)}
        ></wa-input>
      </div>
      <p class="note">{@render version(p)}</p>
      <div>
        <wa-button size="small" appearance="plain" onclick={() => remove(p.id)}
          ><wa-icon slot="start" name="trash-2"></wa-icon>{t("profileRemove")}</wa-button
        >
      </div>
    </div>
  {/each}
  <div class="wa-cluster wa-gap-xs">
    <wa-button size="small" appearance="filled" onclick={add}
      ><wa-icon slot="start" name="plus"></wa-icon>{t("profileAdd")}</wa-button
    >
    {#each Object.keys(AGENTS).filter((a) => !app.installed.includes(a)) as a (a)}
      <wa-button size="small" appearance="outlined" onclick={() => installAgent(a)}
        >{t("installAgent", { agent: AGENTS[a] })}</wa-button
      >
    {/each}
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
