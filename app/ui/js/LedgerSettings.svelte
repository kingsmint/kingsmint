<!-- The ledger's settings, in its files: owner, currency, number format, language, and the accounts of its
     statements. Saving writes the files (and a version); a change of the accounts goes to the agent as one message.
     It loads again on km-settings (loadSettings in settings.js). -->
<script>
  import AgentIcon from "./AgentIcon.svelte";
  import { t, tAgent } from "./i18n.js";
  import { app } from "./app.svelte.js";
  import { tell } from "./tasks.js";
  import { rpc } from "./util.js";

  let data = $state(null); // { settings, locales, accounts }
  let note = $state("");
  let error = $state("");
  const short = (n) => (n.length > 12 ? `${n.slice(0, 4)} ${n.slice(4, 8)} … ${n.slice(-4)}` : n);

  async function load() {
    data = await rpc("settings", { lang: app.lang }).catch((e) => ((error = String(e)), data));
  }

  async function save(e) {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.target));
    const before = data.settings.language;
    note = error = "";
    try {
      const r = await rpc("save_settings", { title: form.title ?? "", locale: form.locale ?? "", language: form.language ?? "" });
      error = r.error;
      if (r.changed) note = r.changed.length ? t("saved", { what: r.changed.join(", ") }) : t("nothingChanged");
    } catch (err) {
      return (error = String(err));
    }
    await load();
    // Fava picks its language when it draws a page; settings.js reloads it and follows with the app
    if (form.language && form.language !== before)
      document.body.dispatchEvent(new CustomEvent("km-ledger-language", { detail: { value: form.language } }));
  }

  async function askAgent(e) {
    e.preventDefault();
    const input = e.target.querySelector("wa-input");
    const text = (input.value ?? "").trim(); // an empty field has null
    if (!text) return input.focus();
    input.value = "";
    await tell(tAgent("accounts", { text }) + tAgent("save"), "", tAgent("beforeAccounts"));
  }

  $effect(() => {
    document.addEventListener("km-settings", load);
    return () => {
      document.removeEventListener("km-settings", load);
    };
  });
</script>

{#if data}
  {@const s = data.settings}
  <form class="inbox-page wa-stack wa-gap-l" onsubmit={save}>
    <h1>{t("settings")}</h1>

    <section class="wa-stack wa-gap-m">
      <header>
        <h2>{t("ledger")}</h2>
        <p class="muted">{t("ledgerNote")}</p>
      </header>
      <div class="wa-grid fields">
        <wa-input name="title" label={t("owner")} hint={t("ownerNote")} value={s.title} autocomplete="off"></wa-input>
        <wa-input label={t("currency")} hint={t("currencyNote")} value={s.currency} disabled></wa-input>
        <wa-select name="locale" label={t("numberFormat")} value={s.locale}>
          {#each data.locales as [code, label] (code)}<wa-option value={code}>{label}</wa-option>{/each}
        </wa-select>
        <wa-select name="language" label={t("language")} hint={t("languageNote")} value={s.language}>
          <wa-option value="en">English</wa-option>
          <wa-option value="sk">Slovenčina</wa-option>
        </wa-select>
      </div>
      <div class="wa-cluster wa-gap-s">
        <wa-button type="submit" variant="brand">{t("save")}</wa-button>
        {#if note}<span class="note">{note}</span>{/if}
      </div>
      {#if error}<p class="error">{error}</p>{/if}
    </section>
  </form>

  <div class="inbox-page wa-stack wa-gap-s">
    <h2>{t("accounts")}</h2>
    {#each data.accounts as a (a.account + a.number)}
      {@const n = a.number.replaceAll(" ", "")}
      <div class="row wa-split">
        <span class="mono">{a.account}</span>
        <span class="mono" title={n}>{short(n)}</span>
        <span>{a.currency}</span>
        <span class="muted">{a.note}</span>
      </div>
    {:else}
      <p class="muted">{t("noAccounts")}</p>
    {/each}

    <form class="wa-flank:end wa-gap-s" onsubmit={askAgent}>
      <wa-input name="text" placeholder={t("accountsAsk")} autocomplete="off"></wa-input>
      <wa-button type="submit" variant="brand"><AgentIcon slot="start" />{t("askAgent")}</wa-button>
    </form>
  </div>
{:else if error}
  <p class="error inbox-page">{error}</p>
{/if}
