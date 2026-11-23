<!-- The ledger menu under the rail's badge, like the project menu of JetBrains IDEs: open a folder, a new ledger, the
     sample, the open ledger and the ones opened before. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import LedgerItem from "./LedgerItem.svelte";
  import { closeMenu, create, openDir, openPicked, sample } from "./ledger.js";
  import { APP_LANGUAGES } from "./settings.js";

  let asking = $state(false); // the form for a new ledger shows
  let title = $state("");
  let chosen = $state(null);
  const language = $derived(chosen ?? app.lang); // the new ledger's: the app's language until one is chosen
  const recent = $derived(app.recent.filter((d) => d !== app.current));
</script>

{#if app.menuOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div id="menu" onclick={(e) => e.stopPropagation()}>
    <button
      type="button"
      class="item"
      onclick={() => {
        closeMenu();
        openPicked();
      }}
    >
      <svg viewBox="0 0 24 24">
        <path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2h9A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" />
      </svg>
      <span>{t("open")}</span>
    </button>
    <button type="button" class="item" onclick={() => (asking = true)}>
      <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
      <span>{t("newLedger")}</span>
    </button>
    <button type="button" class="item" onclick={sample}>
      <svg viewBox="0 0 24 24"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" /></svg>
      <span>{t("trySample")}</span>
    </button>
    {#if asking}
      <form
        onsubmit={(e) => {
          e.preventDefault();
          create(title, language);
        }}
      >
        <!-- svelte-ignore a11y_autofocus -->
        <input placeholder={t("ownerName")} autocomplete="off" bind:value={title} autofocus />
        <select class="lang" value={language} onchange={(e) => (chosen = e.target.value)}>
          {#each APP_LANGUAGES as [code, label] (code)}<option value={code}>{label}</option>{/each}
        </select>
        <button type="submit">{t("chooseEmpty")}</button>
      </form>
    {/if}
    <p class="error">{app.menuError}</p>
    {#if app.current}
      <div>
        <hr />
        <h3>{t("openLedger")}</h3>
        <LedgerItem dir={app.current} onclick={closeMenu} />
      </div>
    {/if}
    {#if recent.length}
      <div>
        <hr />
        <h3>{t("recentLedgers")}</h3>
        {#each recent as dir (dir)}<LedgerItem {dir} onclick={() => openDir(dir)} />{/each}
      </div>
    {/if}
  </div>
{/if}
