"""Recurring payments of the overview (app/server/dashboard.py `recurring`), and hiding a payee (app/server/edit.py)."""
import datetime as dt
import sys
from pathlib import Path

import pytest
from beancount import loader
from beancount.parser import parser

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import dashboard
import edit

TODAY = dt.date(2026, 6, 15)


def ledger(payments, extra=""):
    """A ledger with expense payments [(date, payee, amount)] from Assets:Bank, or [(date, payee, amount, account)]."""
    text = ['option "operating_currency" "EUR"\n2020-01-01 open Assets:Bank EUR\n2020-01-01 open Assets:Other EUR\n'
            '2020-01-01 open Expenses:Other\n']
    for d, payee, n, *account in payments:
        text.append(f'{d} * "{payee}" ""\n  {(account or ["Assets:Bank"])[0]}  -{n:.2f} EUR\n  Expenses:Other  {n:.2f} EUR\n')
    entries, errors, options = parser.parse_string("\n".join(text) + extra)
    assert not errors
    return entries, options


def find(payments, extra=""):
    entries, options = ledger(payments, extra)
    r = dashboard.recurring(entries, options, lambda c, d: None, TODAY)
    return r, {p["payee"]: p for p in r["payees"]}


def monthly(payee, amount, first, last, day=5):
    return [(dt.date(k // 12, k % 12 + 1, day), payee, amount)
            for k in range(dashboard.key(first), dashboard.key(last) + 1)]


def test_monthly_yearly_rise_ended():
    pays = (monthly("Stream", 12.99, dt.date(2025, 1, 1), dt.date(2026, 6, 1))
            + monthly("Gym", 30, dt.date(2025, 1, 1), dt.date(2026, 5, 1))[:-1] + [(dt.date(2026, 5, 6), "Gym", 35)]
            + monthly("Old", 5, dt.date(2025, 1, 1), dt.date(2026, 2, 1))
            + monthly("Fresh", 9, dt.date(2026, 4, 1), dt.date(2026, 6, 1))
            + [(dt.date(2025, 3, 20), "Insurance", 240), (dt.date(2026, 3, 18), "Insurance", 252)])
    r, by = find(pays)
    assert by["Stream"]["period"] == 1 and by["Stream"]["typical"] == 12.99 and by["Stream"]["next"] == "2026-07-05"
    assert not any(by["Stream"][f] for f in ("higher", "new", "ended", "manual")) and by["Stream"]["state"] == "suggested"
    assert by["Gym"]["higher"] and by["Gym"]["typical"] == 30 and by["Gym"]["amounts"][-1] == 35
    assert by["Old"]["ended"]  # due on 2026-03-05, now 2026-06-15
    assert by["Fresh"]["new"] and not by["Fresh"]["ended"]
    assert by["Insurance"]["period"] == 12 and by["Insurance"]["next"] == "2027-03-18"
    assert r["monthly"] == 0  # nothing confirmed yet
    assert by["Insurance"]["higher"]
    confirmed = "".join(f'2026-01-01 custom "recurring" "{p}" "include" "{w}"\n'
                        for p, w in [("Stream", "monthly"), ("Gym", "monthly"), ("Old", "monthly"), ("Fresh", "monthly"),
                                     ("Insurance", "yearly")])
    assert find(pays, confirmed)[0]["monthly"] == round(12.99 + 30 + 9 + 246 / 12, 2)  # the median; Old ended
    assert list(by)[0] == "Gym"  # the largest per month first


def test_irregular_and_one_off_are_not_recurring():
    groceries = [(dt.date(2026, 1, 1) + dt.timedelta(days=d), "Grocer", 20 + d % 7) for d in (0, 3, 4, 11, 19, 20, 33, 41)]
    _, by = find(groceries + [(dt.date(2026, 2, 1), "Shop", 80)] + monthly("Varies", 10, dt.date(2025, 6, 1),
                                                                              dt.date(2026, 6, 1))[::2])
    assert "Grocer" not in by and "Shop" not in by
    # every second month: gaps of 61 days fit no period
    assert "Varies" not in by


def test_the_amounts_must_be_alike():
    pays = [(d, "Shop", n) for (d, _, _), n in zip(monthly("", 0, dt.date(2026, 1, 1), dt.date(2026, 6, 1)),
                                                   (10, 200, 15, 90, 40, 300))]
    assert "Shop" not in find(pays)[1]


def test_marks_ignore_and_include():
    pays = monthly("Stream", 12.99, dt.date(2025, 1, 1), dt.date(2026, 6, 1)) + [
        (dt.date(2026, 2, 3), "Club", 50), (dt.date(2026, 5, 2), "Club", 90),  # unlike amounts: not found
        (dt.date(2026, 6, 1), "Once", 20)]
    r, by = find(pays)
    assert {o["payee"]: o["period"] for o in r["others"]} == {"Club": 3, "Once": None}  # the period the gaps suggest
    r, by = find(pays, '2026-01-01 custom "recurring" "Stream" "ignore"\n'
                       '2026-01-01 custom "recurring" "Club" "include" "quarterly"\n'
                       '2026-01-01 custom "recurring" "Once" "include" "yearly"\n')
    assert by["Stream"]["state"] == "ignored" and not by["Stream"]["manual"]
    assert by["Club"]["state"] == "confirmed" and by["Club"]["manual"] and by["Club"]["typical"] == 70
    assert by["Once"]["next"] == "2027-06-01" and not by["Once"]["higher"]
    assert r["others"] == [] and r["monthly"] == round(70 / 3 + 20 / 12, 2)
    r, by = find(pays, '2026-01-01 custom "recurring" "Stream" "include" "monthly"\n')
    assert by["Stream"]["state"] == "confirmed" and not by["Stream"]["manual"]  # found, and confirmed
    entries, options = ledger(pays, '2026-01-01 custom "recurring" "Stream" "include" "monthly"\n')
    t = dashboard.transactions(entries, options, lambda c, d: None, "2026-06", "2026-06", "Expenses")
    assert {m["payee"]: m["recurring"] for m in t["merchants"]} == {"Stream": True, "Once": False}


def test_set_written_replaced_and_removed(tmp_path):
    rules = tmp_path / "rules.beancount"
    head = "; Rules\n\n"
    rule = '2000-01-01 custom "rule" "x" Expenses:Other\n'
    rules.write_text(head + rule)
    edit.set_recurring(tmp_path, [["Stream", "ignore", None]])
    edit.set_recurring(tmp_path, [["Stream", "ignore", None]])  # once
    text = rules.read_text()
    assert text.count('custom "recurring" "Stream" "ignore"') == 1 and text.index('"recurring"') < text.index('"rule"')
    what = edit.set_recurring(tmp_path, [["Stream", "include", "monthly"], ["Gym", "include", "yearly"]])
    assert what == "Stream: include monthly; Gym: include yearly"
    assert dashboard.marks(loader.load_file(str(rules))[0]) == {"Stream": ("include", 1), "Gym": ("include", 12)}
    edit.set_recurring(tmp_path, [["Stream", None, None], ["Gym", None, None]])
    assert rules.read_text() == head + rule
    for bad in [("include", None), ("ignore", "monthly"), ("keep", None)]:
        with pytest.raises(edit.EditError):
            edit.set_recurring(tmp_path, [["Stream", *bad]])


def test_ended_by_the_accounts_that_paid():
    # the other bank's statements end in March: its payments are not late, the first bank's are
    pays = ([(d, "Card", n, "Assets:Other") for d, _, n in monthly("Card", 9, dt.date(2025, 1, 1), dt.date(2026, 3, 1))]
            + monthly("Stream", 12.99, dt.date(2025, 1, 1), dt.date(2026, 3, 1))
            + [(dt.date(2026, 6, 10), "Shop", 5)])
    entries, options = ledger(pays, '2026-06-12 * "Paid off the card"\n  Assets:Bank  -100.00 EUR\n'
                                    '  Assets:Other  100.00 EUR\n')  # a transfer in June: not a statement of Other
    by = {p["payee"]: p for p in dashboard.recurring(entries, options, lambda c, d: None, TODAY)["payees"]}
    assert not by["Card"]["ended"] and by["Stream"]["ended"]


def test_nothing_new_in_a_young_ledger():
    pays = monthly("Stream", 12.99, dt.date(2026, 4, 1), dt.date(2026, 6, 1))
    assert not find(pays)[1]["Stream"]["new"]
    assert find(pays + [(dt.date(2025, 1, 1), "Old shop", 3)])[1]["Stream"]["new"]


def test_set_keeps_a_rules_comment_and_a_payee_with_quotes(tmp_path):
    rules = tmp_path / "rules.beancount"
    rule = '; Lidl: from the app, 2026-01-01\n2000-01-01 custom "rule" "x" Expenses:Other\n'
    rules.write_text("; Rules\n; DATE custom \"recurring\" ...: what the lines mean\n" + rule)
    edit.set_recurring(tmp_path, [['Bar "U Jana" \\ 2', "include", "monthly"]])
    text = rules.read_text()
    head = '; Rules\n; DATE custom "recurring" ...: what the lines mean\n'
    assert text.endswith("\n\n" + head + rule)  # one paragraph: above it, not inside
    assert dashboard.marks(loader.load_file(str(rules))[0]) == {'Bar "U Jana" \\ 2': ("include", 1)}
    edit.set_recurring(tmp_path, [['Bar "U Jana" \\ 2', None, None]])
    assert rules.read_text() == "; Rules\n; DATE custom \"recurring\" ...: what the lines mean\n" + rule


def test_lines_and_rules_keep_the_templates_comments(tmp_path):
    """In a new ledger (the template's rules.beancount, no rule yet) and after rules the app added: each line goes in
    a paragraph of its own, so no comment is split from what it explains."""
    template = Path(__file__).parent.parent / "template" / "rules.beancount"
    rules = tmp_path / "rules.beancount"
    rules.write_text(template.read_text())
    paragraphs = lambda: [p.strip("\n") for p in rules.read_text().split("\n\n") if p.strip()]  # noqa: E731
    before = paragraphs()
    edit.set_recurring(tmp_path, [["Stream", "include", "monthly"]])
    assert all(p in paragraphs() for p in before)  # the template's paragraphs, whole
    edit.set_recurring(tmp_path, [["Stream", None, None]])
    assert rules.read_text() == template.read_text()
    e = parser.parse_string('2026-01-01 * "Lidl" ""\n  iban: "SK0011"\n  Assets:Bank  -1.00 EUR\n  Expenses:Other\n')[0][0]
    edit.add_rule(tmp_path, e, "Expenses:Other")  # the first rule: at the end
    rule = next(p for p in paragraphs() if "from the app" in p)
    assert paragraphs()[-1] == rule  # without rules, at the end: after the template's comment on these lines
    assert rule.startswith("; SK0011: from the app") and rule.count("\n") == 1  # its comment and itself
    for name in ("Stream", "Gym"):
        edit.set_recurring(tmp_path, [[name, "ignore", None]])
    other = parser.parse_string('2026-01-01 * "Shop" ""\n  iban: "SK0022"\n  Assets:Bank  -1.00 EUR\n  Expenses:Other\n')
    edit.add_rule(tmp_path, other[0][0], "Expenses:Other")  # a second rule goes above the first, its comment with it
    now = paragraphs()
    assert all(p in now for p in [*before, rule]) and now.index(rule) > now.index(rule.replace("SK0011", "SK0022"))
    assert len(loader.load_file(str(rules))[1]) == 0 and dashboard.marks(loader.load_file(str(rules))[0]) == {
        "Stream": ("ignore", None), "Gym": ("ignore", None)}
