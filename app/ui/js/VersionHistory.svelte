<!-- The versions of the ledger (jj), in the popup of the rail's History. The app saves one before each task for the
     agent, the agent after each change; a return to a version is a new version too, so it can be undone. It loads
     each time the popup opens (app.historyOpen). -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { rpc } from "./util.js";

  let data = $state(null); // { versions (null before they are on), dirty, error }
  let confirm = $state(""); // the version whose return waits for a yes
  let note = $state("");
  let error = $state("");

  async function load() {
    confirm = "";
    try {
      data = await rpc("history");
      error = data.error ?? error;
    } catch (e) {
      error = String(e);
    }
  }

  // an action, then the list again with its note or error
  async function act(method, params, done) {
    note = error = "";
    try {
      const r = await rpc(method, params);
      if (r?.error) error = r.error;
      else note = done(r);
    } catch (e) {
      error = String(e);
    }
    await load();
  }

  const restore = (id) =>
    act("versions_restore", id ? { id } : {}, (r) => {
      const back = r.back.length ? ` ${t("movedBack", { files: r.back.join(", ") })}` : "";
      return t("restored", { id: r.id, title: r.title }) + back;
    });

  // loads each time the popup opens
  $effect(() => {
    if (!app.historyOpen) return;
    note = error = "";
    load();
  });
</script>

{#if app.historyOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div id="history" onclick={(e) => e.stopPropagation()}>
    <div class="history-head wa-split">
      <h3>{t("versions")}</h3>
      {#if data?.versions && (data.dirty || data.versions.length > 1)}
        <wa-button size="small" variant="brand" title={t("undoTitle")} onclick={() => restore()}>{t("undo")}</wa-button>
      {/if}
    </div>

    {#if error}<p class="error">{error}</p>{/if}
    {#if note}<p class="note">{note}</p>{/if}

    {#if data && data.versions === null}
      <div class="wa-stack wa-gap-s empty">
        <p>{t("noVersionsYet")}</p>
        <wa-button size="small" variant="brand" onclick={() => act("versions_init", {}, () => t("versionsOn"))}
          >{t("turnOnVersions")}</wa-button
        >
      </div>
    {:else if data}
      {#if data.dirty}
        <div class="version current">
          <div><b>{t("unsaved")}</b><small>{t("current")}</small></div>
        </div>
      {/if}

      {#each data.versions as v, i (v.id)}
        {@const current = i === 0 && !data.dirty}
        <div class="version" class:current class:mark={v.empty} title={v.message}>
          <div>
            <b>{v.message.split("\n")[0] || t("noDescription")}</b>
            <small>{[v.date, current && t("current"), v.empty && t("noChanges")].filter(Boolean).join(" · ")}</small>
          </div>
          {#if !current}
            <wa-button size="small" appearance="outlined" onclick={() => (confirm = v.id)}>{t("returnHere")}</wa-button>
          {/if}
        </div>
        {#if confirm === v.id}
          <div class="confirm wa-stack wa-gap-s">
            <span>{t("returnConfirm", { n: i + (data.dirty ? 1 : 0) })}</span>
            <div class="wa-cluster wa-gap-xs">
              <wa-button size="small" variant="brand" onclick={() => restore(v.id)}>{t("return")}</wa-button>
              <wa-button size="small" appearance="outlined" onclick={() => (confirm = "")}>{t("cancel")}</wa-button>
            </div>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
{/if}
