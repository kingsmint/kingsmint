<!-- An expense account's budget (server/budgets.py): a button that opens the form, the form, and after a save a toast
     with Undo (the version before). Without `account`, the form picks one of `accounts`. A new limit replaces the
     account's budget from its date (the start of the chosen period unless changed); ending it starts with the
     budget's own current period. `averages`: the accounts' average month of the last 12, shown by the limit. -->
<script>
  import { accountLabel } from "./accounts.js";
  import { app } from "./app.svelte.js";
  import { t } from "./i18n.js";
  import Message from "./Message.svelte";
  import { toast } from "./toast.js";
  import { focusField, rpc } from "./util.js";

  let {
    account = null,
    accounts = [],
    budget = null,
    averages = {},
    today,
    currency,
    label,
    onsaved,
    open = $bindable(false),
  } = $props();
  const PERIODS = ["monthly", "quarterly", "yearly"];
  const MONTHS = { monthly: 1, quarterly: 3, yearly: 12 };
  let chosen = $state("");
  let period = $state("monthly"); // start() takes the budget's own
  let limit = $state("");
  let since = $state(""); // empty: the start of the chosen period, shown in the field
  let error = $state("");
  let saving = $state(false);

  // the first day of the period `today` is in, as the server counts it (budgets.period_start)
  const periodStart = (p) => {
    const [y, m] = (today ?? new Date().toISOString()).slice(0, 7).split("-").map(Number);
    const month = p === "monthly" ? m : p === "quarterly" ? Math.floor((m - 1) / 3) * 3 + 1 : 1;
    return `${y}-${String(month).padStart(2, "0")}-01`;
  };
  const target = $derived(account ?? chosen);
  const average = $derived(averages?.[target]);
  const eur = (v) => new Intl.NumberFormat(app.lang, { style: "currency", currency, maximumFractionDigits: 0 }).format(v);

  function start() {
    chosen = account ?? "";
    period = budget?.period && PERIODS.includes(budget.period) ? budget.period : "monthly";
    limit = budget ? String(budget.amount) : "";
    since = "";
    error = "";
    open = true;
  }

  async function save(value = limit, from = since || periodStart(period), per = period) {
    saving = true;
    const r = await rpc("budget_save", { account: target, period: per, limit: value, since: from }).catch((e) => ({
      error: String(e),
    }));
    saving = false;
    if (r.error) return void (error = r.error);
    open = false;
    onsaved?.();
    const text = r.version_error || `${t("budgetSaved")}: ${r.changed}`;
    toast(Message, r.version_error ? { text } : { text, action: t("budgetUndo"), act: undo });
  }
  const undo = () =>
    rpc("versions_restore")
      .then((r) => r.error && toast(Message, { text: r.error }, { variant: "danger" }))
      .finally(() => onsaved?.());
</script>

{#if budget && !PERIODS.includes(budget.period)}
  <!-- weekly or daily, written by hand (Fava takes them): the form would make it monthly -->
  <span class="muted">{t("budgetByHand", { period: t(`budget_${budget.period}`) })}</span>
{:else if !open}
  <wa-button size="small" appearance="filled" onclick={start}><wa-icon slot="start" name="piggy-bank"></wa-icon>{label}</wa-button>
{:else}
  <form
    class="budget-form"
    onsubmit={(e) => {
      e.preventDefault();
      save();
    }}
  >
    {#if !account}
      <wa-select size="small" label={t("category")} placeholder={t("budgetChooseCategory")} value={chosen}
        onchange={(e) => (chosen = e.target.value)}>
        {#each accounts as a}<wa-option value={a}>{accountLabel(a)}</wa-option>{/each}
      </wa-select>
    {/if}
    <div>
      <span class="label">{t("budgetPeriod")}</span>
      <wa-button-group label={t("budgetPeriod")}>
        {#each PERIODS as p}
          <wa-button size="small" variant={p === period ? "brand" : "neutral"} appearance={p === period ? "accent" : "filled"}
            onclick={() => (period = p)}>{t(`budget_${p}`)}</wa-button>
        {/each}
      </wa-button-group>
    </div>
    <wa-input size="small" label={`${t("budgetLimit")} (${currency})`} inputmode="decimal" value={limit}
      hint={average ? t("budgetAverage", { amount: eur(average * MONTHS[period]) }) : ""}
      oninput={(e) => (limit = e.target.value)} use:focusField></wa-input>
    <wa-input size="small" type="date" label={t("budgetSince")} value={since || periodStart(period)}
      oninput={(e) => (since = e.target.value)}></wa-input>
    {#if error}<p class="error">{error}</p>{/if}
    <div class="actions">
      <wa-button size="small" variant="brand" type="submit" disabled={saving || !limit || !target}>{t("save")}</wa-button>
      {#if budget}
        <!-- from the start of the budget's own period, whatever the form has chosen -->
        <wa-button size="small" appearance="filled" disabled={saving}
          onclick={() => save("0", budget.start, budget.period)}>{t("budgetEnd")}</wa-button>
      {/if}
      <wa-button size="small" appearance="filled" onclick={() => (open = false)}>{t("cancel")}</wa-button>
    </div>
  </form>
{/if}
