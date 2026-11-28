"""Budgets, in budgets.beancount: a limit per expense account and period (Fava's `custom "budget"`), and a limit per
tag from a start date to an optional end date (kingsmint's `custom "budget-tag"`, which Fava ignores). What the overview
shows of them, and the app's changes of the file.

    2026-01-01 custom "budget" Expenses:Food "monthly" 400.00 EUR
    2026-02-01 custom "budget-tag" "plot" 8000.00 EUR 2026-09-30 "Fence"

An account's limit comes from Fava's own computation (fava.core.budgets), so the app and Fava agree: an entry holds
from its date until a newer one for the account, `0` ends it, a period it covers in part is prorated by days. A tag's
spending: the expenses of the transactions with the tag, any account, from the start date to the end date.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from beancount.core.amount import Amount
from beancount.core.data import Custom, Open, Transaction
from beancount.parser import parser
from fava.beans.funcs import hash_entry
from fava.core.budgets import calculate_budget, parse_budgets
from fava.util.date import END_OF_YEAR

from dashboard import CASH, Ledger, money
from edit import EditError, tag_slug
from ledger_settings import write

FILE = "budgets.beancount"
PERIODS = ("monthly", "quarterly", "yearly")
WARN = Decimal("0.75")
AHEAD = Decimal("0.1")  # spending runs ahead of time: its share of the limit passes the share of days by 10 points
ACCOUNT_LINE = re.compile(r'^(\d{4}-\d{2}-\d{2}) +custom +"budget" +(\S+) ')
TAG_LINE = re.compile(r'^\d{4}-\d{2}-\d{2} +custom +"budget-tag" +"([^"]*)"')


class BudgetError(ValueError):
    pass


def state(spent: Decimal, limit: Decimal, elapsed: Decimal | None) -> str:
    """good, warn (from 75 %, or spending ahead of the days that passed), bad (over the limit)."""
    if spent > limit:
        return "bad"
    if spent >= limit * WARN or (elapsed is not None and spent / limit > elapsed + AHEAD):
        return "warn"
    return "good"


def status(spent: Decimal, limit: Decimal, start: dt.date, end: dt.date | None, today: dt.date) -> dict:
    """The numbers of one budget: `end` is the last day, inclusive; None for a tag without an end."""
    left = limit - spent
    days = (end - start).days + 1 if end else None
    days_left = None if end is None else max(0, min(days, (end - today).days + 1))
    elapsed = None if end is None else Decimal(days - days_left) / days if today >= start else Decimal(0)
    return {"start": start.isoformat(), "end": end and end.isoformat(), "limit": money(limit), "spent": money(spent),
            "left": money(left), "days": days, "days_left": days_left,
            "per_day": money(left / days_left) if days_left and left > 0 else None,
            "share": float(round(spent / limit, 4)), "elapsed": None if elapsed is None else float(round(elapsed, 4)),
            "state": state(spent, limit, elapsed)}


def fava_budgets(entries) -> dict:
    """Fava's budgets by account, as Fava's account report computes with them."""
    customs = [e for e in entries if isinstance(e, Custom)]
    try:
        return parse_budgets(customs)[0]  # Fava 1.30
    except TypeError:  # Fava 1.31 takes the end of the fiscal year
        return parse_budgets(customs, END_OF_YEAR)[0]


def period_start(period: str, day: dt.date) -> dt.date:
    if period == "monthly":
        return day.replace(day=1)
    return dt.date(day.year, (day.month - 1) // 3 * 3 + 1 if period == "quarterly" else 1, 1)


def under(account: str, parent: str) -> bool:
    return account == parent or account.startswith(parent + ":")


def account_budgets(entries, led: Ledger, today: dt.date, offset: int = 0) -> list[dict]:
    """The accounts' budgets in their current period, or `offset` periods before it (-1: the one before), each in the
    period of its own entry (a month, a quarter, a year). Limits in the operating currency only."""
    budgets = fava_budgets(entries)
    # the period's name as written ("monthly"): Fava keeps only its Interval, whose API differs between versions
    named = {(e.values[0].value, e.date): str(e.values[1].value).lower() for e in entries
             if isinstance(e, Custom) and e.type == "budget" and len(e.values) > 1}
    out = []
    for account, items in budgets.items():
        mine = [b for b in items if b.currency == led.currency]  # shortcut: a budget in another currency is not shown

        def interval(day):
            active = [b for b in mine if b.date_start <= day]
            return (active or mine)[-1].period if mine else None

        if not mine:
            continue
        day = today
        start = interval(day).get_prev(day)
        for _ in range(-offset):
            day = start - dt.timedelta(days=1)
            start = interval(day).get_prev(day)
        end = interval(day).get_next(start)  # exclusive, as Fava counts
        limit = calculate_budget(budgets, account, start, end).get(led.currency, Decimal(0))
        if limit <= 0:
            continue
        spent = sum((led.value(p.units.number, p.units.currency, e.date) or Decimal(0)
                     for e in led.txns if start <= e.date < end for p in e.postings if under(p.account, account)),
                    Decimal(0))
        entry = [b for b in mine if b.date_start < end][-1]  # the entry the period ends with: the one to change
        out.append({"account": account, "period": named.get((account, entry.date_start)),
                    "amount": money(entry.number), "since": entry.date_start.isoformat()}
                   | status(spent, limit, start, end - dt.timedelta(days=1), today))
    return sorted(out, key=lambda b: -b["share"])


def tag_entries(entries) -> tuple[dict, list[str]]:
    """The newest `budget-tag` entry of each tag: {tag: (date, Amount, end, name)}, and the entries it cannot read.
    One with 0 removes the tag's budget."""
    found, errors = {}, []
    for e in entries:
        if not isinstance(e, Custom) or e.type != "budget-tag":
            continue
        values = [v.value for v in e.values]
        if len(values) < 2 or not isinstance(values[0], str) or not isinstance(values[1], Amount):
            errors.append(f"{e.meta.get('filename')}:{e.meta.get('lineno')}: a tag budget is "
                          '`DATE custom "budget-tag" "tag" AMOUNT CURRENCY [END-DATE] ["name"]`')
            continue
        end = next((v for v in values[2:] if isinstance(v, dt.date)), None)
        name = next((v for v in values[2:] if isinstance(v, str)), None)
        if (end and end < e.date) or values[1].number < 0:  # a hand-written entry; no days or no limit to count with
            errors.append(f"{e.meta.get('filename')}:{e.meta.get('lineno')}: a tag budget ends before it starts, "
                          "or its limit is below 0")
            continue
        found[values[0]] = (e.date, values[1], end, name)
    return {t: v for t, v in found.items() if v[1].number}, errors


def tag_budgets(entries, led: Ledger, today: dt.date) -> tuple[list[dict], list[str]]:
    """Each tag's budget: the expenses of the transactions with the tag from its start to its end date, and those
    payments, the newest first."""
    found, errors = tag_entries(entries)
    out = []
    for tag, (start, amount, end, name) in found.items():
        payments = []
        for e in led.txns:
            if tag not in (e.tags or ()) or e.date < start or (end and e.date > end):
                continue
            ps = [p for p in e.postings if p.account.startswith("Expenses:")]
            if any(p.account != CASH for p in ps):  # a cash payment named in cash.beancount: out of Expenses:Cash
                ps = [p for p in ps if p.account != CASH]
            if not ps:
                continue
            values = [led.value(p.units.number, p.units.currency, e.date) or Decimal(0) for p in ps]
            payments.append({"date": e.date.isoformat(), "payee": e.payee or e.narration, "narration": e.narration,
                             "accounts": [p.account for p in ps], "amount": money(sum(values)),
                             "hash": hash_entry(e), "id": e.meta.get("id")})
        spent = sum((Decimal(str(p["amount"])) for p in payments), Decimal(0))
        limit = amount.number if amount.currency == led.currency else None
        if limit is None or limit <= 0:  # shortcut: a tag budget in another currency is not shown
            continue
        out.append({"tag": tag, "name": name or tag, "currency": amount.currency,
                    "payments": sorted(payments, key=lambda p: p["date"], reverse=True)}
                   | status(spent, limit, start, end, today))
    return sorted(out, key=lambda b: -b["share"]), errors


def averages(led: Ledger, today: dt.date) -> dict[str, float]:
    """Each expense account's average month of the last 12, its subaccounts in: what the form shows by the limit, as
    the saved query Baseline by account does."""
    since = today - dt.timedelta(days=365)
    sums: dict[str, Decimal] = {}
    for e in led.txns:
        if since <= e.date <= today:
            for p in e.postings:
                if p.account.startswith("Expenses:"):
                    v = led.value(p.units.number, p.units.currency, e.date) or Decimal(0)
                    for i in range(2, p.account.count(":") + 2):
                        a = ":".join(p.account.split(":")[:i])
                        sums[a] = sums.get(a, Decimal(0)) + v
    return {a: money(v / 12) for a, v in sums.items() if v > 0}


def overview(entries, options, rate, offset: int = 0, today: dt.date | None = None) -> dict:
    """The budgets for the app: `accounts` in their period (`offset` periods back), `tags`, the worst first; `used`:
    the tags of the transactions, the most used first, and `averages`, the accounts' average month: for the forms."""
    led = Ledger(entries, options, rate)
    today = today or dt.date.today()
    tags, errors = tag_budgets(entries, led, today)
    used: dict[str, int] = {}
    for e in led.txns:
        for t in e.tags or ():
            used[t] = used.get(t, 0) + 1
    return {"currency": led.currency, "today": today.isoformat(), "offset": offset,
            "accounts": account_budgets(entries, led, today, offset), "tags": tags, "errors": errors,
            "used": sorted(used, key=lambda t: -used[t]), "averages": averages(led, today)}


def amount(value) -> Decimal:
    try:
        n = Decimal(str(value).replace(",", ".").replace(" ", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise BudgetError(f"Not an amount: {value!r}") from None
    if not n.is_finite() or n < 0:
        raise BudgetError("The limit is 0 or more")
    return n


def day(value) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise BudgetError(f"Not a date: {value!r}") from None


def save(root: Path, text: str) -> None:
    path = root / FILE
    old = path.read_text(encoding="utf-8")
    if len(parser.parse_string(text)[1]) > len(parser.parse_string(old)[1]):
        raise BudgetError(f"The change would break {FILE}; nothing was written")
    write(path, text)


def read(root: Path) -> list[str]:
    path = root / FILE
    if not path.exists():
        raise BudgetError(f"The ledger has no {FILE}: run `kingsmint upgrade --apply`")
    text = path.read_text(encoding="utf-8")
    return (text if not text or text.endswith("\n") else text + "\n").splitlines(keepends=True)


def expense_accounts(entries) -> list[str]:
    """The open expense accounts and their parents (Expenses:Food over Expenses:Food:Groceries): each takes a budget."""
    opened = {e.account for e in entries if isinstance(e, Open) and e.account.startswith("Expenses:")}
    return sorted({":".join(a.split(":")[:i]) for a in opened for i in range(2, a.count(":") + 2)})


def set_account(root: Path, entries, currency: str, account: str, period: str, limit, since=None,
                today: dt.date | None = None) -> str:
    """The account's budget from `since` (default: the start of the current period): its entries from that day on go,
    and one entry takes their place, so an account has one budget at a time. 0 ends the budget. Returns what changed,
    for the version. shortcut: only the entries in budgets.beancount go; one the owner wrote elsewhere stays."""
    if account not in expense_accounts(entries):
        raise BudgetError(f"Not an open expense account: {account!r}")
    if period not in PERIODS:
        raise BudgetError(f"Not a period: {period!r}")
    limit = amount(limit)
    since = day(since) if since else period_start(period, today or dt.date.today())
    lines = [line for line in read(root) if not ((m := ACCOUNT_LINE.match(line)) and m[2] == account
                                                    and dt.date.fromisoformat(m[1]) >= since)]
    earlier = any((m := ACCOUNT_LINE.match(line)) and m[2] == account for line in lines)
    if limit or earlier:  # 0 for a budget that starts only now: nothing to end
        lines.append(f'{since} custom "budget" {account} "{period}" {limit} {currency}\n')
    save(root, "".join(lines))
    return f"{account} {period} {limit} {currency} from {since}" if limit else f"{account} ends {since}"


def set_tag(root: Path, currency: str, tag: str, limit, start, end=None, name: str | None = None,
            old: str | None = None) -> tuple[str, str]:
    """The tag's budget, in place of its entries (and those of `old`, a tag renamed in the form). 0 removes it. Returns
    the tag as written and what changed, for the version."""
    try:
        tag = tag_slug(tag or "")
    except EditError:
        raise BudgetError("A tag of letters, digits, - _ / or .") from None
    limit, start = amount(limit), day(start)
    end = day(end) if end else None
    if end and end < start:
        raise BudgetError("The end date is before the start")
    name = (name or "").strip()
    if any(c in name for c in '"\\\n'):
        raise BudgetError("Name: no quotes, backslashes or line breaks")
    lines = read(root)
    if limit and tag != old and any((m := TAG_LINE.match(line)) and m[1] == tag for line in lines):
        raise BudgetError(f"#{tag} has a budget already: change that one")
    lines = [line for line in lines if not ((m := TAG_LINE.match(line)) and m[1] in (tag, old))]
    if limit:
        lines.append(f'{start} custom "budget-tag" "{tag}" {limit} {currency}'
                     + (f" {end}" if end else "") + (f' "{name}"' if name and name != tag else "") + "\n")
    save(root, "".join(lines))
    return tag, f"#{tag} {limit} {currency} from {start}" + (f" to {end}" if end else "") if limit else f"#{tag} removed"
