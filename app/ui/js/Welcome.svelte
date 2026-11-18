<!-- The start screen, while no ledger is open: the ledgers opened before, open a folder, the sample, a new ledger. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import LedgerItem from "./LedgerItem.svelte";
  import { create, openDir, openPicked, sample } from "./ledger.js";
  import { APP_LANGUAGES, setLang } from "./settings.js";

  let title = $state("");
  let chosen = $state(null);
  const language = $derived(chosen ?? app.lang); // the new ledger's: the app's language until one is chosen
</script>

<form
  class="wa-stack wa-gap-l"
  onsubmit={(e) => {
    e.preventDefault();
    create(title ?? "", language);
  }}
>
  <header class="wa-split wa-align-items-start">
    <div>
      <h1>Kingsmint</h1>
      <p class="lead">{t("lead")}</p>
    </div>
    <wa-select size="small" value={app.lang} onchange={(e) => setLang(e.target.value)}>
      {#each APP_LANGUAGES as [code, label] (code)}<wa-option value={code}>{label}</wa-option>{/each}
    </wa-select>
  </header>

  {#if app.recent.length}
    <wa-card>
      <div class="wa-stack wa-gap-2xs" id="recent-list">
        <h2>{t("recentLedgers")}</h2>
        {#each app.recent as dir (dir)}<LedgerItem {dir} onclick={() => openDir(dir)} />{/each}
      </div>
    </wa-card>
  {/if}

  <div class="wa-grid wa-gap-m choices">
    <wa-card>
      <div class="wa-stack wa-gap-s">
        <h2>{t("openALedger")}</h2>
        <p>{@html t("openALedgerText")}</p>
        <div><wa-button size="small" variant="brand" onclick={openPicked}>{t("chooseFolder")}</wa-button></div>
      </div>
    </wa-card>
    <wa-card>
      <div class="wa-stack wa-gap-s">
        <h2>{t("sampleHead")}</h2>
        <p>{t("sampleText")}</p>
        <div><wa-button size="small" onclick={sample}>{t("trySample")}</wa-button></div>
      </div>
    </wa-card>
  </div>

  <wa-card>
    <div class="wa-stack wa-gap-s">
      <h2>{t("newLedgerHead")}</h2>
      <p>{t("newLedgerText")}</p>
      <div class="wa-flank:end wa-gap-xs">
        <wa-input
          size="small"
          placeholder={t("ownerName")}
          autocomplete="off"
          value={title}
          oninput={(e) => (title = e.target.value)}
        ></wa-input>
        <wa-select size="small" value={language} onchange={(e) => (chosen = e.target.value)}>
          {#each APP_LANGUAGES as [code, label] (code)}<wa-option value={code}>{label}</wa-option>{/each}
        </wa-select>
      </div>
      <div><wa-button type="submit" size="small" variant="brand">{t("chooseEmpty")}</wa-button></div>
    </div>
  </wa-card>
  <p id="error">{app.welcomeError}</p>
</form>
