<!-- A toast (toast.js) after a transaction got a category: Undo, and the offer to give the category to the
     counterparty's other transactions too, as a rule (server/edit.py), which also takes the later ones. It asks the
     server what the rule would move first; when it moves nothing, it is a short message that goes by itself. Yes adds
     the rule and runs `kingsmint reimport`; a transaction changed by hand keeps its category. -->
<script>
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import { rpc } from "./util.js";

  // ref: the changed transaction ({id} or {hash}); undo(): the change back; apply(): adds the rule, as the page saves
  // its changes (one after another), and gives what rpc("rule_save") gives, or null after an error it showed
  let { ref, account, undo, apply, close } = $props();
  let offer = $state(null); // rpc("rule_preview")
  let open = $state(false);
  let busy = $state(false);

  $effect(() => {
    rpc("rule_preview", { ...ref, account })
      .then((r) => {
        offer = r.error ? { moves: 0, rows: [] } : r;
        if (!offer.moves) setTimeout(close, 6000); // only Undo to offer
      })
      .catch(() => {});
  });
  const others = $derived(offer?.rows.filter((x) => !ref.id || x.id !== ref.id) ?? []);
  const fmt = (v, c) => new Intl.NumberFormat(app.lang, { style: "currency", currency: c, minimumFractionDigits: 2 }).format(v);
  const name = (a) => a.split(":").at(-1);

  async function yes() {
    busy = true;
    const r = await apply();
    busy = false;
    if (r) close();
  }
</script>

<div class="toast-message rule-offer">
  <span>
    {t("savedAs", { account: name(account) })}
    {#if offer?.moves > 0}
      {t("ruleAsk", { n: offer.moves, who: offer.counterparty, account: name(account) })}
      <button type="button" class="more" onclick={() => (open = !open)}>{open ? t("hideList") : t("showList")}</button>
    {/if}
  </span>
  <div class="buttons">
    <wa-button size="small" appearance="filled" onclick={() => (undo(), close())}>{t("runwayUndo")}</wa-button>
    {#if offer?.moves > 0}
      <wa-button size="small" appearance="filled" onclick={close}>{t("no")}</wa-button>
      <wa-button size="small" variant="brand" disabled={busy} onclick={yes}>{busy ? t("ruleApplying") : t("yes")}</wa-button>
    {/if}
  </div>
  {#if open && offer}
    <table class="rule-rows">
      <tbody>
        {#each others.slice(0, 20) as x (x.id)}
          <tr class:muted={x.edited || (x.accounts.length === 1 && x.accounts[0] === account)}>
            <td>{x.date}</td>
            <td>{x.payee}</td>
            <td class="num">{fmt(x.amount, x.currency)}</td>
            <td>{x.accounts.map(name).join(", ")}{x.edited ? ` · ${t("editedByHand")}` : ""}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if others.length > 20}<p class="muted">{t("andMore", { n: others.length - 20 })}</p>{/if}
  {/if}
</div>
