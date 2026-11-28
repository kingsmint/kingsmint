<!-- The budgets' detail (server/budgets.py): each budget's spending against its limit, what is left, per day, and the
     days left; the worst first. ‹ › show the accounts' periods before this one (each in its own period: a month, a
     quarter, a year); a tag's budget has its dates and its payments. Forms for an account's budget (BudgetForm) and
     a tag's. Color only for the state. -->
<script>
  import { accountLabel } from "./accounts.js";
  import { app } from "./app.svelte.js";
  import BudgetForm from "./BudgetForm.svelte";
  import { t } from "./i18n.js";
  import Message from "./Message.svelte";
  import { toast } from "./toast.js";
  import { focusField, rpc } from "./util.js";

  // data: rpc("budgets") of the current periods, which comes with the overview; onchanged: the overview loads again
  let { data, currency, onchanged, openAccount, openTxn } = $props();
  let offset = $state(0);
  let adding = $state(false); // a new account's budget: a card at the end of the list
  let older = $state(null); // rpc("budgets", {offset}) for offset < 0
  const b = $derived(offset ? older : data);

  $effect(() => {
    const o = offset;
    data; // again after the ledger changes
    older = null; // not the period before under this one's label, while it loads or when it fails
    if (!o) return;
    rpc("budgets", { offset: o })
      .then((r) => offset === o && (older = r))
      .catch(() => {});
  });

  const fmt = (o) => new Intl.NumberFormat(app.lang, o);
  const eur = (v) => (v == null ? "–" : fmt({ style: "currency", currency, maximumFractionDigits: 0 }).format(v));
  const pct = (v) => fmt({ style: "percent", maximumFractionDigits: 0 }).format(v);
  const day = (iso, o = { day: "numeric", month: "numeric", year: "numeric" }) =>
    new Intl.DateTimeFormat(app.lang, o).format(new Date(iso));
  const range = (x) => `${day(x.start)} – ${x.end ? day(x.end) : t("budgetOpenEnd")}`;

  // a tag's form: a new budget, or the one of `editing` (its tag)
  let tagForm = $state(null);
  let tagError = $state("");
  const newTag = () => {
    const now = new Date();
    tagForm = { tag: "", name: "", limit: "", end: "", start: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01` };
    tagError = "";
  };
  const editTag = (x) => {
    tagForm = { old: x.tag, tag: x.tag, name: x.name === x.tag ? "" : x.name, limit: String(x.limit), start: x.start, end: x.end ?? "" };
    tagError = "";
  };
  async function saveTag(limit = tagForm.limit) {
    const f = $state.snapshot(tagForm);
    const r = await rpc("budget_tag_save", { ...f, limit, end: f.end || null, old: f.old ?? null }).catch((e) => ({
      error: String(e),
    }));
    if (r.error) return void (tagError = r.error);
    tagForm = null;
    onchanged?.();
    const text = r.version_error || `${t("budgetSaved")}: ${r.changed}`;
    toast(Message, r.version_error ? { text } : { text, action: t("budgetUndo"), act: undo });
  }
  const undo = () =>
    rpc("versions_restore")
      .then((r) => r.error && toast(Message, { text: r.error }, { variant: "danger" }))
      .finally(() => onchanged?.());
</script>

{#snippet numbers(x)}
  <span class="meter"><span style:width="{Math.min(x.share, 1) * 100}%"></span></span>
  <dl>
    <dt>{t("budgetSpent")}</dt>
    <dd>{eur(x.spent)} / {eur(x.limit)} ({pct(x.share)})</dd>
    <dt>{x.left < 0 ? t("budgetOverLabel") : t("budgetLeftLabel")}</dt>
    <dd>{eur(Math.abs(x.left))}</dd>
    {#if x.days_left}
      <dt>{t("budgetPerDay")}</dt>
      <dd>{x.per_day == null ? "–" : eur(x.per_day)}</dd>
      <dt>{t("budgetDaysLeft")}</dt>
      <dd>{x.days_left}</dd>
    {/if}
  </dl>
{/snippet}

<div class="budgets">
  <p class="muted">{t("budgetsNote")}</p>
  {#if b?.errors?.length}<p class="error">{b.errors.join(" ")}</p>{/if}
  {#if data?.file === false}<p class="error">{t("budgetsNoFile")}</p>{/if}

  <h2>
    {t("budgetsAccounts")}
    <span class="period">
      <button type="button" class="arrow" title={t("previous")} onclick={() => offset--}><wa-icon name="chevron-left"></wa-icon></button>
      <span class="muted">{offset ? t("budgetsBefore", { n: -offset }) : t("budgetsNow")}</span>
      <button type="button" class="arrow" title={t("next")} disabled={!offset} onclick={() => offset++}><wa-icon name="chevron-right"></wa-icon></button>
    </span>
  </h2>
  {#if b && !b.accounts.length}<p class="muted">{offset ? t("budgetsNoneThen") : t("budgetsNoneAccounts")}</p>{/if}
  <div class="budget-list">
    {#each b?.accounts ?? [] as x (x.account)}
      <section class="card" data-state={x.state}>
        <h3>
          <button type="button" class="more" onclick={() => openAccount(x.account)}>{accountLabel(x.account)}</button>
          <span class="muted">{t(`budget_${x.period}`)} · {range(x)}</span>
        </h3>
        {@render numbers(x)}
        {#if !offset}
          <BudgetForm account={x.account} budget={x} averages={data?.averages} today={data?.today} {currency}
            label={t("budgetChange")} onsaved={onchanged} />
        {/if}
      </section>
    {/each}
    {#if adding && !offset}
      <section class="card">
        <h3><span>{t("budgetNew")}</span></h3>
        <!-- the accounts without a budget: one with a budget changes it in its own card -->
        <BudgetForm bind:open={adding} accounts={data.expense_accounts.filter((a) => !data.accounts.some((x) => x.account === a))}
          averages={data.averages} today={data.today} {currency} onsaved={onchanged} />
      </section>
    {/if}
  </div>
  {#if !offset && !adding && data?.file}
    <wa-button size="small" appearance="filled" onclick={() => (adding = true)}
      ><wa-icon slot="start" name="piggy-bank"></wa-icon>{t("budgetForAccount")}</wa-button
    >
  {/if}

  <h2>{t("budgetsTags")}</h2>
  {#if !data?.tags.length}<p class="muted">{t("budgetsNoneTags")}</p>{/if}
  <div class="budget-list">
    {#each data?.tags ?? [] as x (x.tag)}
      <section class="card" data-state={x.state}>
        <h3>
          <span>{x.name}</span>
          <span class="muted">#{x.tag} · {range(x)}</span>
        </h3>
        {@render numbers(x)}
        {#if tagForm?.old === x.tag}
          {@render tagFormFields()}
        {:else}
          <wa-button size="small" appearance="filled" onclick={() => editTag(x)}
            ><wa-icon slot="start" name="piggy-bank"></wa-icon>{t("budgetChange")}</wa-button
          >
        {/if}
        {#if x.payments.length}
          <table>
            <tbody>
              {#each x.payments as p (p.hash)}
                <tr class="link" onclick={() => openTxn(p)}>
                  <td class="muted">{day(p.date)}</td>
                  <td>{p.payee}{#if p.narration && p.narration !== p.payee}<span class="muted">{` · ${p.narration}`}</span>{/if}</td>
                  <td class="num">{eur(p.amount)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <p class="muted">{t("budgetNoPayments", { tag: x.tag })}</p>
        {/if}
      </section>
    {/each}
    {#if tagForm && !tagForm.old}
      <section class="card">
        <h3><span>{t("budgetNewTag")}</span></h3>
        {@render tagFormFields()}
      </section>
    {/if}
  </div>
  {#if !tagForm && data?.file}
    <wa-button size="small" appearance="filled" onclick={newTag}><wa-icon slot="start" name="tag"></wa-icon>{t("budgetForTag")}</wa-button>
  {/if}
</div>

{#snippet tagFormFields()}
  <form
    class="budget-form"
    onsubmit={(e) => {
      e.preventDefault();
      saveTag();
    }}
  >
    <div>
      <wa-input size="small" label={t("budgetTag")} hint={t("budgetTagNote")} value={tagForm.tag}
        oninput={(e) => (tagForm.tag = e.target.value)} use:focusField></wa-input>
      <!-- the tags of the transactions, the most used first: a click takes one -->
      {#each (data?.used ?? []).slice(0, 8) as tag}
        <button type="button" class="tag" onclick={() => (tagForm.tag = tag)}>#{tag}</button>
      {/each}
    </div>
    <wa-input size="small" label={t("budgetName")} value={tagForm.name} oninput={(e) => (tagForm.name = e.target.value)}></wa-input>
    <wa-input size="small" label={`${t("budgetLimit")} (${currency})`} inputmode="decimal" value={tagForm.limit}
      oninput={(e) => (tagForm.limit = e.target.value)}></wa-input>
    <wa-input size="small" type="date" label={t("budgetStart")} value={tagForm.start}
      oninput={(e) => (tagForm.start = e.target.value)}></wa-input>
    <wa-input size="small" type="date" label={t("budgetEndDate")} hint={t("budgetEndDateNote")} value={tagForm.end}
      oninput={(e) => (tagForm.end = e.target.value)}></wa-input>
    {#if tagError}<p class="error">{tagError}</p>{/if}
    <div class="actions">
      <wa-button size="small" variant="brand" type="submit" disabled={!tagForm.tag || !tagForm.limit || !tagForm.start}
        >{t("save")}</wa-button
      >
      {#if tagForm.old}
        <wa-button size="small" appearance="filled" onclick={() => saveTag("0")}>{t("budgetRemove")}</wa-button>
      {/if}
      <wa-button size="small" appearance="filled" onclick={() => (tagForm = null)}>{t("cancel")}</wa-button>
    </div>
  </form>
{/snippet}
