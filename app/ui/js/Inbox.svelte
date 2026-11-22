<!-- The inbox: what `kingsmint scan` says of each statement in inbox/, and the imported periods with their gaps. Its
     buttons run the app's native dialogs, the Trash and tasks for the agent. It loads again on km-inbox
     (refreshInbox in inbox.js): when it shows, after files were added, and when the ledger's state changed. -->
<script>
  import AgentIcon from "./AgentIcon.svelte";
  import { t } from "./i18n.js";
  import { INBOX_ACTIONS, removeFile } from "./inbox.js";
  import { app } from "./app.svelte.js";
import { active, assign } from "./state.js";
  import { rpc } from "./util.js";

  let inbox = $state(null); // { statements, coverage, imported, month }
  let error = $state("");
  let busy = $state(""); // the action of the last click, for 3 s: one task per click
  const agent = $derived((inbox, app.installed.length ? active?.agent || app.installed[0] : ""));

  async function load() {
    try {
      inbox = await rpc("inbox", { lang: app.lang });
      error = app.inboxError; // an error of the last action, shown once
      assign({ inboxError: "" });
    } catch (e) {
      error = String(e);
    }
  }

  async function act(name) {
    if (busy) return;
    busy = name;
    try {
      await INBOX_ACTIONS[name]();
    } finally {
      setTimeout(() => (busy = ""), 3000);
    }
  }

  $effect(() => {
    document.addEventListener("km-inbox", load);
    return () => {
      document.removeEventListener("km-inbox", load);
    };
  });
</script>

<div class="inbox-page wa-stack wa-gap-l">
  <header>
    <h1>{t("inbox")}</h1>
    <p class="lead">{t("inboxLead")}</p>
  </header>

  {#if inbox && !inbox.imported}
    <ol class="start">
      <li>{@html t("step1")}</li>
      <li>{@html t("step2")}</li>
      <li>{@html t("step3")}</li>
    </ol>
  {/if}

  <div class="drop wa-cluster wa-gap-s">
    <p>{t("dropHere")}</p>
    <wa-button size="small" variant="brand" disabled={busy === "add"} onclick={() => act("add")}
      >{t("chooseFiles")}</wa-button
    >
    <wa-button size="small" appearance="filled" onclick={() => act("reveal")}>{t("showInFinder")}</wa-button>
  </div>
  {#if error}<p class="error">{error}</p>{/if}

  {#if inbox}
    <section class="wa-stack wa-gap-xs">
      <h2>{t("waiting")}{inbox.statements.length ? ` (${inbox.statements.length})` : ""}</h2>
      {#each inbox.statements as s (s.name)}
        <div class="row wa-split">
          <div class="wa-cluster wa-gap-s">
            <span class="name">{s.name}</span>
            <span class="muted">{s.account || s.detail.startsWith("FAIL") ? s.detail : t("cannotRead")}</span>
          </div>
          <div class="wa-cluster wa-gap-xs">
            {#if s.account === "NEW"}
              <wa-tag size="small" variant="warning">{t("newAccount")}</wa-tag>
            {:else if s.account}
              <wa-tag size="small" variant="success">{s.account}</wa-tag>
            {:else}
              <wa-tag size="small" variant="danger">{t("needsParser")}</wa-tag>
            {/if}
            <wa-button size="small" appearance="plain" title={t("removeFile")} onclick={() => removeFile(s.name)}
              >×</wa-button
            >
          </div>
        </div>
      {:else}
        <p class="muted">{t("noWaiting")}</p>
      {/each}
      {#if inbox.statements.length}
        <div class="wa-cluster wa-gap-m">
          <wa-button variant="brand" disabled={busy === "import"} onclick={() => act("import")}>
            <AgentIcon slot="start" />
            {agent ? t(inbox.imported ? "importWith" : "setupWith", { agent }) : t("import")}
          </wa-button>
          <p class="muted note">{t("importNote")}</p>
        </div>
      {/if}
    </section>

    {#if inbox.imported}
      <section class="wa-stack wa-gap-xs">
        <h2>{t("closeHead")}</h2>
        <p class="muted">{t("closeNote")}</p>
        <div>
          <wa-button size="small" appearance="filled" disabled={busy === "close"} onclick={() => act("close")}
            ><AgentIcon slot="start" />{t("closeMonth", { month: inbox.month })}</wa-button
          >
        </div>
      </section>
    {/if}

    <section class="wa-stack wa-gap-xs">
      <h2>{t("importedPeriods")}</h2>
      {#each inbox.coverage as c (c.account)}
        <div class="row wa-split">
          <span class="mono">{c.account}</span>
          <span>
            {#if c.period}{c.period}{:else}<wa-tag size="small" variant="danger">{t("neverImported")}</wa-tag>{/if}
            {#if c.missing.length}<span class="missing">{c.missing.join(", ")}</span>{/if}
          </span>
        </div>
      {:else}
        <p class="muted">{t("nothingImported")}</p>
      {/each}
    </section>
  {/if}
</div>
