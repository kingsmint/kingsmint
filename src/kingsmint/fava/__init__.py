"""Fava extension: expenses per account and year, with the change against the year before.

main.beancount turns it on with `custom "fava-extension" "kingsmint.fava"`. Fava's own yearly table has the
amounts but not the change, so a jump hides among the numbers. The last year, when its statements end before
31 December, is compared with the same days of the year before. Fava's filters (time, account, tags) apply.
"""

import datetime as dt
from collections import defaultdict
from urllib.parse import urlencode
from decimal import Decimal

from beancount.core import account as acc
from beancount.core.data import Transaction
from fava.ext import FavaExtensionBase
from flask import g, request

TITLES = {"sk": "Trendy", "cs": "Trendy", "de": "Trends"}
# (lowest change, class): a rise in expenses is red, a fall green; a small account is grey whatever its change
LEVELS = [(Decimal("0.5"), "up2"), (Decimal("0.15"), "up1"), (Decimal("-0.15"), ""), (Decimal("-0.5"), "down1")]


def level(change):
    return next((cls for low, cls in LEVELS if change >= low), "down2")


class Trends(FavaExtensionBase):
    report_title = "Trends"
    has_js_module = True  # Trends.js: the threshold slider

    def __init__(self, ledger, config=None):
        super().__init__(ledger, config)
        self.report_title = TITLES.get(ledger.fava_options.language or "", "Trends")

    def table(self, root="Expenses", by="year", depth=None):
        """{periods: [(label, Fava time filter)], newest first; partial: the newest period's last day when its
        statements end before the period does; rows: [(account, depth, cells)]}. A cell is (amount, change or None,
        class, peak); change "new" where the account had nothing in the year before the period, "-" where there is
        nothing to compare: nothing in the same month a year before, or money back (a negative amount). by: "year", or "month" for the last 13 months,
        each against the same month a year before (not the month before, which mixes in the seasons).
        depth: only accounts with at most that many ":". peak: a marked change in percent (a "new" one counts as
        10000), 0 when the change is not marked; the slider hides the rows below its threshold in the chosen column."""
        txns = [e for e in g.filtered.entries if isinstance(e, Transaction)]
        empty = {"periods": [], "rows": [], "partial": None, "currency": None}
        if not txns:
            return empty
        last = max(e.date for e in txns)  # the end of the statements, not the calendar: the rest is not imported yet
        key = (lambda d: d.year) if by == "year" else (lambda d: (d.year, d.month))
        prior = (lambda k: k - 1) if by == "year" else (lambda k: (k[0] - 1, k[1]))
        # the periods of the year before a period: the year before, or the 12 months before
        year_before = (lambda k: [k - 1]) if by == "year" else (
            lambda k: [((k[0] * 12 + k[1] - 1 - i) // 12, (k[0] * 12 + k[1] - 1 - i) % 12 + 1) for i in range(1, 13)])
        currency = self.ledger.options["operating_currency"][0]
        prices = self.ledger.prices
        totals = defaultdict(lambda: defaultdict(Decimal))  # account -> period -> amount
        early = defaultdict(lambda: defaultdict(Decimal))  # the same, only days up to the last day's day of the year
        for e in txns:
            for p in e.postings:
                if p.account != root and not p.account.startswith(root + ":"):
                    continue
                number = p.units.number
                if p.units.currency != currency:
                    rate = prices.get_price((p.units.currency, currency), e.date)
                    if rate is None:
                        continue  # shortcut: no rate drops the posting; Fava's own tables show such amounts apart
                    number *= rate
                for a in acc.parents(p.account):
                    if a.startswith(root):
                        totals[a][key(e.date)] += number
                        if (e.date.month, e.date.day) <= (last.month, last.day):
                            early[a][key(e.date)] += number
        if not totals:
            return empty
        first = min(k for t in totals.values() for k in t)
        if by == "year":
            keys = list(range(last.year, first - 1, -1))
            ends = (last.month, last.day) != (12, 31)
        else:
            keys = [((last.year * 12 + last.month - 1 - i) // 12, (last.year * 12 + last.month - 1 - i) % 12 + 1) for i in range(13)]
            ends = (last + dt.timedelta(days=1)).month == last.month
        partial = last if ends else None
        rows = []
        for a in sorted(totals):
            if depth is not None and a.count(":") > depth:
                continue
            cells = []
            for k in keys:
                amount = totals[a].get(k, Decimal(0))
                before = (early if partial and k == keys[0] else totals)[a].get(prior(k), Decimal(0))
                big = abs(amount - before) >= abs(totals[root].get(prior(k), Decimal(0))) * Decimal("0.005")
                if prior(k) < first or (not amount and not before):
                    change, cls = None, ""
                elif amount < 0 or before < 0:
                    change, cls = "-", "small"
                elif not before and any(totals[a].get(x) for x in year_before(k)):
                    change, cls = "-", "small"
                elif not before:
                    change, cls = "new", "up2" if big else "small"
                else:
                    change = (amount - before) / abs(before)
                    cls = level(change) if big else "small"
                peak = 0 if cls in ("", "small") else 10000 if change == "new" else round(abs(change) * 100)
                cells.append((amount, change, cls, peak))
            rows.append((a, a.count(":"), cells))
        periods = [(str(k), str(k)) if by == "year" else (f"{k[0]}-{k[1]:02}", f"{k[0]}-{k[1]:02}") for k in keys]
        return {"periods": periods, "rows": rows, "currency": currency, "partial": partial}

    def link(self, **changes):
        """The query string of this report with `changes`; None removes one. Keeps Fava's filters."""
        args = {**request.args, **changes}
        return "?" + urlencode({k: v for k, v in args.items() if v is not None})
