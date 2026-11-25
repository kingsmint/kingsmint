<!-- A transaction's split over several categories (server/edit.py), saved into its file, where `kingsmint reimport`
     keeps it. The first row is the category the transaction had, which gets the rest; each part added below has its
     amount. The server takes the rest last: the rows go to it in that order. -->
<script>
  import { untrack } from "svelte";
  import { app } from "./app.svelte.js";
  import CategoryPicker from "./CategoryPicker.svelte";
  import { t } from "./i18n.js";

  // txn: what rpc("entry") gives; save(args): saves it as the page saves its changes, the result or null (the page
  // shows the error); a save gives the page a new transaction, which ends the split
  let { txn, save, cancel } = $props();

  const FEES = "Expenses:Bank:Fees";
  // the form starts from the transaction as it opened; a save gives the view a new one
  const start = untrack(() => $state.snapshot(txn));
  const bank = start.postings[0];
  const after = start.postings.slice(1);
  // the fee the import wrote beside the category (start.fee, from the server) belongs to the statement row
  const fixed = [bank, ...(start.fee ? [after.find((p) => p.account === FEES)] : [])];
  const total = Math.abs(fixed.reduce((s, p) => s + p.number, 0)); // what the categories share
  const old = after.filter((p) => !fixed.includes(p));
  // the rest first (in the file, the category without an amount is the last), then the parts with their amounts
  let rows = $state(
    [old.at(-1), ...old.slice(0, -1)].filter(Boolean).map((p) => ({ account: p.account, amount: Math.abs(p.number) })),
  );
  if (rows.length < 2) rows.push({ account: "", amount: null });
  let picking = $state(rows.length - 1 && !rows.at(-1).account ? rows.length - 1 : -1); // a new part: its category first
  let busy = $state(false);

  const money = (v) =>
    new Intl.NumberFormat(app.lang, { style: "currency", currency: bank.currency, minimumFractionDigits: 2 }).format(v);
  const given = $derived(rows.slice(1).reduce((s, r) => s + (Number(r.amount) || 0), 0));
  const rest = $derived(Math.round((total - given) * 100) / 100);
  const ok = $derived(rows.every((r) => r.account) && rows.slice(1).every((r) => Number(r.amount) > 0) && rest > 0);

  async function submit() {
    busy = true;
    const parts = rows.slice(1).map((r) => ({ account: r.account, amount: String(r.amount) }));
    await save({ postings: [...parts, { account: rows[0].account }] });
    busy = false;
  }
  function add() {
    rows.push({ account: "", amount: null });
    picking = rows.length - 1;
  }
</script>

<section class="txn-edit">
  <h2>{t("split")} <span class="muted">{money(total)}</span></h2>
  <table>
    <tbody>
      {#each rows as r, i}
        <tr>
          <td>
            {#if picking === i}
              <CategoryPicker accounts={txn.accounts} suggested={txn.suggested} value={r.account}
                pick={(a) => ((r.account = a), (picking = -1))} cancel={() => (picking = -1)} />
            {:else}
              <button type="button" class="cat" class:empty={!r.account} onclick={() => (picking = i)}
                >{r.account || t("pickCategory")}</button
              >
            {/if}
          </td>
          <td class="num">
            {#if i > 0}
              <input type="number" min="0.01" step="0.01" bind:value={r.amount} aria-label={t("amount")} />
            {:else}
              <span class:error={rest <= 0} title={t("restTitle")}>{money(rest)}</span>
            {/if}
          </td>
          <td>
            {#if rows.length > 1}<!-- the first one removed: the next one gets the rest -->
              <button type="button" class="more" title={t("removeCategory")} onclick={() => rows.splice(i, 1)}>×</button>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
  <button type="button" class="more" onclick={add}>+ {t("addCategory")}</button>
  <div class="buttons">
    <wa-button size="small" appearance="filled" onclick={cancel}>{t("cancel")}</wa-button>
    <wa-button size="small" variant="brand" disabled={busy || !ok} onclick={submit}>{t("save")}</wa-button>
  </div>
</section>
