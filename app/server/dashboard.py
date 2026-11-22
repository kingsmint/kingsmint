"""The overview's numbers (ui/js/Dashboard.svelte) for one month or year and the 12 before it: the income and
expenses of every account and its parents in each, the balances of the asset and liability accounts, the runway, and the
payees behind an account. Amounts are in the operating currency: income and expenses at the rate of their day,
balances at the rate of the month's last day. Positive income and expenses; balances as booked (a liability is
negative)."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

import beanquery
from beancount.core import account as acc
from beancount.core.data import Open, Query, Transaction
from fava.beans.funcs import hash_entry

GOAL = 6  # months of the baseline that the liquid money should cover


def key(d: dt.date) -> int:
    return d.year * 12 + d.month - 1


def label(k: int) -> str:
    return f"{k // 12}-{k % 12 + 1:02}"


def month_end(k: int) -> dt.date:
    return dt.date((k + 1) // 12, (k + 1) % 12 + 1, 1) - dt.timedelta(days=1)


def kind(account: str) -> str:
    """The group of an asset or liability account in the net worth, by the names accounts.beancount defines."""
    parts = account.split(":")
    if parts[0] == "Liabilities":
        return "liabilities"
    for name in ("Investments", "Property", "Loans"):
        if name in parts:
            return name.lower()
    if "Bank" in parts:
        return "current" if parts[-1] == "Current" else "savings"
    return "other"


def money(n) -> float | None:
    return None if n is None else float(round(n, 2))


class Ledger:
    """The transactions, and amounts in the operating currency. `rate(currency, date)`: the price of a unit in the
    operating currency, or None."""

    def __init__(self, entries, options, rate):
        self.currency = (options["operating_currency"] or ["EUR"])[0]
        self.txns = [e for e in entries if isinstance(e, Transaction)]
        self.rate = rate

    def value(self, number, currency, day):
        if currency == self.currency:
            return number
        r = self.rate(currency, day)
        return None if r is None else number * r  # shortcut: no price drops the amount, as Trends does


def overview(entries, errors, options, rate, period: str | None = None, unit: str = "month",
             today: dt.date | None = None) -> dict:
    """`period` (a month YYYY-MM or a year YYYY, by `unit`; else the last full month, or its year) and the 12 periods
    before it, from the first with transactions. `window`: their labels; `ends`: the last month of each (YYYY-MM);
    `flows`: the Income and Expenses accounts and their parents, an amount per period; `accounts`: the balances at
    each end; `months`: how many months of each year count. A year that is not over counts its months up to the last
    full one, and so do the years before it, as Fava's Trends report compares them; a year before it whose statements
    start after January is left out."""
    led = Ledger(entries, options, rate)
    result = {"currency": led.currency, "goal": GOAL, "runway": runway(entries, errors, options, led.currency),
              "unit": unit}
    if not led.txns:
        return result | {"period": None, "periods": []}
    first = key(min(e.date for e in led.txns))
    last = key(max(e.date for e in led.txns))
    default = min(key(today or dt.date.today()) - 1, last)  # the last full month, not after the statements
    if unit == "year":
        sel = int(period) if period else default // 12
        months = default % 12 + 1 if sel == default // 12 else 12
        # the years before it from their January only: a year that starts later would compare less than its months
        window = [y for y in range(sel - 12, sel) if y * 12 >= first] + [sel]
        ends = [y * 12 + months - 1 for y in window]
        bucket = {y * 12 + m: y for y in window for m in range(months)}  # month -> its year, the months that count
        names = [str(y) for y in window]
        periods = [str(y) for y in range(max(last, default) // 12, first // 12 - 1, -1)]
    else:
        sel = key(dt.date.fromisoformat(period + "-01")) if period else default
        months = 1
        window = ends = [k for k in range(sel - 12, sel + 1) if k >= first]
        bucket = {k: k for k in window}
        names = [label(k) for k in window]
        periods = [label(k) for k in range(last, first - 1, -1)]
    result |= {"period": str(sel) if unit == "year" else label(sel), "periods": periods, "months": months}
    if not window:
        return result | {"window": [], "ends": [], "flows": {}, "accounts": []}
    lo, hi = ends[0], ends[-1]
    flows = defaultdict(lambda: defaultdict(Decimal))  # an Income or Expenses account or its parent -> period -> amount
    units = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))  # account -> month (lo: before) -> currency -> units
    for e in led.txns:
        k = key(e.date)
        if k > hi:
            continue
        for p in e.postings:
            root = p.account.split(":")[0]
            if root in ("Assets", "Liabilities"):
                units[p.account][max(k, lo)][p.units.currency] += p.units.number
            elif root in ("Income", "Expenses") and k in bucket:
                n = led.value(p.units.number, p.units.currency, e.date)
                if n is None:
                    continue
                for a in acc.parents(p.account):
                    flows[a][bucket[k]] += -n if root == "Income" else n

    def balances(k):
        out = {}
        for a, by_month in units.items():
            total = defaultdict(Decimal)
            for m, curs in by_month.items():
                if m <= k:
                    for c, n in curs.items():
                        total[c] += n
            out[a] = sum((led.value(n, c, month_end(k)) or Decimal(0) for c, n in total.items() if n), Decimal(0))
        return out

    history = [balances(k) for k in ends]
    return result | {
        "window": names,
        "ends": [label(k) for k in ends],
        "flows": {a: [money(f.get(w, Decimal(0))) for w in window] for a, f in sorted(flows.items())
                  if any(f.get(w) for w in window)},
        "accounts": [{"account": a, "kind": kind(a), "history": [money(h[a]) for h in history]}
                     for a in sorted(units) if any(h[a] for h in history)],
    }


def transactions(entries, options, rate, start: str, end: str, account: str | None = None) -> dict:
    """The postings from month `start` to month `end` (YYYY-MM) under `account` (else all income and expenses), money
    in positive: income and expenses with the sign turned, assets and liabilities as booked, with the account's
    `balance` after each. Each with its entry's `others` accounts, `hash` (Fava's, for its statement and context
    pages), and whether it names a statement (`document`). `merchants`: their payees, `recurring` when the payee was
    paid in each of the 3 months up to `end`."""
    led = Ledger(entries, options, rate)
    lo, hi = (key(dt.date.fromisoformat(m + "-01")) for m in (start, end))
    booked = bool(account) and account.split(":")[0] in ("Assets", "Liabilities")
    rows, seen, balance = [], defaultdict(set), Decimal(0)
    for e in led.txns:
        m = key(e.date)
        if m > hi or (m < min(lo, hi - 2) and not booked):
            continue
        for p in e.postings:
            if account:
                if p.account != account and not p.account.startswith(account + ":"):
                    continue
            elif p.account.split(":")[0] not in ("Income", "Expenses"):
                continue
            # shortcut: a balance in another currency is summed at the rate of each day, not of the last one
            n = led.value(p.units.number, p.units.currency, e.date)
            if n is None:
                continue
            balance += n
            payee = e.payee or e.narration
            if m >= hi - 2:
                seen[payee].add(m)
            if m >= lo:
                rows.append({"date": e.date.isoformat(), "payee": payee, "narration": e.narration,
                             "account": p.account, "amount": money(n if booked else -n), "hash": hash_entry(e),
                             "others": [o.account for o in e.postings if o.account != p.account],
                             "document": "document" in e.meta} | ({"balance": money(balance)} if booked else {}))
    payees = defaultdict(lambda: [Decimal(0), 0])
    for r in rows:
        payees[r["payee"]][0] += Decimal(str(r["amount"]))
        payees[r["payee"]][1] += 1
    merchants = sorted(({"payee": p, "amount": money(s), "count": c, "recurring": len(seen[p]) == 3}
                        for p, (s, c) in payees.items()), key=lambda m: m["amount"])
    return {"rows": rows, "merchants": merchants}


def runway(entries, errors, options, currency) -> dict | None:
    """The saved queries `Liquid money` and `Baseline` (as `kingsmint runway`): the liquid money now and its accounts
    (the query's rows, largest first), the monthly baseline in each of the query's columns (today, reduced,
    minimum), and the query `Baseline by account`, which shows what the baseline is made of. None in a ledger older
    than the queries."""
    queries = {e.name: e.query_string for e in entries if isinstance(e, Query)}
    if "Liquid money" not in queries or "Baseline" not in queries:
        return None
    conn = beanquery.connect("beancount:", entries=entries, errors=errors, options=options)
    rows = [(a, inv.get_currency_units(currency).number) for a, inv in conn.execute(queries["Liquid money"]).fetchall()]
    liquid = sum((n for _, n in rows), Decimal(0))
    cursor = conn.execute(queries["Baseline"])
    row = cursor.fetchone() or [None] * len(cursor.description)
    return {"liquid": money(liquid),
            "liquid_by_account": [{"account": a, "amount": money(n)} for a, n in sorted(rows, key=lambda r: -r[1]) if n],
            "baseline": {c.name: money(v) for c, v in zip(cursor.description, row)},
            "query": queries.get("Baseline by account")}


NEEDS = ("essential", "flexible", "optional", "unknown", "income-linked")
CUT_NEEDS = ("flexible", "unknown")  # the needs whose spending a `cut` reduces


def checked(entries, changes: dict) -> dict:
    """The runway's edits {account: {key: value}}, checked (ValueError) and in the form of the ledger's metadata: `liquid`
    "false" on an asset account, `need` and `cut` (0 to 1, flexible and unknown only) on an expense or liability
    account; None removes the key. A need without a cut drops the account's `cut`."""
    opens = {e.account: e for e in entries if isinstance(e, Open)}
    out = {}
    for account, edit in changes.items():
        if account not in opens:
            raise ValueError(f"No open entry for {account}")
        if not edit or set(edit) - {"liquid", "need", "cut"}:
            raise ValueError(f"Not an edit of liquid, need or cut: {edit!r}")
        assets = account.startswith("Assets:")
        if "liquid" in edit and (not assets or edit["liquid"] not in ("false", None)):
            raise ValueError(f"liquid is \"false\" or none, on an asset account: {account}")
        if assets and {"need", "cut"} & set(edit):
            raise ValueError(f"need and cut are on expense and liability accounts: {account}")
        if "need" in edit and edit["need"] not in (*NEEDS, None):
            raise ValueError(f"Not a need: {edit['need']!r}")
        edit = dict(edit)
        if edit.get("cut") is not None:
            edit["cut"] = Decimal(str(edit["cut"]))
            if not 0 <= edit["cut"] <= 1:
                raise ValueError(f"cut is from 0 to 1: {edit['cut']}")
        need = edit["need"] if "need" in edit else opens[account].meta.get("need")
        if need not in CUT_NEEDS and ("cut" in opens[account].meta or edit.get("cut") is not None):
            if edit.get("cut") is not None:
                raise ValueError(f"cut is for flexible and unknown spending: {account}")
            edit["cut"] = None
        out[account] = edit
    return out


def with_meta(entries, changes: dict) -> list:
    """The entries with the checked edits in the metadata of their `open` entries, for a preview."""
    def edited(e):
        if not isinstance(e, Open) or e.account not in changes:
            return e
        meta = {**e.meta, **changes[e.account]}
        return e._replace(meta={k: v for k, v in meta.items() if v is not None})
    return [edited(e) for e in entries]


def runway_edit(entries, errors, options, currency, changes: dict) -> dict | None:
    """The runway with the edits `changes` (as `checked` takes them), for the runway's edit view: `runway()`, the rows
    of `Baseline by account` (columns and rows, as the query method gives them), the asset accounts with a balance
    (amount, and `counted`: in the saved query `Liquid money` by itself), and the liquid, need and cut of each account.
    None in a ledger older than the queries."""
    entries = with_meta(entries, checked(entries, changes))
    r = runway(entries, errors, options, currency)
    if r is None:
        return None
    conn = beanquery.connect("beancount:", entries=entries, errors=errors, options=options)
    queries = {e.name: e.query_string for e in entries if isinstance(e, Query)}
    # shortcut: the query by account, not by its root; a query edited without root(account, 3) counts each account as
    # not liquid, so the edit view offers no switch: then add the account's liquid: "false" by hand
    counted = {a for a, _ in conn.execute(queries["Liquid money"].replace("root(account, 3)", "account")).fetchall()}
    assets = conn.execute(f"SELECT account, convert(value(sum(position)), '{currency}') WHERE account ~ '^Assets:' "
                          "GROUP BY account").fetchall()
    rows = {"columns": [], "rows": []}
    if r["query"]:
        cursor = conn.execute(r["query"])
        rows = {"columns": [c.name for c in cursor.description], "rows": cursor.fetchall()}
    return r | {"by_account": rows,
                "assets": sorted(({"account": a, "amount": money(inv.get_currency_units(currency).number),
                                   "counted": a in counted} for a, inv in assets
                                  if inv.get_currency_units(currency).number), key=lambda a: -a["amount"]),
                "meta": {e.account: {k: str(e.meta[k]) for k in ("liquid", "need", "cut") if k in e.meta}
                         for e in entries if isinstance(e, Open) and e.account.startswith(("Assets:", "Expenses:",
                                                                                            "Liabilities:"))}}


def entry(e, entries, options, rate, statement: bool) -> dict:
    """One transaction: its postings (units, and their value in the operating currency at its date), its metadata, its
    `amount` (money in positive: of its income and expenses, or what moved between own accounts), whether Fava finds
    its `statement`; `payee`: the payee, else the narration, as `transactions` names it; and the payee's transactions
    in the 12 months up to it, the newest first (`history`)."""
    led = Ledger(entries, options, rate)

    def amount(t):
        values = [(p.account.split(":")[0], led.value(p.units.number, p.units.currency, t.date)) for p in t.postings]
        flows = [-v for root, v in values if root in ("Income", "Expenses") and v is not None]
        return money(sum(flows) if flows else sum(v for _, v in values if v and v > 0))

    name = e.payee or e.narration
    since = e.date - dt.timedelta(days=365)
    same = [t for t in led.txns if since < t.date <= e.date and (t.payee or t.narration) == name]
    return {
        "hash": hash_entry(e), "date": e.date.isoformat(), "flag": e.flag, "payee": name, "narration": e.narration,
        "amount": amount(e), "transfer": not any(p.account.split(":")[0] in ("Income", "Expenses") for p in e.postings),
        "postings": [{"account": p.account, "number": float(p.units.number), "currency": p.units.currency,
                      "value": money(led.value(p.units.number, p.units.currency, e.date))} for p in e.postings],
        "meta": {k: str(v) for k, v in e.meta.items() if k not in ("filename", "lineno") and not k.startswith("__")},
        "statement": statement,
        "history": [{"date": t.date.isoformat(), "hash": hash_entry(t), "amount": amount(t)} for t in reversed(same)],
    }
