<!-- The overview, on one screen: five tiles for a month or a year, each with the 12 before it, then the cash flow of
     those periods and where the money went. ‹ › (and ← →) go to the previous and the next period. A tile, a bar or a category opens its detail in place of the overview, with the
     way back at the top (Esc goes one level up). Each view is a step of the window's history, as a page in a browser:
     the trackpad's swipe (WebKit's, main.rs), ⌘[ and the mouse's back button go back, also from Fava when the overview
     opened it. An account without subaccounts, a payee and a balance open the transactions of the period, with
     their filter on top; a transaction opens its detail (its postings, statement, the payee's other payments), where
     it can be changed (TxnEdit.svelte), and from there Fava.
     A split of its group (GroupActions.svelte) opens one more overview beside it, on the same view: each has its own
     period, view and steps of the history. In a wide panel a transaction's detail opens beside the transactions.
     The numbers come from the ledger's server (server/dashboard.py) and load again after the ledger's files change.
     Color only for a state: green good, yellow or red a warning. -->
<script>
  import { untrack } from "svelte";
  import { app } from "./app.svelte.js";
  import Chart, { FAVA } from "./Chart.svelte";
  import { stepToFava } from "./fava.js";
  import { t, tAgent } from "./i18n.js";
  import { saveSoon, showPart, visible } from "./panels.js";
  import { pinKey, pinOf, railKey, togglePin, VIEWS } from "./rail.js";
  import Spark from "./Spark.svelte";
  import CashEntry from "./CashEntry.svelte";
  import CategoryPicker from "./CategoryPicker.svelte";
  import RuleOffer from "./RuleOffer.svelte";
  import Message from "./Message.svelte";
  import { toast } from "./toast.js";
  import TxnEdit from "./TxnEdit.svelte";
  import TagField from "./TagField.svelte";
  import { assign, dock, favas, overviews } from "./state.js";
  import { tell } from "./tasks.js";
  import { invoke, listen, rpc } from "./util.js";

  const KINDS = ["current", "savings", "investments", "property", "loans", "other", "liabilities"];

  // the overview in the rail's panel ("dashboard"), or one more in a split: its Dockview panel, and the state it
  // starts with (the view it was split from, or the one saved with the layout)
  let { api = null, params = {} } = $props();
  const id = untrack(() => api?.id ?? "dashboard");
  const start = untrack(() => params ?? {});

  let unit = $state(start.unit ?? "month"); // "month" or "year"
  let period = $state(start.period ?? null); // the chosen month (YYYY-MM) or year (YYYY); null: the last full month, or its year
  let d = $state(null); // what rpc("dashboard") gives
  // what shows: the overview, a report's detail ("cashflow", "networth", "savings", "runway"), or an account's
  let view = $state(start.view ?? { name: "overview" });
  // another view, as a step of the window's history: of this panel
  function go(next) {
    if (next.name !== "txns" && next.name !== "txn") search = "";
    view = next;
    history.pushState({ dashboard: $state.snapshot(next), panel: id }, "");
  }
  // the rail marks the view of the overview it goes to
  $effect(() => {
    if (app.overview.id === id) Object.assign(app.overview, { key: railKey(view), view: pinKey(view) });
  });
  // what a split starts with, and what a split view's layout saves
  const current = () => ({ view: $state.snapshot(view), unit, period });
  $effect(() => {
    overviews.set(id, current);
    return () => overviews.delete(id);
  });
  // saved in the panel's parameters with the ledger's layout, so the overview goes on where it was after a restart
  $effect(() => {
    const now = current();
    untrack(() => {
      const panel = api ?? dock?.getPanel("dashboard")?.api;
      if (!panel) return;
      panel.updateParameters(now);
      saveSoon();
    });
  });
  let root = $state(); // the panel's scrolled element
  let width = $state(0);
  // a transaction's detail beside the transactions it was opened from, when the panel is wide enough for both
  const wide = $derived(width >= 1100);
  const listView = $derived(wide && view.name === "txn" && view.parent?.name === "txns" ? view.parent : view);
  let payees = $state(null); // the payees of the account that shows, in the chosen period
  let rec = $state(null); // the recurring payments: what rpc("recurring") gives
  let adding = $state(null); // the recurring view's form that confirms a payee by hand: { payee, period }
  let showHidden = $state(false); // the recurring view shows the payees marked as not recurring
  let showSuggested = $state(null); // ... and the suggestions; null: only while none is confirmed
  // the transactions view: its rows from the period before the chosen one (for the comparison), and the text searched
  let rows = $state(null);
  let search = $state("");
  let txn = $state(); // the transaction view's: what rpc("entry") gives, null when the ledger no longer has it
  // the transaction view's changes, in place: the category picked (its index), the payee or note typed, the split
  // (TxnEdit.svelte); after a change, a toast: Undo, and for one category the rule for the counterparty (RuleOffer)
  let picking = $state(-1);
  let typing = $state(null); // "payee" or "note"
  let splitting = $state(false);
  // the transactions view's change of a row's category, in place: the row (its hash), the accounts to pick from
  let listPick = $state(null);
  let listInfo = $state({ editable: false, accounts: [] });
  let cashing = $state(false); // the form of a cash payment (CashEntry.svelte) shows above the transactions
  // after a save: Undo, which returns to the version before it; a payment out of the months shown shows its month,
  // else it would not be in the rows
  function cashDone(r) {
    cashing = false;
    if (!r) return;
    if (r.error) problem(r.error);
    else if (r.version)
      toast(Message, {
        text: t("cashSaved"),
        action: t("runwayUndo"),
        act: () => rpc("versions_restore").then((u) => (u.error && problem(u.error), load())),
      });
    else toast(Message, { text: t("cashSaved") });
    // a year that is not over shows its full months only (d.ends): a payment after them shows in its month
    const m = r.date.slice(0, 7);
    const shows = unit === "year" ? m.slice(0, 4) === d?.period && m <= d.ends.at(-1) : m === d?.period;
    if (shows) return load();
    unit = "month";
    pick(m);
  }
  // the tags (rpc("tags")): each with what it spent, first and last date; a tag's transactions are the transactions
  // view with its tag filter (view.tag), over all the ledger's months (view.all)
  let tagged = $state(null);
  // the transactions view's rows chosen with ⌘ or Shift click (their id, else hash), to add or remove a tag on all
  let chosen = $state([]);
  let anchor = null; // the transaction (keyOf) a Shift click chooses from: the last clicked, by key, as rows come and go

  // numbers in the app's language: money without cents, percentages with one decimal
  const fmt = (o) => new Intl.NumberFormat(app.lang, o);
  const eur = (v, sign = "auto") =>
    v == null ? "–" : fmt({ style: "currency", currency: d.currency, maximumFractionDigits: 0, signDisplay: sign }).format(v);
  const delta = (v) => eur(v, "exceptZero");
  const pct = (v, sign = "auto") =>
    v == null || !Number.isFinite(v)
      ? "–"
      : fmt({ style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: sign }).format(v);
  const one = (v) => fmt({ minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);
  const date = (m, o) => new Intl.DateTimeFormat(app.lang, o).format(new Date(m.slice(0, 4), m.slice(5) - 1));
  // a period's name: a year as it is, a month in the app's language
  const periodName = (p) => (p.length === 4 ? p : date(p, { month: "long", year: "numeric" }));
  const periodShort = (p) => (p.length === 4 ? p : date(p, { month: "short", year: "numeric" })); // "Oct 2025": "Oct 25" reads as a day
  // the texts that name the period and its comparisons
  const L = $derived(
    unit === "year"
      ? { last: "lastYear", avg: "avgYears", during: "thisYear", vsLast: "vsLastYear", window: "years", note: "vsAverageNoteYears" }
      : { last: "lastMonth", avg: "avg12", during: "thisMonth", vsLast: "vsLastMonth", window: "months12", note: "vsAverageNote" },
  );
  // Fava's time filter of the chosen period: a year that is not over, its months up to the last full one
  const favaTime = $derived(
    unit === "year" && d?.months < 12 ? `${d.period}-01 - ${d.ends.at(-1)}` : (d?.period ?? ""),
  );
  // the previous and the next period that has data (d.periods: the newest first)
  const older = $derived(d?.periods?.[d.periods.indexOf(d.period) + 1]);
  const newer = $derived(d?.periods?.[d.periods.indexOf(d.period) - 1]);
  const money = $derived({ style: "currency", currency: d?.currency ?? "EUR" }); // a chart's unit
  const PERCENT = { style: "unit", unit: "percent" };
  // months, or years when they are 2 or more: 153.7 months reads as 12.8 years
  const duration = (months) =>
    months >= 24 ? `${one(months / 12)} ${t("yearsShort")}` : `${one(months)} ${t("monthsShort")}`;

  // An account's amount in each period of the window; the chosen period is the last
  const flow = (a) => d?.flows?.[a] ?? d?.window?.map(() => 0) ?? [];
  const prevOf = (s) => (s.length > 1 ? s.at(-2) : null);
  const avgOf = (s) => (s.length > 1 ? s.slice(0, -1).reduce((x, y) => x + y, 0) / (s.length - 1) : null);
  const sum = (s) => s.reduce((x, y) => x + y, 0);
  const children = (a) =>
    Object.keys(d?.flows ?? {}).filter((c) => c.startsWith(`${a}:`) && !c.slice(a.length + 1).includes(":"));
  const name = (a) => (a.includes(":") ? a.split(":").at(-1) : t(a.toLowerCase()));
  // the account's subaccounts in the chosen period, the largest first
  const parts = (a) =>
    children(a)
      .map((c) => ({ account: c, series: flow(c), leaf: !children(c).length }))
      .filter((c) => c.series.some(Boolean))
      .sort((x, y) => y.series.at(-1) - x.series.at(-1));
  // The change of `v` against `base` as Fava's Trends report marks it: a percentage, red when it is bad and green when
  // it is good, full from 50 %; grey when the change is under 0.5 % of `total`. `rise`: whether a rise is "good"
  // (income, balances) or "bad" (spending). Money back (a negative amount of spending) is not compared.
  const LEVELS = [
    [0.5, 2],
    [0.15, 1],
    [-0.15, 0],
    [-0.5, -1],
  ];
  const MARKS = { 2: "bad2", 1: "bad1", 0: "", "-1": "good1", "-2": "good2" };
  function change(v, base, rise, total) {
    if (base == null || (!v && !base)) return null;
    const small = Math.abs(v - base) < Math.abs(total) * 0.005;
    const mark = (level) => (small ? "small" : MARKS[rise === "bad" ? level : -level]);
    if (!base) return { text: t("new"), cls: mark(v > 0 ? 2 : -2) };
    if (rise === "bad" && (v < 0 || base < 0)) return { text: "–", cls: "small" };
    const c = (v - base) / Math.abs(base);
    // over ten times as much: the number says no more than that
    const text = fmt({ style: "percent", maximumFractionDigits: 0, signDisplay: "exceptZero" }).format(Math.min(c, 9.99));
    if (c > 9.99) return { text: `>${text}`, cls: mark(2) };
    return { text, cls: mark(LEVELS.find(([low]) => c >= low)?.[1] ?? -2) };
  }
  const riseOf = (account) => (account.startsWith("Expenses") ? "bad" : "good");

  // a rise over the average is a warning for spending, not for income
  const over = (a, s) => a.startsWith("Expenses") && avgOf(s) > 0 && s.at(-1) > avgOf(s) * 1.15;

  const income = $derived(flow("Income"));
  const expenses = $derived(flow("Expenses"));
  const net = $derived(income.map((v, i) => v - expenses[i]));
  const rates = $derived(income.map((v, i) => (v > 0 ? net[i] / v : 0)));
  const avgRate = $derived(
    income.length > 1 && sum(income.slice(0, -1)) > 0 ? sum(net.slice(0, -1)) / sum(income.slice(0, -1)) : null,
  );
  const worth = $derived(
    d?.accounts?.length ? d.window.map((_, i) => sum(d.accounts.map((a) => a.history[i]))) : null,
  );
  const runway = $derived(
    d?.runway?.baseline?.today ? { ...d.runway, months: d.runway.liquid / d.runway.baseline.today } : null,
  );
  // the explain skill's runway without investments: the liquid money outside Assets:*:Investments
  const cashOf = (r) =>
    r.liquid - sum((r.liquid_by_account ?? []).filter((a) => /^Assets:[^:]+:Investments(:|$)/.test(a.account)).map((a) => a.amount));
  const cash = $derived(runway && cashOf(runway));
  const level = (months) => (months >= d.goal ? "good" : months >= d.goal / 2 ? "warn" : "bad");
  const areas = $derived(d?.flows ? parts("Expenses").filter((c) => c.series.at(-1) > 0) : []);

  // the tiles: a main number, a line under it, the comparisons, a small chart, a state, and the detail they open;
  // `empty` says why data are missing
  const tiles = $derived.by(() => {
    if (!d) return [];
    const has = !!d.period;
    const top = areas[0];
    const w = worth?.length > 1 ? worth.at(-1) - worth.at(-2) : null;
    return [
      {
        id: "cashflow",
        title: t("cashFlow"),
        empty: !has && t("noData"),
        value: has && delta(net.at(-1)),
        sub: has && `${t("income")} ${eur(income.at(-1))} · ${t("expenses")} ${eur(expenses.at(-1))}`,
        compare: [
          prevOf(net) != null && [t(L.last), delta(prevOf(net))],
          avgOf(net) != null && [t(L.avg), delta(avgOf(net))],
        ],
        spark: { values: net, bars: true },
        state: has && (net.at(-1) < 0 ? "bad" : "good"),
        go: { name: "cashflow" },
      },
      {
        id: "category",
        title: t("topCategory"),
        empty: !top && t("noData"),
        value: top && eur(top.series.at(-1)),
        sub: top && `${name(top.account)} · ${pct(top.series.at(-1) / expenses.at(-1))} ${t("ofExpenses")}`,
        compare: [
          top && prevOf(top.series) != null && [t(L.last), eur(prevOf(top.series))],
          top && avgOf(top.series) != null && [t(L.avg), eur(avgOf(top.series))],
        ],
        spark: top && { values: top.series },
        state: top && over(top.account, top.series) ? "warn" : "",
        go: top && { name: "account", account: top.account },
      },
      {
        id: "networth",
        title: t("netWorth"),
        empty: !worth && t("noBalances"),
        value: worth && eur(worth.at(-1)),
        compare: [w != null && [t(L.during), `${delta(w)} (${pct(w / Math.abs(worth.at(-2)), "exceptZero")})`]],
        spark: worth && { values: worth },
        state: w != null && (w < 0 ? "warn" : "good"),
        go: { name: "networth" },
      },
      {
        id: "savings",
        title: t("savingsRate"),
        empty: !(income.at(-1) > 0) && t("noIncome"),
        value: pct(rates.at(-1)),
        compare: [avgRate != null && [t(L.avg), pct(avgRate)]],
        spark: { values: rates },
        state: rates.at(-1) < 0 ? "bad" : avgRate != null && rates.at(-1) < avgRate ? "warn" : "good",
        go: { name: "savings" },
      },
      {
        id: "runway",
        title: t("runway"),
        empty: !d.runway ? t("runwayMissing") : !runway && t("noExpenses"),
        value: runway && duration(runway.months),
        compare: [[t("goal"), `${d.goal} ${t("monthsShort")}`], runway && [t("liquid"), eur(runway.liquid)]],
        meter: runway && Math.min(runway.months / d.goal, 1),
        state: runway && level(runway.months),
        go: { name: "runway" },
      },
    ];
  });

  // the way back to the overview: an account's parents, or the report
  // a transaction: the way to the view it was opened from, then its day
  const crumbsOf = (v) => {
    if (v.name === "overview") return [];
    if (v.name === "txn") {
      const before = crumbsOf(v.parent);
      if (before.length) before.at(-1).view ??= v.parent;
      return [...before, { label: txn?.date ? fullDay(txn.date) : "…" }];
    }
    if (v.name === "txns") {
      const before = !v.account
        ? []
        : booked(v.account)
          ? [{ label: t("netWorth"), view: { name: "networth" } }]
          : path(v.account);
      return [...before, { label: t("transactions") }];
    }
    if (v.name === "tags") return [{ label: t("tags") }];
    if (v.name === "recurring") return [{ label: t("recurringPayments") }];
    if (v.name !== "account") return [{ label: tiles.find((x) => x.go?.name === v.name)?.title }];
    return path(v.account);
  };
  const crumbs = $derived(crumbsOf(view));
  // a pin's name on the rail: transactions by their filter (the rail's icon says they are transactions), else the title
  const pinLabel = (v) =>
    (v.name === "txns" && (v.payee ?? (v.account && name(v.account)) ?? (v.tag && `#${v.tag}`))) || crumbs.at(-1)?.label || t("overview");
  // an account and its parents, each to its detail
  const path = (account) =>
    account.split(":").map((_, i, p) => {
      const a = p.slice(0, i + 1).join(":");
      return { label: name(a), view: { name: "account", account: a } };
    });
  const booked = (account) => /^(Assets|Liabilities)(:|$)/.test(account);
  function up() {
    if (view.name === "txn") return go(view.parent);
    const parent = view.account?.split(":").slice(0, -1).join(":");
    if (view.name === "txns" && view.account)
      go(booked(view.account) ? { name: "networth" } : { name: "account", account: view.account });
    else go(view.name === "account" && parent ? { name: "account", account: parent } : { name: "overview" });
  }
  // Fava's page `path` in the Fava view used last, as a link in a terminal
  const fava = (path) => stepToFava(path, id);
  // Fava's journal of the transactions view's filter in the chosen period: Fava's filter takes a quoted string as a
  // case-insensitive regular expression on the payee and the narration
  function favaJournal() {
    let url = `/ledger/${listView.account ? `account/${listView.account}` : "journal"}/?time=${encodeURIComponent(listView.all ? "" : favaTime)}`;
    const filter = [listView.tag && `#${listView.tag}`];
    if (listView.payee) {
      const quote = listView.payee.includes('"') ? "'" : '"';
      filter.push(`${quote}^${listView.payee.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$${quote}`);
    }
    if (filter.some(Boolean)) url += `&filter=${encodeURIComponent(filter.filter(Boolean).join(" "))}`;
    fava(url);
  }
  // an account: its detail, or its transactions when it has no subaccounts
  function open(account, leaf = !children(account).length) {
    go(leaf ? { name: "txns", account } : { name: "account", account });
  }
  function pick(p) {
    // days of another period; a period chosen ends "all"
    if (view.days || view.all) view = { ...view, days: undefined, all: undefined };
    if (view.parent?.days || view.parent?.all) view = { ...view, parent: { ...view.parent, days: undefined, all: undefined } };
    period = p;
    load();
  }
  // from a month to its year, from a year to its December, or to the last full month in the year that is not over
  function setUnit(u) {
    if (listView.all) go({ ...listView, all: undefined, days: undefined });
    if (u === unit || !d?.period) return;
    period = u === "year" ? d.period.slice(0, 4) : d.months < 12 ? null : `${d.period}-12`;
    unit = u;
    load();
  }

  // the recurring payments: the payees the owner confirmed, the ones found that wait for a decision (suggested), and the
  // ones marked as not recurring (ignored), as rules.beancount says (server/edit.py set_recurring); each change with
  // Undo. A click on a payee: its payments over a year.
  const PERIOD_NAMES = { 1: "monthly", 3: "quarterly", 12: "yearly" };
  const perMonth = $derived(rec && `~${eur(rec.monthly)} ${t("aMonth")}`);
  const recOf = (payee) => rec?.payees.find((p) => p.payee === payee);
  const otherOf = (payee) => rec?.others.find((p) => p.payee === payee);
  const recIn = (state) => rec?.payees.filter((p) => p.state === state) ?? [];
  function openPayee(p) {
    unit = "year";
    pick(p.last.slice(0, 4));
    go({ name: "txns", payee: p.payee });
  }
  // what rules.beancount says of a payee now, as set_recurring takes it
  const markOf = (payee) => {
    const p = recOf(payee);
    if (p?.state === "confirmed") return [payee, "include", PERIOD_NAMES[p.period]];
    return [payee, p?.state === "ignored" ? "ignore" : null, null];
  };
  const confirm = (p) => [p.payee, "include", PERIOD_NAMES[p.period]];
  async function setRecurring(changes, message, undoable = true) {
    const before = changes.map(([payee]) => markOf(payee));
    const r = await rpc("recurring_set", { changes }).catch((e) => ({ error: String(e) }));
    if (r.error) toast(Message, { text: r.error }, { variant: "danger", duration: 0 });
    else if (undoable)
      toast(Message, { text: t(message), action: t("runwayUndo"), act: () => setRecurring(before, "", false) });
    loadRec();
  }

  async function load() {
    try {
      d = await rpc("dashboard", period ? { unit, period } : { unit });
    } catch {
      return; // no ledger's server yet: the start screen
    }
    loadTags();
  }
  // the recurring payments do not depend on the period: they load at the start and after the ledger changed
  function loadRec() {
    rpc("recurring")
      .then((r) => (rec = r))
      .catch(() => {});
  }
  const reload = () => (load(), loadRec());
  function loadTags() {
    rpc("tags")
      .then((r) => (tagged = r))
      .catch(() => {});
  }

  $effect(() => {
    untrack(reload); // once: a change of the period loads in pick(), not by running this again
    const off = listen("ledger-changed", reload);
    document.addEventListener("km-ledger", reload);
    // Esc goes one level up, ← and → to the previous and the next period, when the overview has the focus (not in a
    // terminal, where the keys are the program's)
    const key = (e) => {
      const here = root?.contains(e.target) || (e.target === document.body && dock?.activePanel?.id === id);
      if (!here || !visible(id) || e.target.closest?.("select, input")) return;
      if (e.key === "Escape" && view.name !== "overview") up();
      if (e.key === "ArrowLeft" && older) pick(older);
      if (e.key === "ArrowRight" && newer) pick(newer);
    };
    addEventListener("keydown", key);
    // back and forward: the view of that step, in front; a step into Fava shows that Fava view
    const pop = (e) => {
      if (e.state?.dashboard && (e.state.panel ?? "dashboard") === id) {
        for (const [f, from] of Object.entries(app.favaBack)) if (from === id) delete app.favaBack[f]; // back here
        view = e.state.dashboard;
        if (api) api.setActive();
        else showPart("dashboard");
      } else if (!api && favas.has(e.state?.fava)) dock.getPanel(e.state.fava).api.setActive();
    };
    if (!api && !history.state) history.replaceState({ dashboard: { name: "overview" } }, "");
    // a ledger's layout loaded (panels.js): the rail's overview where it was, or the overview of another ledger
    const restore = (e) => {
      if (api) return;
      const saved = e.detail ?? {};
      view = saved.view ?? { name: "overview" };
      unit = saved.unit ?? "month";
      period = saved.period ?? null;
      history.replaceState({ dashboard: $state.snapshot(view), panel: id }, "");
      reload();
    };
    document.addEventListener("km-overview", restore);
    // a view of the rail (rail.js showView), in this overview
    const goTo = (e) => {
      if (e.detail.panel !== id) return;
      if (JSON.stringify($state.snapshot(view)) !== JSON.stringify(e.detail.view)) go(e.detail.view);
      if (api) api.setActive();
      else showPart("dashboard");
    };
    document.addEventListener("km-go", goTo);
    // ⌘N (shortcuts.js): the transactions, with the form of a cash payment
    const cash = () => {
      if ((overviews.has(app.overview.id) ? app.overview.id : "dashboard") !== id) return;
      if (view.name !== "txns") go({ name: "txns" });
      cashing = true;
    };
    document.addEventListener("km-cash", cash);
    // an account's link in a terminal (fava.js openLink): its detail in the month or year of Fava's time filter
    const account = (e) => {
      if (api) return; // the rail's overview opens it
      const { account: a, time, path } = e.detail;
      if (!d?.period) return stepToFava(path);
      const p = time.match(/^\d{4}(-\d\d)?$/)?.[0];
      if (p && p !== d.period) {
        unit = p.length === 4 ? "year" : "month";
        pick(p);
      }
      if (booked(a)) go({ name: "txns", account: a });
      else open(a);
      showPart("dashboard");
    };
    document.addEventListener("km-account", account);
    addEventListener("popstate", pop);
    const panel = root;
    const back = (e) => e.button === 3 && history.back();
    panel.addEventListener("mouseup", back);
    return () => {
      off.then((unlisten) => unlisten());
      document.removeEventListener("km-ledger", reload);
      document.removeEventListener("km-account", account);
      document.removeEventListener("km-cash", cash);
      document.removeEventListener("km-overview", restore);
      document.removeEventListener("km-go", goTo);
      removeEventListener("keydown", key);
      removeEventListener("popstate", pop);
      panel.removeEventListener("mouseup", back);
    };
  });

  // the payees of the account that shows, in the chosen period
  $effect(() => {
    const account = view.account;
    const end = d?.ends?.at(-1);
    const start = unit === "year" ? `${d?.period}-01` : end;
    payees = null;
    if (!account || !end) return;
    rpc("transactions", { start, end, account })
      .then((r) => {
        if (view.account === account && d?.ends?.at(-1) === end) payees = r.merchants;
      })
      .catch(() => {});
  });

  // the transactions view: the chosen period, and the one before it (in a year that is not over, its same months)
  const range = $derived(
    d?.period && listView.all
      ? (({ first, last } = tagged?.tags.find((x) => x.tag === listView.tag) ?? {}) => ({
          start: first?.slice(0, 7) ?? firstMonth(), // a tag's months; else all the ledger's
          end: last?.slice(0, 7) ?? new Date().toISOString().slice(0, 7),
          prevStart: null,
          prevEnd: null,
        }))()
      : d?.period && {
      start: unit === "year" ? `${d.period}-01` : d.period,
      end: d.ends.at(-1),
      prevStart: d.window.length < 2 ? null : unit === "year" ? `${d.window.at(-2)}-01` : d.ends.at(-2),
      prevEnd: d.ends.at(-2),
    },
  );
  let asked = 0; // the last request: an older answer that comes later is dropped
  let rowsOf = ""; // the request whose rows show
  $effect(() => {
    if (listView.name !== "txns" || !range) return;
    const n = ++asked;
    const { prevStart, start, end } = range;
    const args = { start: prevStart ?? start, end, ...(listView.account && { account: listView.account }) };
    // other rows: none until they come; the same rows again (after a change): the old ones until then, no flash
    if (JSON.stringify(args) !== rowsOf) (rows = null), (chosen = []);
    rowsOf = JSON.stringify(args);
    rpc("transactions", args)
      .then((r) => n === asked && ((rows = r.rows), (listInfo = { editable: !!r.editable, accounts: r.accounts ?? [] })))
      .catch(() => {});
  });
  // spending as a positive number when the filter is an Expenses account, as the overview shows it
  const sign = $derived(listView.account?.startsWith("Expenses") ? -1 : 1);
  // a row's amount as it counts: a cash payment counts 0 (spent when withdrawn), but in a tag its amount, as the
  // tag's total (dashboard.spent): what the tag cost
  const amt = (r) => (listView.tag && r.cash != null ? r.cash : r.amount);
  const matches = (r) =>
    (!listView.tag || r.tags?.includes(listView.tag)) &&
    (!listView.payee || r.payee === listView.payee) &&
    (!search ||
      `${r.payee} ${r.narration} ${r.account} ${r.others.join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  // the days chosen in the chart: [first, last] (YYYY-MM-DD), inside the period
  const inDays = (r) => !listView.days || (r.date >= listView.days[0] && r.date <= listView.days[1]);
  // the rows of the period that match, the newest first, each with the sum from the period's start up to it
  const shown = $derived.by(() => {
    if (!rows) return null;
    let run = 0;
    return rows
      .filter((r) => r.date >= range.start && matches(r) && inDays(r))
      .map((r) => {
        const a = amt(r) * sign;
        return { ...r, amount: a, cash: listView.tag ? undefined : r.cash && r.cash * sign, run: (run += a) };
      })
      .reverse();
  });
  // the same filter in the period before
  const before = $derived(
    rows && range.prevStart && !listView.days
      ? sum(
          rows
            .filter((r) => r.date < range.start && r.date.slice(0, 7) <= range.prevEnd && matches(r))
            .map((r) => amt(r) * sign),
        )
      : null,
  );
  // The chart of the transactions view: what the filter (without its days) moved on each day of a month or in each
  // month of a year, its running total and the period before's; for an asset or a liability, its balance. `keys`: the
  // first and the last date of each bar, for the days a drag in the chart picks.
  const tchart = $derived.by(() => {
    if (!rows || !range) return null;
    const year = unit === "year";
    // "all": a bar for each month, for each year over 3 years (160 months of bars read as noise)
    const all = listView.all && monthsOf(range.start, range.end);
    const months = all && (all.length > 36 ? [...new Set(all.map((m) => m.slice(0, 4)))] : all); // YYYY-MM or YYYY
    const n = months ? months.length : year ? d.months : new Date(+range.end.slice(0, 4), +range.end.slice(5, 7), 0).getDate();
    const at = (date) => (months ? months.indexOf(date.slice(0, months[0].length)) + 1 : year ? +date.slice(5, 7) : +date.slice(8, 10)) - 1;
    const cur = Array(n).fill(0);
    const prev = Array(n).fill(0);
    const balance = listView.account && booked(listView.account);
    let start = null; // the balance before the period
    for (const r of rows) {
      if (r.date < range.start) start = r.balance ?? start;
      if (!matches(r) || at(r.date) >= n) continue;
      if (r.date >= range.start) cur[at(r.date)] += amt(r) * sign;
      else if (range.prevStart && r.date.slice(0, 7) <= range.prevEnd) prev[at(r.date)] += amt(r) * sign;
    }
    const first = rows.find((r) => r.date >= range.start);
    if (balance && start == null && first) start = first.balance - first.amount;
    const running = (s, from = 0) => s.map((v) => (from += v));
    // the running total up to the last day with data, not into the days after it
    const last = Math.max(...cur.map((v, i) => (v ? i : -1)));
    const line = running(cur, balance ? (start ?? 0) : 0).map((v, i) => (i <= last || balance ? v : null));
    const p = range.start.slice(0, 7);
    const pad = (i) => String(i + 1).padStart(2, "0");
    const keys = cur.map((_, i) =>
      months
        ? months[i].length === 4 ? [`${months[i]}-01-01`, `${months[i]}-12-31`] : [`${months[i]}-01`, `${months[i]}-31`]
        : year
        ? [`${d.period}-${pad(i)}-01`, `${d.period}-${pad(i)}-31`]
        : [`${p}-${pad(i)}`, `${p}-${pad(i)}`],
    );
    const label = (i) =>
      months ? periodShort(months[i]) : year ? date(`${d.period}-${pad(i)}`, { month: "short" }) : String(i + 1);
    const columns = [t(months ? (months[0].length === 4 ? "year" : "month") : unit), t("amount"), balance ? t("balance") : t("running")];
    if (!balance && range.prevStart) columns.push(t(L.last));
    const lastPrev = running(prev);
    return {
      columns,
      keys,
      rows: cur.map((v, i) => [label(i), v, line[i], ...(columns.length > 3 ? [lastPrev[i]] : [])]),
    };
  });
  // the ledger's first month, and the months from one to another (YYYY-MM)
  const firstMonth = () => (p => (p.length === 4 ? `${p}-01` : p))(d.periods.at(-1));
  function monthsOf(from, to) {
    const out = [];
    for (let y = +from.slice(0, 4), m = +from.slice(5, 7); `${y}-${String(m).padStart(2, "0")}` <= to; m === 12 ? (y++, (m = 1)) : m++)
      out.push(`${y}-${String(m).padStart(2, "0")}`);
    return out;
  }
  // what the rows that show moved by category (their account; the subaccounts of an account filter), the largest
  // first, with the share of the ones of the same sign: of the spending, or of the income. Not for an asset or a
  // liability: its rows are its own account.
  const categories = $derived.by(() => {
    if (!shown || (listView.account && booked(listView.account))) return [];
    const by = {};
    for (const r of shown) by[r.account] = (by[r.account] ?? 0) + r.amount;
    const list = Object.entries(by).map(([account, amount]) => ({ account, amount }));
    // Expenses, then Income, each with the share of its own total
    return ["Expenses", "Income"]
      .map((root) => {
        const items = list.filter((c) => c.account.split(":")[0] === root).sort((x, y) => Math.abs(y.amount) - Math.abs(x.amount));
        const all = sum(items.map((c) => c.amount));
        return { root, items: items.map((c) => ({ ...c, share: all && c.amount / all > 0 ? c.amount / all : null })) };
      })
      .filter((g) => g.items.length);
  });
  // a category's name under the account filter (or its root): Food:Groceries, not Groceries, which two may share
  const catName = (a) => a.slice((listView.account ?? a.split(":")[0]).length + 1) || name(a);
  const categoryCount = $derived(sum(categories.map((g) => g.items.length)));
  let allCategories = $state(false); // more than the first 8 of each group
  // a row's tooltip: what a click does, and how to choose rows for tags
  const rowTitle = $derived(listInfo.editable ? `${t("openTransaction")}. ${t("chooseRowsNote")}` : t("openTransaction"));
  // the categories and the chart, each folded or open; the app's setting
  const fold = $derived(app.appSettings.transactionsFold ?? {});
  function setFold(part, open) {
    if (!open === !!fold[part]) return;
    assign({ appSettings: { ...app.appSettings, transactionsFold: { ...fold, [part]: !open } } });
    invoke("save_app_settings", { settings: app.appSettings });
  }
  const dayName = (iso) => new Intl.DateTimeFormat(app.lang, { day: "numeric", month: "numeric" }).format(new Date(iso));
  // the sum of each day (YYYY-MM-DD) and month (YYYY-MM) that shows
  const sums = $derived.by(() => {
    const out = {};
    for (const r of shown ?? []) for (const k of [r.date, r.date.slice(0, 7)]) out[k] = (out[k] ?? 0) + r.amount;
    return out;
  });
  // the transactions as a list (a payee and what it is, the amounts on the right) or a table; the app's setting
  const layout = $derived(app.appSettings.transactions ?? "list");
  function setLayout(l) {
    assign({ appSettings: { ...app.appSettings, transactions: l } });
    invoke("save_app_settings", { settings: app.appSettings });
  }
  // The runway's baseline by `need` and account, from the saved query "Baseline by account": the groups in the
  // order accounts.beancount defines them; income-linked spending does not count, it stops with the income.
  const NEEDS = ["essential", "flexible", "optional", "unknown", "income-linked"];
  const groupBaseline = ({ columns, rows }) => {
    const at = (name) => columns.indexOf(name);
    const groups = {};
    for (const r of rows) {
      const need = [null, "None", ""].includes(r[at("need")]) ? "unknown" : String(r[at("need")]); // no need: str() of None
      const g = (groups[need] ??= { need, counted: need !== "income-linked", today: 0, reduced: 0, accounts: [] });
      const a = { account: r[at("account")], today: Number(r[at("today")] ?? 0), reduced: Number(r[at("reduced")] ?? 0) };
      if (!a.today && !a.reduced) continue;
      g.accounts.push(a);
      g.today += a.today;
      g.reduced += a.reduced;
    }
    const rank = (n) => (NEEDS.includes(n) ? NEEDS.indexOf(n) : NEEDS.length - 1);
    return Object.values(groups)
      .filter((g) => g.accounts.length)
      .sort((x, y) => rank(x.need) - rank(y.need));
  };
  let savedBaseline = $state(null);
  $effect(() => {
    savedBaseline = null;
    const bql = view.name === "runway" && d?.runway?.query;
    if (!bql) return;
    rpc("query", { bql })
      .then((res) => (savedBaseline = groupBaseline(res)))
      .catch(() => {});
  });

  // The runway's edit view: the accounts' liquid, need and cut (their `open` in accounts.beancount). Each change asks
  // the server for the runway with the edits (a preview, nothing written); Save writes them, and Undo writes the
  // values from before.
  let editing = $state(false);
  let edits = $state({}); // {account: {liquid | need | cut: value, null removes it}}, not saved
  let unedited = $state(null); // rpc("runway_edit") without edits: the values the preview compares with
  let preview = $state(null); // rpc("runway_edit") with the edits
  let editError = $state("");
  let dragCut = $state({}); // a cut slider's % while it moves; the preview's meta after
  $effect(() => {
    preview;
    dragCut = {};
  });
  let undo = $state(null); // after a save: what changed, and the edits that put the old values back
  // the values without edits, asked for when the runway shows (and again after the ledger changes): Edit opens at once
  let uneditedNext = null;
  $effect(() => {
    if (view.name !== "runway" || !d?.runway) return;
    uneditedNext = rpc("runway_edit");
    uneditedNext.catch(() => {});
  });
  const startEdit = () =>
    (uneditedNext ?? rpc("runway_edit"))
      .then((r) => ((unedited = preview = r), (edits = {}), (editError = ""), (undo = null), (editing = true)))
      .catch((e) => (editError = String(e)));
  $effect(() => {
    if (!editing) return;
    const changes = $state.snapshot(edits);
    if (!Object.keys(changes).length) return void (preview = unedited);
    rpc("runway_edit", { changes })
      .then((r) => ((preview = r), (editError = "")))
      .catch((e) => (editError = String(e)));
  });
  function setEdit(account, key, value) {
    const e = { ...edits[account] };
    if ((unedited.meta[account]?.[key] ?? null) === value) delete e[key];
    else e[key] = value;
    const { [account]: _, ...rest } = edits;
    edits = Object.keys(e).length ? { ...rest, [account]: e } : rest;
  }
  const inverse = (changes) =>
    Object.fromEntries(
      Object.entries(changes).map(([a, e]) => [a, Object.fromEntries(Object.keys(e).map((k) => [k, unedited.meta[a]?.[k] ?? null]))]),
    );
  // the agent proposes the runway's inputs and talks them through; the edits not saved yet go with the task
  function discuss() {
    const changes = Object.entries(editing ? edits : {})
      .map(([a, e]) => `${a} ${Object.entries(e).map(([k, v]) => `${k} ${v ?? "none"}`).join(", ")}`)
      .join("; ");
    const draft = changes ? tAgent("runwayDraft", { changes }) : "";
    tell(tAgent("runway", { draft }) + tAgent("save"), "", tAgent("beforeRunway"));
  }
  async function saveEdits(changes, back) {
    try {
      const r = await rpc("runway_save", { changes });
      editing = false;
      undo = back && { changed: r.changed ?? [], changes: back, error: r.error };
      await load();
    } catch (e) {
      editError = String(e);
    }
  }
  $effect(() => {
    if (view.name !== "runway") editing = false; // an edit not saved ends with the view
  });
  // what the runway's tables show: the preview while editing
  const rw = $derived(editing && preview ? preview : runway);
  const baseline = $derived(editing && preview ? groupBaseline(preview.by_account) : savedBaseline);
  const old = $derived(
    editing && unedited
      ? Object.fromEntries(groupBaseline(unedited.by_account).flatMap((g) => [[g.need, g], ...g.accounts.map((a) => [a.account, a])]))
      : {},
  );

  // a transaction's detail, its way back the view it was opened from
  const openTxn = (r) =>
    go({ name: "txn", hash: r.hash, id: r.id, parent: view.name === "txn" ? view.parent : $state.snapshot(view) });
  // whether a row is the transaction that shows: by its id, which a change keeps
  const isOpen = (r) => view.name === "txn" && (view.id ? view.id === r.id : view.hash === r.hash);
  const editInFava = (hash) => fava(`/ledger/journal/?time=${encodeURIComponent(favaTime)}#context-${hash}`);
  const statementOf = (hash) => fava(`/ledger/statement/?entry_hash=${hash}&key=document`);
  // after a change: the transaction's new hash in the same step of the history; the overview loads again
  // after a change: the transaction as the server gives it back, at once; the overview loads again behind it
  let renamed = null; // the new hash of the transaction a change saved: the view does not load it again
  function changed(hash, entry) {
    splitting = false;
    renamed = hash;
    if (entry) txn = entry;
    if (hash && hash !== view.hash) {
      view = { ...view, hash };
      history.replaceState({ dashboard: $state.snapshot(view), panel: id }, "");
    }
    load();
  }
  // the transaction view's transaction, again after the ledger changes
  $effect(() => {
    if (view.name !== "txn" || !d) return;
    const { hash, id: tid } = view;
    // another transaction (not the same one after a change): its change ends; the transaction before stays until
    // this one comes, so the detail does not flash "loading"
    const same = hash === renamed || untrack(() => (tid ? txn?.meta?.id === tid : txn?.hash === hash));
    if (!same) (picking = -1), (typing = null), (splitting = false);
    const n = saves;
    // by id: a transaction changed meanwhile is found again; asked before a change, or while one waits, it is old
    rpc("entry", tid ? { id: tid } : { hash })
      .then((e) => view.hash === hash && n === saves && !waiting && (txn = e))
      .catch(() => {});
  });
  const FEES = "Expenses:Bank:Fees";
  // a transaction's categories: the postings after the statement row, without the fee the import wrote beside the
  // category (x.fee, from the server); a fee a split by hand added is a category
  function categoriesOf(x) {
    const after = x.postings.slice(1);
    const fee = x.fee ? after.find((p) => p.account === FEES) : null;
    return after.filter((p) => p !== fee);
  }
  // as entry_save takes them: an amount on each but the last, which gets the rest
  const asPostings = (list) =>
    list.map((p, i) => (i < list.length - 1 ? { account: p.account, amount: String(Math.abs(p.number)) } : { account: p.account }));
  // Changes go to the server one after another, each to its transaction by `id`, which a change keeps (Fava's hash
  // changes with each): a second change made quickly never names a transaction that is gone. `saves` counts them, so
  // a transaction asked for before a change, which comes after it, does not replace the one the change gave back.
  let queue = Promise.resolve();
  let saves = 0;
  const refOf = (x) => ((x.id ?? x.meta?.id) ? { id: x.id ?? x.meta.id } : { hash: x.hash });
  const shows = (ref) => view.name === "txn" && txn && (ref.id ? txn.meta.id === ref.id : txn.hash === ref.hash);
  const problem = (text) => toast(Message, { text }, { variant: "danger", duration: 0 });
  // The transaction a change gives back shows only after the last change waiting: an earlier one's would replace
  // what was typed since, which shows already.
  let waiting = 0;
  let latest = null; // the last change's answer while others wait
  function save(method, ref, args = {}) {
    waiting++;
    const run = queue.then(async () => {
      saves++;
      const r = await rpc(method, { ...ref, ...args }).catch((e) => ({ error: String(e) }));
      saves++;
      waiting--;
      const problems = [r.error, ...(r.messages ?? [])].filter(Boolean);
      if (problems.length) problem(problems.join("\n"));
      if (r.hash !== undefined) latest = { ref, r };
      else if (!waiting) load(); // nothing written: the rows load again, without what showed before the save
      if (waiting) return r.hash === undefined ? null : r;
      const last = latest;
      latest = null;
      if (last?.r.entry && shows(last.ref)) changed(last.r.hash, last.r.entry);
      else if (last) load();
      return r.hash === undefined ? null : r;
    });
    queue = run.catch(() => {});
    return run;
  }
  // after a new category: Undo, and when it is the only one, the rule for the counterparty. Undo shows the old
  // categories at once (`show`), as the change showed the new ones, and saves them behind.
  function offerRule(ref, account, before, rule, show) {
    const undo = () => (show(), save("entry_save", ref, { postings: before }));
    if (rule) toast(RuleOffer, { ref, account, undo, apply: () => save("rule_save", ref, { account }) }, { duration: 0 });
    else toast(Message, { text: t("txnSaved"), action: t("runwayUndo"), act: undo });
  }
  async function pickCategory(i, account) {
    picking = -1;
    const list = categoriesOf(txn);
    if (list[i].account === account) return;
    const ref = refOf(txn);
    const before = asPostings(list);
    const postings = asPostings(list.map((p, j) => (j === i ? { ...p, account } : p)));
    list[i].account = account; // shows at once, with its message; the transaction the server gives back replaces it
    const saved = save("entry_save", ref, { postings });
    offerRule(ref, account, before, list.length === 1, () => {
      if (shows(ref)) categoriesOf(txn).forEach((p, j) => before[j] && (p.account = before[j].account));
    });
    // the error's toast replaced the message; a change typed since stays
    if (!(await saved) && !waiting && shows(ref)) list[i].account = before[i].account;
  }
  async function typed(key, value) {
    typing = null;
    const before = key === "payee" ? txn.payee : (txn.meta.note ?? "");
    if (value.trim() === before) return;
    const ref = refOf(txn);
    if (key === "payee") txn.payee = value.trim();
    else txn.meta.note = value.trim(); // shows at once, with its message; the transaction the server gives back replaces it
    const saved = save("entry_save", ref, { [key]: value });
    const undo = () => {
      if (shows(ref) && key === "payee") txn.payee = before;
      else if (shows(ref)) txn.meta.note = before; // shows at once, as the change did
      save("entry_save", ref, { [key]: before });
    };
    toast(Message, { text: t("txnSaved"), action: t("runwayUndo"), act: undo });
    if ((await saved) || waiting || !shows(ref)) return; // the error's toast replaced the message; a change since stays
    if (key === "payee") txn.payee = before;
    else txn.meta.note = before;
  }
  // Enter saves what was typed, Esc and a click elsewhere leave it
  function typingKey(e, key) {
    if (e.key === "Enter") typed(key, e.currentTarget.value);
    else if (e.key === "Escape") {
      e.stopPropagation();
      typing = null;
    }
  }
  const focus = (el) => el.focus();
  // back to the categories the rules give: kingsmint reset, then reimport
  let resetting = $state(false);
  async function reset() {
    resetting = true;
    await save("entry_reset", refOf(txn));
    resetting = false;
  }
  async function pickRow(r, account) {
    listPick = null;
    const before = accountOf(r);
    if (account === before) return;
    const ref = refOf(r);
    // shows at once; the rows loaded after the change replace it. The row by its id: a change gives it another hash
    const put = (a) => {
      const row = rows?.find((x) => (r.id ? x.id === r.id : x.hash === r.hash));
      if (row && booked(listView.account ?? "")) row.others = [a];
      else if (row) row.account = a;
    };
    put(account);
    save("entry_save", ref, { postings: [{ account }] }); // an error's toast replaces the message
    offerRule(ref, account, [{ account: before }], true, () => put(before));
  }
  // A tag on the transaction that shows: its chips show the transaction the server gives back, which has the tag as
  // the server wrote it (edit.tag_slug)
  const tagTxn = (args) => save("tags_save", refOf(txn), args);
  const keyOf = (r) => r.id ?? r.hash;
  const tagView = (tag) => ({ name: "txns", tag, all: true }); // a tag's transactions, over all its dates
  // ⌘ (Ctrl) click adds a row to the chosen ones or takes it away, Shift click chooses the rows from the last clicked
  // (with or without ⌘); true when the click chose, so the row does not open
  function choose(e, i) {
    const key = keyOf(shown[i]);
    const from = anchor;
    anchor = key;
    if (!(e.metaKey || e.ctrlKey || e.shiftKey) || !listInfo.editable) return false;
    e.preventDefault();
    const j = e.shiftKey ? shown.findIndex((r) => keyOf(r) === from) : -1;
    const keys = (j >= 0 ? shown.slice(Math.min(i, j), Math.max(i, j) + 1) : [shown[i]]).map(keyOf);
    const on = e.shiftKey || !chosen.includes(key);
    chosen = on ? [...new Set([...chosen, ...keys])] : chosen.filter((k) => !keys.includes(k));
    return true;
  }
  // all the rows that show, or those of them not chosen
  function chooseRows(how) {
    const keys = [...new Set(shown.map(keyOf))];
    chosen = how === "all" ? keys : keys.filter((k) => !chosen.includes(k));
  }
  // the tags of the chosen rows, each once, and the ledger's tags to suggest
  const chosenTags = $derived([...new Set((rows ?? []).filter((r) => chosen.includes(keyOf(r))).flatMap((r) => r.tags ?? []))].sort());
  const knownTags = $derived((tagged?.tags ?? []).map((x) => x.tag));
  async function tagChosen(args) {
    const items = chosen.map((k) => (rows.find((r) => keyOf(r) === k)?.id ? { id: k } : { hash: k }));
    const r = await save("tags_save", {}, { items, ...args });
    if (!r) return;
    // a row without an id (cash.beancount) is chosen by its hash, which the tag changed: it drops out of the choice
    chosen = chosen.filter((k) => rows.some((r) => r.id === k));
    toast(Message, { text: t(args.add ? "tagAdded" : "tagRemoved", { n: items.length }) });
  }
  // an amount in its own currency; a commodity that is not a currency (a fund) by its name
  function units(n, currency) {
    try {
      return fmt({ style: "currency", currency, maximumFractionDigits: 2 }).format(n);
    } catch {
      return `${fmt({ maximumFractionDigits: 4 }).format(n)} ${currency}`;
    }
  }
  const signed = (v) =>
    fmt({ style: "currency", currency: d.currency, minimumFractionDigits: 2, signDisplay: "exceptZero" }).format(v);
  // the account a row shows: the category of a bank account's transaction, else its account under the filter's
  const accountOf = (r) =>
    booked(listView.account ?? "") ? (r.others.find((o) => !booked(o)) ?? r.others[0] ?? "") : r.account;
  const short = (a) => (listView.account && a.startsWith(`${listView.account}:`) ? a.slice(listView.account.length + 1) : a);
  const filterAccounts = $derived(
    [
      ...new Set(
        [...Object.keys(d?.flows ?? {}), ...(d?.accounts ?? []).map((a) => a.account), listView.account].filter(Boolean),
      ),
    ].sort(),
  );
  const cents = (v) =>
    fmt({ style: "currency", currency: d.currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);
  const day = (iso) => new Intl.DateTimeFormat(app.lang, { day: "numeric", month: "short" }).format(new Date(iso));
  const fullDay = (iso) =>
    new Intl.DateTimeFormat(app.lang, { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
  // a tag's period: the dates of its first and last transaction
  const dates = (x) => (x.first === x.last ? fullDay(x.first) : `${fullDay(x.first)} – ${fullDay(x.last)}`);
  const shortDay = (iso) =>
    new Intl.DateTimeFormat(app.lang, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
  const longDay = (iso) =>
    new Intl.DateTimeFormat(app.lang, { weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));
</script>

<!-- the runway's edit view: the value before the edit, then the new one; one value when they are the same -->
{#snippet was(before, now, f)}{#if editing && before != null && Math.abs(before - now) > 0.005}<span class="muted"
      >{`${f(before)} → `}</span
    >{/if}{f(now)}{/snippet}
{#snippet chg(v, base, rise, total)}
  {@const c = change(v, base, rise, total)}
  {#if c}<small class="chg {c.cls}">{c.text}</small>{/if}
{/snippet}

{#snippet payeeButton(r)}
  <button
    type="button"
    class="pick"
    title={t("filterPayee")}
    onclick={(e) => {
      e.stopPropagation();
      go({ ...listView, payee: r.payee });
    }}>{r.payee}</button
  >
{/snippet}

{#snippet accountButton(r)}
  {#if accountOf(r)}
    <button
      type="button"
      class="pick"
      title={t("filterAccount")}
      onclick={(e) => {
        e.stopPropagation();
        go({ name: "txns", account: accountOf(r) });
      }}>{short(accountOf(r))}</button
    >
  {/if}
{/snippet}

<!-- a row's amount; a cash payment's (dashboard.transactions `cash`) is muted: it counts 0, spent when withdrawn -->
{#snippet amountOf(r)}
  {#if r.cash != null}
    <span class="muted" title={t("cashRowTitle")}>{t("cashRow")} {cents(r.cash)}</span>
  {:else}
    {sign === 1 && r.amount > 0 && layout === "list" ? "+" : ""}{cents(r.amount)}
  {/if}
{/snippet}

{#snippet tagButtons(r)}
  {#each r.tags ?? [] as tag}
    <button type="button" class="pick hashtag" title={t("openTag")}
      onclick={(e) => (e.stopPropagation(), go(tagView(tag)))}>#{tag}</button>
  {/each}
{/snippet}

{#snippet tagBars(list)}
  <ul class="bars tags">
    {#each list as x (x.tag)}
      <li>
        <button type="button" onclick={() => go(tagView(x.tag))}>
          <span class="name">#{x.tag}</span>
          <span class="bar"><span style:width="{Math.max(x.total / Math.max(...list.map((y) => y.total)), 0) * 100}%"></span></span>
          <span class="num">{cents(x.total)}</span>
          <span class="num muted">{dates(x)}</span>
        </button>
      </li>
    {/each}
  </ul>
{/snippet}

{#snippet statementButton(r)}
  {#if r.document}
    <button
      type="button"
      class="more"
      title={t("statement")}
      onclick={(e) => {
        e.stopPropagation();
        statementOf(r.hash);
      }}>{t(r.cash == null ? "statementShort" : "cashReceipt")}</button
    >
  {/if}
{/snippet}

{#snippet txnView()}
    {#if txn === undefined}
      <p class="muted">{t("loading")}</p>
    {:else if !txn}
      <p class="muted">
        {t("txnGone")} <button type="button" class="more" onclick={up}>{t("back")}</button>
      </p>
    {:else}
      {@const others = txn.history.filter((h) => h.hash !== txn.hash)}
      {@const avg = others.length ? sum(others.map((h) => h.amount)) / others.length : null}
      {@const cats = categoriesOf(txn)}
      {@const multi = txn.postings.some((q) => q.currency !== d.currency)}
      <div class="txn" class:stale={!isOpen({ id: txn.meta?.id, hash: txn.hash })}>
        <div class="headline">
          <div class="who">
            {#if typing === "payee"}
              <input class="inline title" type="text" value={txn.payee} aria-label={t("payee")} use:focus
                onkeydown={(e) => typingKey(e, "payee")} onblur={() => (typing = null)} />
            {:else if txn.editable}
              <h2><button type="button" class="editable" title={t("changePayee")} onclick={() => (typing = "payee")}
                >{txn.payee} <wa-icon name="pencil"></wa-icon></button></h2>
            {:else}
              <h2>{txn.payee}</h2>
            {/if}
            <span class="muted">
              {new Intl.DateTimeFormat(app.lang, { dateStyle: "full" }).format(new Date(txn.date))}{#if txn.narration && txn.narration !== txn.payee}{` · ${txn.narration}`}{/if}
            </span>
            {#if txn.flag === "!"}<span class="tag" title={t("flaggedTitle")}>{t("flagged")}</span>{/if}
            {#if recOf(txn.payee)?.state === "confirmed"}
              <button type="button" class="tag link-tag" title={t("recurringTitle")} onclick={() => go({ name: "recurring" })}
                >{t("recurring")}</button
              >
            {/if}
          </div>
          <strong>{txn.transfer ? cents(txn.amount) : signed(txn.amount)}</strong>
          {@render compare([
            txn.transfer && [t("kind"), t("transfer")],
            avg != null && [t("payeeAvg"), signed(avg)],
          ])}
          {#if avg != null && !txn.transfer}
            {@render chg(Math.abs(txn.amount), Math.abs(avg), txn.amount < 0 ? "bad" : "good", txn.amount)}
          {/if}
        </div>
        <div class="actions">
          {#if txn.statement}
            <button type="button" class="action" onclick={() => statementOf(txn.hash)}>{t("openStatement")} <wa-icon name="external-link"></wa-icon></button>
          {/if}
          <button type="button" class="action" onclick={() => editInFava(txn.hash)}>{t("editInFava")} <wa-icon name="external-link"></wa-icon></button>
          {@render markButton(txn.payee)}
          {#if listView !== view}
            <button type="button" class="action close" title={t("closeDetail")} onclick={up}
              ><wa-icon name="panel-right-close"></wa-icon> {t("close")}</button
            >
          {/if}
        </div>
        <div class="panels">
          <section>
            <h2 class="postings-head">
              {t("postings")}
              {#if txn.edited}
                <span class="tag" title={t("editedTitle")}>{t("editedByHand")}</span>
                <button type="button" class="more" title={t("byRulesTitle")} disabled={resetting} onclick={reset}
                  >{resetting ? t("ruleApplying") : t("byRules")}</button
                >
              {/if}
            </h2>
            {#if splitting}
              <TxnEdit {txn} save={(args) => save("entry_save", refOf(txn), args)} cancel={() => (splitting = false)} />
            {:else}
              <table class="postings">
                <tbody>
                  {#each txn.postings as p}
                    {@const i = cats.indexOf(p)}
                    {#if txn.editable && i >= 0}
                      <tr class="link cat-row" title={t("changeCategory")} onclick={() => (picking = i)}>
                        <td>
                          {#if picking === i}
                            <CategoryPicker accounts={txn.accounts} suggested={txn.suggested} value={p.account}
                              pick={(a) => pickCategory(i, a)} cancel={() => (picking = -1)} />
                          {:else}
                            <span class="cat">{p.account} <wa-icon name="pencil"></wa-icon></span>
                          {/if}
                        </td>
                        <td class="num">{units(p.number, p.currency)}</td>
                        {#if multi}<td class="num muted">{p.value == null ? "–" : cents(p.value)}</td>{/if}
                      </tr>
                    {:else}
                      <tr class="link" title={t("filterAccount")} onclick={() => go({ name: "txns", account: p.account })}>
                        <td>{p.account}</td>
                        <td class="num">{units(p.number, p.currency)}</td>
                        {#if multi}<td class="num muted">{p.value == null ? "–" : cents(p.value)}</td>{/if}
                      </tr>
                    {/if}
                  {/each}
                </tbody>
              </table>
              {#if txn.editable && cats.length && !multi}
                <button type="button" class="more" onclick={() => ((splitting = true), (picking = -1))}
                  >+ {t("splitMore")}</button
                >
              {/if}
            {/if}
            {#if txn.editable}
              <h2>{t("note")}</h2>
              {#if typing === "note"}
                <input class="inline" type="text" value={txn.meta.note ?? ""} aria-label={t("note")} use:focus
                  onkeydown={(e) => typingKey(e, "note")} onblur={() => (typing = null)} />
              {:else}
                <button type="button" class="editable note" class:muted={!txn.meta.note} onclick={() => (typing = "note")}
                  >{txn.meta.note || t("addNote")} <wa-icon name="pencil"></wa-icon></button
                >
              {/if}
            {/if}
            {#if txn.taggable || txn.tags?.length}
              <h2>{t("tags")}</h2>
              <TagField tags={txn.tags} known={knownTags} open={(tag) => go(tagView(tag))}
                add={txn.taggable ? (tag) => tagTxn({ add: tag }) : null}
                remove={txn.taggable ? (tag) => tagTxn({ remove: tag }) : null} />
            {/if}
            {#if Object.keys(txn.meta).some((k) => k !== "note" || !txn.editable)}
              <h2>{t("details")}</h2>
              <table>
                <tbody>
                  {#each Object.entries(txn.meta).filter(([k]) => k !== "note" || !txn.editable) as [k, v]}
                    <tr><td class="muted">{k}</td><td class="meta">{v}</td></tr>
                  {/each}
                </tbody>
              </table>
            {/if}
          </section>
          <section>
            <h2>
              {t("payeeHistory")}
              <span class="muted">{t("payeeCount", { n: txn.history.length })}</span>
            </h2>
            <ul class="txlist">
              {#each txn.history.slice(0, 12) as h (h.hash)}
                <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
                <li
                  class="item"
                  class:on={h.id ? h.id === txn.meta.id : h.hash === txn.hash}
                  role="button"
                  tabindex="0"
                  onclick={() => !isOpen(h) && openTxn(h)}
                  onkeydown={(e) => e.key === "Enter" && !isOpen(h) && openTxn(h)}
                >
                  <span class="main">{fullDay(h.date)}</span>
                  <span class="num amount">{signed(h.amount)}</span>
                </li>
              {/each}
            </ul>
            <button
              type="button"
              class="more"
              onclick={() => {
                // all the payee's transactions, not the period chosen before
                const account = view.parent?.name === "txns" ? view.parent.account : undefined;
                go({ name: "txns", account, payee: txn.payee, all: true });
              }}>{t("allOfPayee")} <wa-icon name="chevron-right"></wa-icon></button
            >
          </section>
        </div>
      </div>
    {/if}
{/snippet}

<!-- a transaction's payee confirmed as recurring: with the period its payments suggest, or the one picked when they
     suggest none (one payment) -->
{#snippet markButton(payee)}
  {@const p = recOf(payee)}
  {@const period = p?.period ?? otherOf(payee)?.period}
  {#if rec?.editable && (otherOf(payee) || (p && p.state !== "confirmed"))}
    {#if period}
      <button type="button" class="action" title={t("recurringMarkTitle")}
        onclick={() => setRecurring([[payee, "include", PERIOD_NAMES[period]]], "recurringConfirmed")}
        ><wa-icon name="repeat"></wa-icon> {t("recurringMark")}</button
      >
    {:else}
      <wa-dropdown>
        <button slot="trigger" type="button" class="action" title={t("recurringMarkTitle")}
          ><wa-icon name="repeat"></wa-icon> {t("recurringMark")} <wa-icon name="chevron-down"></wa-icon></button
        >
        {#each Object.values(PERIOD_NAMES) as w}
          <wa-dropdown-item onclick={() => setRecurring([[payee, "include", w]], "recurringConfirmed")}>{t(w)}</wa-dropdown-item>
        {/each}
      </wa-dropdown>
    {/if}
  {/if}
{/snippet}

<!-- a row of the recurring payments, as a transaction's in the list: the payee over its period and next payment, the
     usual amount over what it costs a month; what the owner can decide of it on the right -->
{#snippet recRow(p)}
  <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role: the row holds buttons, a button cannot -->
  <li class="item" class:faded={p.ended || p.state === "ignored"} role="button" tabindex="0" onclick={() => openPayee(p)}
    onkeydown={(e) => e.key === "Enter" && openPayee(p)}>
    <span class="main">
      <span class="title"><span class="name">{p.payee}</span>{@render recTags(p)}</span>
      <span class="sub">
        <span>{t(PERIOD_NAMES[p.period])}</span>
        <span>{p.ended ? t("recurringLastShort", { date: shortDay(p.last) }) : t("recurringNextShort", { date: shortDay(p.next) })}</span>
      </span>
    </span>
    <span class="rec-spark"><Spark values={p.amounts} span={p.typical / 5} /></span>
    <span class="trail">
      <span class="num amount">{eur(p.typical)}</span>
      {#if p.period > 1}<span class="num run">~{eur(p.typical / p.period)} {t("aMonth")}</span>{/if}
    </span>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions: only stops the row's click -->
    <span class="rec-actions" onclick={(e) => e.stopPropagation()}>
      {#if rec.editable && p.state === "ignored"}
        <button type="button" class="more" onclick={() => setRecurring([[p.payee, null, null]], "recurringRestored")}
          >{t("recurringRestore")}</button
        >
      {:else if rec.editable}
        {#if p.state === "suggested"}
          <button type="button" class="more" onclick={() => setRecurring([confirm(p)], "recurringConfirmed")}
            >{t("recurringConfirm")}</button
          >
        {/if}
        <wa-dropdown placement="bottom-end">
          <button slot="trigger" type="button" class="menu" title={t("recurringMenu")}
            ><wa-icon name="ellipsis" label={t("recurringMenu")}></wa-icon></button
          >
          <wa-dropdown-item onclick={() => setRecurring([[p.payee, "ignore", null]], "recurringHidden")}
            ><wa-icon slot="icon" name="eye-off"></wa-icon>{t("recurringHide")}</wa-dropdown-item
          >
        </wa-dropdown>
      {/if}
    </span>
  </li>
{/snippet}

{#snippet recTags(p)}
  {#if p.new}<span class="tag" title={t("recurringNewTitle")}>{t("recurringNew")}</span>{/if}
  {#if p.higher}<span class="tag" data-state="warn" title={t("recurringHigherTitle")}>{t("recurringHigher")}</span>{/if}
  {#if p.ended}<span class="tag" title={t("recurringEndedTitle")}>{t("recurringEnded")}</span>{/if}
  {#if p.manual}<span class="tag" title={t("recurringManualTitle")}>{t("recurringManual")}</span>{/if}
{/snippet}

{#snippet compare(list)}
  {#if list.some(Boolean)}
    <dl>
      {#each list.filter(Boolean) as [label, value]}<dt>{label}</dt><dd>{value}</dd>{/each}
    </dl>
  {/if}
{/snippet}

<div class="overview-scroll" bind:this={root} bind:clientWidth={width}>
<div class="dashboard" class:split={listView !== view}>
  <header>
    {#if view.name === "overview"}
      <h1>{t("overview")}</h1>
    {:else}
      <nav class="crumbs">
        <button type="button" onclick={() => go({ name: "overview" })}>{t("overview")}</button>
        {#each crumbs as c, i}
          <span class="sep"><wa-icon name="chevron-right"></wa-icon></span>
          {#if i < crumbs.length - 1}
            <button type="button" onclick={() => go(c.view)}>{c.label}</button>
          {:else}
            <h1>{c.label}</h1>
          {/if}
        {/each}
        <!-- ★ pins the view on the rail; the rail's own views have their buttons there -->
        {#if pinOf(view) >= 0 || !Object.values(VIEWS).some((v) => pinKey(v) === pinKey(view))}
        <button
          type="button"
          class="pin"
          class:on={pinOf(view) >= 0}
          title={t(pinOf(view) >= 0 ? "unpinView" : "pinView")}
          onclick={() => togglePin(view, pinLabel(view))}
          ><wa-icon name="star"></wa-icon></button
        >
        {/if}
      </nav>
    {/if}
    {#if d?.periods?.length && view.name !== "tags" && view.name !== "recurring"}<!-- the tags' list: each tag over all its dates -->
      <div class="period">
        {#if !listView.all && unit === "year" && d.months < 12}
          <span class="muted">{t("ytd", { months: date(d.ends.at(-1), { month: "long" }) })}</span>
        {/if}
        <!-- All: the transactions of all the ledger's months (a tag's: its months); the transactions view only -->
        <wa-radio-group orientation="horizontal" size="small" value={listView.all ? "all" : unit}
          onchange={(e) => (e.currentTarget.value === "all" ? go({ ...listView, all: true, days: undefined }) : setUnit(e.currentTarget.value))}>
          {#if listView.name === "txns"}<wa-radio appearance="button" value="all">{t("allTime")}</wa-radio>{/if}
          <wa-radio appearance="button" value="month">{t("month")}</wa-radio>
          <wa-radio appearance="button" value="year">{t("year")}</wa-radio>
        </wa-radio-group>
        {#if !listView.all}
          <button type="button" class="arrow" disabled={!older} title={t("previous")} onclick={() => pick(older)}><wa-icon name="chevron-left"></wa-icon></button>
          <select value={d.period} onchange={(e) => pick(e.target.value)}>
            {#each d.periods as p}<option value={p}>{periodName(p)}</option>{/each}
          </select>
          <button type="button" class="arrow" disabled={!newer} title={t("next")} onclick={() => pick(newer)}><wa-icon name="chevron-right"></wa-icon></button>
        {/if}
      </div>
    {/if}
  </header>

  {#if !d?.period}
    <p class="muted">{t("noData")}</p>
  {:else if view.name === "overview"}
    <div class="tiles">
      {#each tiles as tile (tile.id)}
        <button
          type="button"
          class="tile"
          data-state={tile.empty ? "" : tile.state || ""}
          disabled={!tile.go || !!tile.empty}
          onclick={() => go(tile.go)}
        >
          <span class="title">{tile.title}</span>
          {#if tile.empty}
            <span class="empty">{tile.empty}</span>
          {:else}
            <strong>{tile.value}</strong>
            {#if tile.sub}<span class="sub">{tile.sub}</span>{/if}
            {#if tile.spark}<Spark {...tile.spark} />{/if}
            {#if tile.meter != null}
              <span class="meter"><span style:width="{tile.meter * 100}%"></span></span>
            {/if}
            {@render compare(tile.compare)}
          {/if}
        </button>
      {/each}
    </div>

    <div class="panels">
      <section class="card">
        <h2>
          <button type="button" class="more" onclick={() => go({ name: "cashflow" })}>{t("cashFlow")} <wa-icon name="chevron-right"></wa-icon></button>
          <span class="muted">{t(L.window)}</span>
        </h2>
        <Chart
          type="bar"
          columns={[t(unit), t("net")]}
          colors={[FAVA[6], FAVA[3]]}
          bySign
          unit={money}
          rows={d.window.map((m, i) => [periodShort(m), net[i]])}
          onselect={(i) => pick(d.window[i])}
        />
      </section>
      <section class="card">
        <h2>
          <button type="button" class="more" onclick={() => open("Expenses", false)}>{t("whereMoney")} <wa-icon name="chevron-right"></wa-icon></button>
          <span class="muted">{periodName(d.period)}</span>
        </h2>
        <ul class="bars">
          {#each areas.slice(0, 8) as c (c.account)}
            {@const avg = avgOf(c.series)}
            <li>
              <button type="button" onclick={() => open(c.account, c.leaf)}>
                <span class="name">{name(c.account)}</span>
                <span class="bar"><span style:width="{(c.series.at(-1) / areas[0].series.at(-1)) * 100}%"></span></span>
                <span class="num">{eur(c.series.at(-1))}</span>
                <span class="num" title={avg == null ? "" : `${t(L.avg)}: ${eur(avg)}`}
                  >{@render chg(c.series.at(-1), avg, "bad", expenses.at(-1))}</span
                >
              </button>
            </li>
          {/each}
        </ul>
        <p class="muted note">{t(L.note)}</p>
        {#if d.cash?.withdrawn || d.cash?.entered}
          <!-- cash: withdrawn, entered in cash.beancount, and the rest that stays in Expenses:Cash -->
          <p class="muted note">
            <button type="button" class="more" onclick={() => go({ name: "txns", account: "Expenses:Cash" })}
              >{t("cashLine", { withdrawn: eur(d.cash.withdrawn), entered: eur(d.cash.entered),
                rest: eur(d.cash.withdrawn - d.cash.entered) })}</button
            >
          </p>
        {/if}
      </section>
      {#if rec?.payees.length}
        {@const confirmed = recIn("confirmed").filter((p) => !p.ended)}
        {@const waiting = recIn("suggested").length}
        <section class="card">
          <h2>
            <button type="button" class="more" onclick={() => go({ name: "recurring" })}>{t("recurringPayments")} <wa-icon name="chevron-right"></wa-icon></button>
            {#if confirmed.length}<span class="muted">{perMonth}</span>{/if}
          </h2>
          <ul class="bars rec">
            {#each confirmed.slice(0, 8) as p (p.payee)}
              <li>
                <button type="button" onclick={() => openPayee(p)}>
                  <span class="name">{p.payee}{@render recTags(p)}</span>
                  <span class="muted">{t(PERIOD_NAMES[p.period])}</span>
                  <span class="num">{eur(p.typical)}</span>
                </button>
              </li>
            {/each}
          </ul>
          {#if waiting}
            <button type="button" class="more" onclick={() => ((showSuggested = true), go({ name: "recurring" }))}
              >{t("recurringWaiting", { n: waiting })} <wa-icon name="chevron-right"></wa-icon></button
            >
          {/if}
        </section>
      {/if}
    </div>
    {#if tagged?.tags?.length}
      <div class="panels">
        <section class="card">
          <h2>
            <button type="button" class="more" onclick={() => go({ name: "tags" })}>{t("tags")} <wa-icon name="chevron-right"></wa-icon></button>
            <span class="muted">{t("tagsAllTime")}</span>
          </h2>
          {@render tagBars(tagged.tags.slice(0, 5))}
        </section>
      </div>
    {/if}
  {:else if view.name === "tags"}
    {#if !tagged}
      <p class="muted">{t("loading")}</p>
    {:else if !tagged.tags.length}
      <p class="muted">{t("noTags")}</p>
    {:else}
      <table class="tag-list">
        <thead>
          <tr><th>{t("tag")}</th><th class="num">{t("spent")}</th><th class="num">{t("transactions")}</th><th>{t("tagDates")}</th></tr>
        </thead>
        <tbody>
          {#each tagged.tags as x (x.tag)}
            <tr class="link" onclick={() => go(tagView(x.tag))}>
              <td>#{x.tag}</td><td class="num">{cents(x.total)}</td><td class="num">{x.count}</td>
              <td class="muted">{dates(x)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
    <p class="muted note">{t("tagsNote")}</p>
  {:else if view.name === "account"}
    {@const s = flow(view.account)}
    {@const list = parts(view.account)}
    <div class="headline">
      <strong>{eur(s.at(-1))}</strong>
      {@render compare([
        prevOf(s) != null && [t(L.last), eur(prevOf(s))],
        avgOf(s) != null && [t(L.avg), eur(avgOf(s))],
      ])}
      <button type="button" class="more" onclick={() => go({ name: "txns", account: view.account })}
        >{t("transactions")} <wa-icon name="chevron-right"></wa-icon></button
      >
    </div>
    <Chart
      type="bar"
      columns={[t(unit), name(view.account)]}
      colors={[FAVA[0]]}
      unit={money}
      average={avgOf(s)}
      rows={d.window.map((m, i) => [periodShort(m), s[i]])}
      onselect={(i) => pick(d.window[i])}
    />
    {#if list.length}
      <table>
        <thead>
          <tr>
            <th>{t("category")}</th><th class="num">{periodName(d.period)}</th><th class="num">{t("share")}</th>
            <th class="num" colspan="2">{t(L.vsLast)}</th><th class="num" colspan="2">{t("vsAverage")}</th>
            <th class="spark-col">{t(L.window)}</th>
          </tr>
        </thead>
        <tbody>
          {#each list as c (c.account)}
            {@const v = c.series.at(-1)}
            <tr class="link" onclick={() => open(c.account, c.leaf)}>
              <td>{name(c.account)}</td>
              <td class="num">{eur(v)}</td>
              <td class="num">{s.at(-1) > 0 ? pct(v / s.at(-1)) : "–"}</td>
              <td class="num">{prevOf(c.series) == null ? "–" : delta(v - prevOf(c.series))}</td>
              <td class="pct">{@render chg(v, prevOf(c.series), riseOf(c.account), s.at(-1))}</td>
              <td class="num">{avgOf(c.series) == null ? "–" : delta(v - avgOf(c.series))}</td>
              <td class="pct">{@render chg(v, avgOf(c.series), riseOf(c.account), s.at(-1))}</td>
              <td class="spark-col"><Spark values={c.series} span={Math.max(...s.map(Math.abs)) / 10} /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
    {#if payees?.length}
      <h2>{t("topPayees")}</h2>
      <table>
        <thead><tr><th>{t("payee")}</th><th class="num">{t("count")}</th><th class="num">{t("amount")}</th></tr></thead>
        <tbody>
          {#each [...payees].sort((x, y) => Math.abs(y.amount) - Math.abs(x.amount)).slice(0, 10) as p}
            <tr class="link" onclick={() => go({ name: "txns", account: view.account, payee: p.payee })}>
              <td>{p.payee}{#if p.recurring}<span class="tag" title={t("recurringTitle")}>{t("recurring")}</span>{/if}</td>
              <td class="num">{p.count}</td>
              <td class="num">{eur(riseOf(view.account) === "bad" ? -p.amount : p.amount)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {:else if view.name === "recurring" && rec}
    {@const suggested = recIn("suggested")}
    {@const hidden = recIn("ignored")}
    <div class="headline">
      <strong>{perMonth}</strong>
      <span class="muted">{t("recurringNote")}</span>
      {#if rec.editable && !adding}
        <wa-button class="more" size="small" appearance="filled" onclick={() => (adding = { payee: "", period: "monthly" })}
          ><wa-icon slot="start" name="plus"></wa-icon>{t("recurringAdd")}</wa-button
        >
      {/if}
    </div>
    {#if adding}
      {@const other = otherOf(adding.payee)}
      <form
        class="edit-bar rec-add"
        onsubmit={(e) => {
          e.preventDefault();
          setRecurring([[adding.payee, "include", adding.period]], "recurringAdded");
          adding = null;
        }}
      >
        <input type="text" list="rec-others" placeholder={t("payee")} aria-label={t("payee")} bind:value={adding.payee} use:focus
          oninput={() => otherOf(adding.payee)?.period && (adding.period = PERIOD_NAMES[otherOf(adding.payee).period])}
          onkeydown={(e) => e.key === "Escape" && (adding = null)} />
        <datalist id="rec-others">
          {#each rec.others as o (o.payee)}<option value={o.payee}></option>{/each}
        </datalist>
        <select bind:value={adding.period} aria-label={t("recurringPeriod")}>
          {#each Object.values(PERIOD_NAMES) as w}<option value={w}>{t(w)}</option>{/each}
        </select>
        <span class="muted">{other ? t("recurringCount", { n: other.count }) : ""}</span>
        <wa-button size="small" appearance="filled" onclick={() => (adding = null)}>{t("cancel")}</wa-button>
        <wa-button size="small" variant="brand" type="submit" disabled={!other}>{t("recurringAdd")}</wa-button>
      </form>
    {/if}
    {@const open = showSuggested ?? !recIn("confirmed").length}
    <ul class="txlist rec-list">
      {#each recIn("confirmed") as p (p.payee)}{@render recRow(p)}{:else}
        <li class="empty muted">{t("recurringNoneConfirmed")}</li>
      {/each}
      {#if suggested.length}
        <li class="month">
          <button type="button" class="pick" onclick={() => (showSuggested = !open)}
            ><wa-icon name={open ? "chevron-down" : "chevron-right"}></wa-icon> {t("recurringSuggested")} ({suggested.length})</button
          >
          {#if rec.editable && open}
            <button type="button" class="more" onclick={() => setRecurring(suggested.map(confirm), "recurringConfirmed")}
              >{t("recurringConfirmAll")}</button
            >
          {/if}
        </li>
        {#if open}
          <li class="empty muted">{t("recurringSuggestedNote")}</li>
          {#each suggested as p (p.payee)}{@render recRow(p)}{/each}
        {/if}
      {/if}
      {#if hidden.length}
        <li class="month">
          <button type="button" class="pick" onclick={() => (showHidden = !showHidden)}
            ><wa-icon name={showHidden ? "chevron-down" : "chevron-right"}></wa-icon> {t("recurringHiddenList")} ({hidden.length})</button
          >
        </li>
        {#if showHidden}{#each hidden as p (p.payee)}{@render recRow(p)}{/each}{/if}
      {/if}
    </ul>
  {:else if view.name === "cashflow"}
    <Chart
      type="bar"
      columns={[t(unit), t("income"), t("expenses")]}
      colors={[FAVA[6], FAVA[3]]}
      unit={money}
      rows={d.window.map((m, i) => [periodShort(m), income[i], expenses[i]])}
      onselect={(i) => pick(d.window[i])}
    />
    <table>
      <thead>
        <tr>
          <th>{t(unit)}</th><th class="num">{t("income")}</th><th class="num">{t("expenses")}</th>
          <th class="num">{t("net")}</th>
        </tr>
      </thead>
      <tbody>
        {#each d.window.map((m, i) => i).reverse() as i}
          <tr
            class="link"
            class:on={d.window[i] === d.period}
            onclick={() => {
              pick(d.window[i]);
              go({ name: "account", account: "Expenses" });
            }}
          >
            <td>{periodName(d.window[i])}</td>
            <td
              class="num"
              onclick={(e) => {
                e.stopPropagation();
                pick(d.window[i]);
                go({ name: "account", account: "Income" });
              }}>{eur(income[i])}</td
            >
            <td class="num">{eur(expenses[i])}</td>
            <td class="num" data-state={net[i] < 0 ? "bad" : ""}>{delta(net[i])}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else if view.name === "networth" && worth}
    <Chart
      type="line"
      columns={[t(unit), t("netWorth")]}
      unit={money}
      rows={d.window.map((m, i) => [periodShort(m), worth[i]])}
      onselect={(i) => pick(d.window[i])}
    />
    <table>
      <thead>
        <tr>
          <th>{t("account")}</th><th class="num">{t("balance")}</th><th class="num" colspan="2">{t(L.vsLast)}</th>
          <th class="spark-col">{t(L.window)}</th>
        </tr>
      </thead>
      <tbody>
        {#each KINDS as kind}
          {@const group = d.accounts.filter((a) => a.kind === kind)}
          {#if group.length}
            {@const total = group.map((a) => a.history).reduce((x, h) => x.map((v, i) => v + h[i]))}
            <tr class="group">
              <td>{t(`kind_${kind}`)}</td>
              <td class="num">{eur(total.at(-1))}</td>
              <td class="num">{prevOf(total) == null ? "–" : delta(total.at(-1) - prevOf(total))}</td>
              <td class="pct">{@render chg(total.at(-1), prevOf(total), "good", worth.at(-1))}</td>
              <td class="spark-col"><Spark values={total} span={worth.at(-1) / 20} /></td>
            </tr>
            {#each group as a}
              <tr class="link" onclick={() => go({ name: "txns", account: a.account })}>
                <td class="indent">{a.account.split(":").slice(1).join(":")}</td>
                <td class="num">{eur(a.history.at(-1))}</td>
                <td class="num">{prevOf(a.history) == null ? "–" : delta(a.history.at(-1) - prevOf(a.history))}</td>
                <td class="pct">{@render chg(a.history.at(-1), prevOf(a.history), "good", worth.at(-1))}</td>
                <td class="spark-col"><Spark values={a.history} span={worth.at(-1) / 20} /></td>
              </tr>
            {/each}
          {/if}
        {/each}
      </tbody>
    </table>
  {:else if view.name === "savings"}
    <Chart
      type="bar"
      columns={[t(unit), t("savingsRate")]}
      colors={[FAVA[6], FAVA[3]]}
      bySign
      unit={PERCENT}
      average={avgRate == null ? null : avgRate * 100}
      rows={d.window.map((m, i) => [periodShort(m), Math.round(rates[i] * 1000) / 10])}
      onselect={(i) => pick(d.window[i])}
    />
    {#if prevOf(income) != null}
      <h2>{t("moved")}</h2>
      <table>
        <tbody>
          <tr class="link" onclick={() => open("Income", false)}>
            <td>{t("income")}</td><td class="num">{delta(income.at(-1) - prevOf(income))}</td>
          </tr>
          {#each [...areas]
            .sort((x, y) => Math.abs(y.series.at(-1) - prevOf(y.series)) - Math.abs(x.series.at(-1) - prevOf(x.series)))
            .slice(0, 5) as c}
            <tr class="link" onclick={() => open(c.account, false)}>
              <td>{name(c.account)}</td>
              <td class="num">{delta(-(c.series.at(-1) - prevOf(c.series)))}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p class="muted note">{t("movedNote")}</p>
    {/if}
  {:else if listView.name === "txns"}
    {@const total = shown && sum(shown.map((r) => r.amount))}
    <div class="panes">
    <div class="pane">
    <div class="filter" role="search">
      <label class="chip">
        <span>{t("account")}</span>
        <select
          value={listView.account ?? ""}
          onchange={(e) => go({ ...listView, account: e.target.value || undefined, days: undefined })}
        >
          <option value="">{t("allIncomeExpenses")}</option>
          {#each filterAccounts as a}<option value={a}>{a}</option>{/each}
        </select>
      </label>
      {#if listView.payee}
        <span class="chip">
          <span>{t("payee")}</span>
          <b>{listView.payee}</b>
          <button type="button" title={t("removeFilter")} onclick={() => go({ ...listView, payee: undefined })}><wa-icon name="x"></wa-icon></button>
        </span>
      {/if}
      <!-- a tag: its transactions over all its months; chosen, a chip as the payee's; else a menu of the tags -->
      {#if listView.tag}
        <span class="chip">
          <span>{t("tag")}</span>
          <b>#{listView.tag}</b>
          <button type="button" title={t("removeFilter")} onclick={() => go({ ...listView, tag: undefined })}><wa-icon name="x"></wa-icon></button>
        </span>
      {:else if tagged?.tags?.length}
        <wa-dropdown distance="6" onwa-select={(e) => go({ ...listView, tag: e.detail.item.value, all: true, days: undefined })}>
          <button slot="trigger" type="button" class="chip pick-tag"
            ><span>{t("tag")}</span><wa-icon name="chevron-down"></wa-icon></button
          >
          {#each tagged.tags as x (x.tag)}
            <wa-dropdown-item value={x.tag}>#{x.tag}<span slot="details" class="muted">{cents(x.total)}</span></wa-dropdown-item>
          {/each}
        </wa-dropdown>
      {/if}
      {#if listView.days}
        <span class="chip">
          <span>{t("days")}</span>
          <b>{listView.days[0] === listView.days[1] ? dayName(listView.days[0]) : `${dayName(listView.days[0])} – ${dayName(listView.days[1])}`}</b>
          <button type="button" title={t("removeFilter")} onclick={() => go({ ...listView, days: undefined })}><wa-icon name="x"></wa-icon></button>
        </span>
      {/if}
      <input type="search" placeholder={t("searchTransactions")} bind:value={search} />
      <button type="button" class="more" onclick={favaJournal}>Fava <wa-icon name="external-link"></wa-icon></button>
    </div>
    {#if shown}
      <div class="headline">
        <!-- an asset or a liability: its balance at the period's end, then what the filtered transactions moved -->
        {#if listView.account && booked(listView.account)}
          <strong>{eur(rows.at(-1)?.balance)}</strong>
        {:else}
          <strong>{listView.account ? eur(total) : delta(total)}</strong>
        {/if}
        {@render compare([
          listView.account && booked(listView.account) && [t(listView.all ? "allTime" : L.during), delta(total)],
          [t("transactions"), shown.length],
          before != null && [t(L.last), listView.account && !booked(listView.account) ? eur(before) : delta(before)],
        ])}
        {#if before != null}{@render chg(total, before, listView.account ? riseOf(listView.account) : "good", total)}{/if}
        {#if sign === 1}
          <span class="muted"
            >{t("in")} {eur(sum(shown.filter((r) => r.amount > 0).map((r) => r.amount)))} · {t("out")}
            {eur(-sum(shown.filter((r) => r.amount < 0).map((r) => r.amount)))}</span
          >
        {/if}
      </div>
      <!-- the chart, then the categories (expenses beside income); each can be folded -->
      <div class="tx-parts">
        {#if tchart}
          <details class="fold txchart" open={!fold.chart} ontoggle={(e) => setFold("chart", e.currentTarget.open)}>
            <summary>{t("chart")}</summary>
            <Chart
              type="bar"
              columns={tchart.columns}
              rows={tchart.rows}
              colors={[FAVA[0], FAVA[3]]}
              bySign={sign === 1}
              lines={tchart.columns.slice(2)}
              dashed={tchart.columns.slice(3)}
              lineScale={!!listView.account && booked(listView.account)}
              unit={money}
              range={listView.days &&
                [tchart.keys.findIndex((k) => k[1] >= listView.days[0]), tchart.keys.findLastIndex((k) => k[0] <= listView.days[1])]}
              onrange={(i, j) =>
                go({ ...listView, days: i == null ? undefined : [tchart.keys[i][0], tchart.keys[j][1]] })}
            />
            <p class="muted note">{t("dragDays")}</p>
          </details>
        {/if}
        {#if categoryCount > 1}
          <details class="fold cats" open={!fold.categories} ontoggle={(e) => setFold("categories", e.currentTarget.open)}>
            <summary>{t("byCategory")}</summary>
            <div class="cat-groups wa-grid wa-gap-xl"><!-- side by side, one under the other when narrow -->
              {#each categories as g (g.root)}
                <table>
                  {#if categories.length > 1}
                    <thead><tr class="group"><td colspan="3">{t(g.root.toLowerCase())}</td></tr></thead>
                  {/if}
                  <tbody>
                    {#each allCategories ? g.items : g.items.slice(0, 8) as c (c.account)}
                      <tr class="link" title={`${c.account}: ${t("filterAccount")}`}
                        onclick={() => go({ ...listView, account: c.account, days: undefined })}>
                        <td>{catName(c.account)}</td><td class="num">{cents(c.amount)}</td>
                        <td class="num muted">{c.share == null ? "–" : pct(c.share)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/each}
            </div>
            {#if categories.some((g) => g.items.length > 8)}
              <button type="button" class="more" onclick={() => (allCategories = !allCategories)}
                >{allCategories
                  ? t("fewerCategories")
                  : t("moreCategories", { n: sum(categories.map((g) => Math.max(g.items.length - 8, 0))) })}</button>
            {/if}
          </details>
        {/if}
      </div>
      {#if shown.length || listInfo.editable}
        <!-- the list's own header: a cash payment and its layout beside it, not among the filters -->
        <div class="list-head wa-split">
          <span>
            {t("transactions")}
            {#if listInfo.editable && shown.length}<button type="button" class="more" onclick={() => chooseRows("all")}>{t("chooseAll")}</button>{/if}
          </span>
          <div class="wa-cluster wa-gap-s">
            {#if listInfo.editable && !cashing}
              <wa-button size="small" variant="brand" appearance="outlined" title={t("cashTitle")} onclick={() => (cashing = true)}
                ><wa-icon slot="start" name="plus"></wa-icon>{t("cashAdd")}</wa-button
              >
            {/if}
            {#if shown.length}
              <wa-radio-group orientation="horizontal" size="small" value={layout} onchange={(e) => setLayout(e.currentTarget.value)}>
                <wa-radio appearance="button" value="list">{t("asList")}</wa-radio>
                <wa-radio appearance="button" value="table">{t("asTable")}</wa-radio>
              </wa-radio-group>
            {/if}
          </div>
        </div>
      {/if}
      {#if chosen.length}
        <div class="edit-bar sticky tag-bar">
          <span>{t("chosenRows", { n: chosen.length })}</span>
          <TagField tags={chosenTags} known={knownTags} add={(tag) => tagChosen({ add: tag })}
            remove={(tag) => tagChosen({ remove: tag })} />
          <wa-button size="small" appearance="plain" onclick={() => chooseRows("invert")}>{t("invertChoice")}</wa-button>
          <wa-button size="small" appearance="filled" onclick={() => (chosen = [])}>{t("cancel")}</wa-button>
        </div>
      {/if}
      <!-- a cash payment: its form above the rows, the payment then in the rows below -->
      {#if cashing && listInfo.editable}
        <CashEntry accounts={listInfo.accounts} done={cashDone} />
      {/if}
      {#if shown.length && layout === "list"}
        <!-- the days, the newest first, each with its sum; a row: the payee over what it is, the amount over the
             running total -->
        <ul class="txlist">
          {#each shown as r, i (i)}
            {@const m = r.date.slice(0, 7)}
            {#if (listView.all || unit === "year") && (i === 0 || shown[i - 1].date.slice(0, 7) !== m)}
              <li class="month"><span>{periodName(m)}</span><span class="num">{cents(sums[m])}</span></li>
            {/if}
            {#if i === 0 || shown[i - 1].date !== r.date}
              <!-- a day's sum when it has more than one transaction -->
              <li class="day">
                <span>{longDay(r.date)}</span>
                {#if shown[i + 1]?.date === r.date}<span class="num">{cents(sums[r.date])}</span>{/if}
              </li>
            {/if}
            <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role: the row holds buttons, a button cannot -->
            <li
              class="item"
              class:on={isOpen(r)}
              role="button"
              tabindex="0"
              class:chosen={chosen.includes(keyOf(r))}
              title={rowTitle}
              onclick={(e) => choose(e, i) || openTxn(r)}
              onmousedown={(e) => e.shiftKey && e.preventDefault()}
              onkeydown={(e) => e.key === "Enter" && openTxn(r)}
            >
              <span class="main">
                <span class="title">{@render payeeButton(r)}</span>
                <span class="sub">
                  {@render accountButton(r)}
                  {#if r.narration && r.narration !== r.payee}<span class="text">{r.narration}</span>{/if}
                  {@render tagButtons(r)}
                  {@render statementButton(r)}
                </span>
              </span>
              <span class="trail">
                <span class="num amount">{@render amountOf(r)}</span>
                <span class="num run" title={r.balance == null ? t("runningTitle") : ""}
                  >{r.balance == null ? t("running") : t("balance")} {cents(r.balance ?? r.run)}</span
                >
              </span>
            </li>
          {/each}
        </ul>
      {:else if shown.length}
        <table class="txns">
          <thead>
            <tr>
              <th>{t("date")}</th><th>{t("payee")}</th><th>{booked(listView.account ?? "") ? t("category") : t("account")}</th>
              <th class="num">{t("amount")}</th>
              <th class="num" title={listView.account && booked(listView.account) ? "" : t("runningTitle")}
                >{listView.account && booked(listView.account) ? t("balance") : t("running")}</th
              >
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each shown as r, i (i)}
              {@const m = r.date.slice(0, 7)}
              {#if (listView.all || unit === "year") && (i === 0 || shown[i - 1].date.slice(0, 7) !== m)}
                <tr class="group">
                  <td colspan="3">{periodName(m)}</td><td class="num">{cents(sums[m])}</td><td></td><td></td>
                </tr>
              {/if}
              <tr class="link" class:on={isOpen(r)} class:chosen={chosen.includes(keyOf(r))} title={rowTitle}
                onclick={(e) => choose(e, i) || openTxn(r)} onmousedown={(e) => e.shiftKey && e.preventDefault()}>
                <td class="date">{i && shown[i - 1].date === r.date ? "" : day(r.date)}</td>
                <td class="what" title={r.narration}>
                  {@render payeeButton(r)}{#if r.narration && r.narration !== r.payee}<span class="muted"
                      >{r.narration}</span
                    >{/if}{@render tagButtons(r)}
                </td>
                <td class="cat-cell">
                  {#if listPick === r.hash}
                    <CategoryPicker accounts={listInfo.accounts} value={accountOf(r)} pick={(a) => pickRow(r, a)}
                      cancel={() => (listPick = null)} />
                  {:else}
                    {@render accountButton(r)}
                    {#if listInfo.editable && r.id && r.others.length === 1}
                      <button type="button" class="pen" title={t("changeCategory")}
                        onclick={(e) => (e.stopPropagation(), (listPick = r.hash))}><wa-icon name="pencil"></wa-icon></button
                      >
                    {/if}
                  {/if}
                </td>
                <td class="num">{@render amountOf(r)}</td>
                <td class="num muted">{cents(r.balance ?? r.run)}</td>
                <td class="doc">{@render statementButton(r)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else}
        <p class="muted">
          {t("noTransactions")}
          {#if listView.payee || listView.tag || search}
            <button type="button" class="more" onclick={() => ((search = ""), go({ name: "txns", account: listView.account }))}
              >{t("removeFilter")}</button
            >
          {/if}
        </p>
      {/if}
    {:else}
      <p class="muted">{t("loading")}</p>
    {/if}
    </div>
    {#if listView !== view}<div class="pane detail">{@render txnView()}</div>{/if}
    </div>
  {:else if view.name === "txn"}
    {@render txnView()}
  {:else if view.name === "runway" && runway}
    {@const withCash = cashOf(rw) !== rw.liquid || cash !== runway.liquid}
    <div class="runway-head">
      <p class="muted">{t("runwayNote")}</p>
      <div class="actions">
        {#if !editing}
          <wa-button size="small" appearance="filled" onclick={startEdit}><wa-icon slot="start" name="pencil"></wa-icon>{t("runwayEdit")}</wa-button>
        {/if}
        <wa-button size="small" appearance="filled" title={t("runwayAgentTitle")} onclick={discuss}
          ><wa-icon slot="start" class="agent-icon" name="sparkles"></wa-icon>{t("runwayAgent")}</wa-button
        >
      </div>
    </div>
    {#if undo}
      <div class="edit-bar" role="status">
        <span>{undo.error || `${t("runwaySaved")}: ${undo.changed.join("; ")}`}</span>
        <wa-button size="small" appearance="filled" onclick={() => saveEdits(undo.changes, null)}>{t("runwayUndo")}</wa-button>
      </div>
    {/if}
    {#if editing}
      {@const n = Object.keys(edits).length}
      <div class="edit-bar sticky">
        <span class:error={editError}>{editError || t("runwayEditNote")}</span>
        <wa-button size="small" appearance="filled" onclick={() => (editing = false)}>{t("cancel")}</wa-button>
        <wa-button size="small" variant="brand" disabled={!n || !!editError}
          onclick={() => saveEdits($state.snapshot(edits), inverse($state.snapshot(edits)))}
          >{n ? `${t("save")} (${n})` : t("save")}</wa-button
        >
      </div>
    {/if}
    <table>
      <thead>
        <tr>
          <th></th><th class="num">{t("perMonth")}</th><th class="num">{t("covers")}</th>
          {#if withCash}<th class="num">{t("withoutInvestments")}</th>{/if}
          <th class="num">{t("missing")}</th>
        </tr>
      </thead>
      <tbody>
        <tr class="group" class:link={!editing} onclick={() => editing || go({ name: "networth" })}>
          <td>{t("liquid")}</td><td class="num">{@render was(unedited?.liquid, rw.liquid, eur)}</td><td></td>
          {#if withCash}<td class="num">{@render was(unedited && cashOf(unedited), cashOf(rw), eur)}</td>{/if}
          <td></td>
        </tr>
        {#if editing && preview}
          <!-- the asset accounts one by one: liquid: "false" is on an account's open; the query leaves out some by
               their name (property, loans given), and their switch is off and fixed -->
          {#each preview.assets as a (a.account)}
            {@const fixed = !a.counted && preview.meta[a.account]?.liquid !== "false"}
            <tr class:muted={!a.counted}>
              <td class="indent">
                <label title={fixed ? t("liquidByName") : ""}>
                  <input type="checkbox" checked={a.counted} disabled={fixed}
                    onchange={(e) => setEdit(a.account, "liquid", e.currentTarget.checked ? null : "false")} />
                  {a.account.split(":").slice(1).join(":")}
                </label>
              </td>
              <td class="num">{eur(a.amount)}</td>
              <td class="num muted">{a.counted ? duration(a.amount / rw.baseline.today) : t("notCounted")}</td>
              {#if withCash}<td></td>{/if}
              <td></td>
            </tr>
          {/each}
        {:else}
          {#each runway.liquid_by_account ?? [] as a (a.account)}
            <tr class="link" onclick={() => go({ name: "txns", account: a.account })}>
              <td class="indent">{a.account.split(":").slice(1).join(":")}</td>
              <td class="num">{eur(a.amount)}</td><td class="num muted">{duration(a.amount / runway.baseline.today)}</td>
              {#if withCash}<td></td>{/if}
              <td></td>
            </tr>
          {/each}
        {/if}
        {#each Object.entries(rw.baseline) as [key, base]}
          {#if base}
            {@const months = rw.liquid / base}
            {@const was0 = unedited?.baseline[key]}
            <tr>
              <td>{t(`baseline_${key}`)}</td>
              <td class="num">{@render was(was0, base, eur)}</td>
              <td class="num" data-state={level(months)}>{@render was(was0 && unedited.liquid / was0, months, duration)}</td>
              {#if withCash}
                <td class="num" data-state={level(cashOf(rw) / base)}
                  >{@render was(was0 && cashOf(unedited) / was0, cashOf(rw) / base, duration)}</td
                >
              {/if}
              <td class="num">{eur(Math.max(0, d.goal * base - rw.liquid))}</td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
    {#if baseline?.length}
      {@const total = sum(baseline.filter((g) => g.counted).map((g) => g.today))}
      <h2>{t("baselineParts")}</h2>
      <table>
        <thead>
          <tr>
            <th>{t("need")}</th><th class="num">{t("baseline_today")}</th><th class="num">{t("baseline_reduced")}</th>
            <th class="num">{t("share")}</th>
            {#if editing}<th>need</th><th class="num" title="cut">{t("cutKept")}</th>{/if}
          </tr>
        </thead>
        <tbody>
          {#each baseline as g (g.need)}
            <tr class="group" class:muted={!g.counted}>
              <td>{t(`need_${g.need}`) === `need_${g.need}` ? g.need : t(`need_${g.need}`)}</td>
              <td class="num">{@render was(old[g.need]?.today ?? (editing ? 0 : null), g.today, eur)}</td>
              <td class="num">{@render was(old[g.need]?.reduced ?? (editing ? 0 : null), g.reduced, eur)}</td>
              <td class="num">{g.counted && total ? pct(g.today / total) : "–"}</td>
              {#if editing}<td></td><td></td>{/if}
            </tr>
            {#each g.accounts as a (a.account)}
              <tr
                class:link={!editing}
                class:muted={!g.counted}
                onclick={() =>
                  editing || (a.account.startsWith("Expenses") ? open(a.account) : go({ name: "txns", account: a.account }))}
              >
                <td class="indent">{a.account.split(":").slice(1).join(":")}</td>
                <td class="num">{eur(a.today)}</td>
                <td class="num">{@render was(old[a.account]?.reduced, a.reduced, eur)}</td><td></td>
                {#if editing}
                  {@const m = preview.meta[a.account] ?? {}}
                  <td>
                    <select value={m.need ?? "unknown"} onchange={(e) => setEdit(a.account, "need", e.currentTarget.value)}>
                      {#each NEEDS as n}<option value={n}>{t(`need_${n}`)}</option>{/each}
                    </select>
                  </td>
                  <td class="num">
                    {#if ["flexible", "unknown"].includes(m.need ?? "unknown")}
                      {@const kept = dragCut[a.account] ?? Math.round(Number(m.cut ?? 0) * 100)}
                      <label class="cut">
                        <input type="range" min="0" max="100" step="5" value={kept} aria-label={`${a.account}: ${t("cutKept")}`}
                          oninput={(e) => (dragCut[a.account] = Number(e.currentTarget.value))}
                          onchange={(e) => setEdit(a.account, "cut", String(Number(e.currentTarget.value) / 100))} />
                        <span>{kept} %</span>
                      </label>
                    {/if}
                  </td>
                {/if}
              </tr>
            {/each}
          {/each}
        </tbody>
      </table>
      <p class="muted note">
        {t("baselineNote")}
        <button
          type="button"
          class="more"
          onclick={() => fava(`/ledger/query/?query_string=${encodeURIComponent(runway.query)}`)}>Fava <wa-icon name="external-link"></wa-icon></button
        >
      </p>
    {/if}
  {/if}
</div>
</div>
