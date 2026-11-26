"""Budgets (app/server/budgets.py) on a small synthetic ledger: what the app shows, and what it writes."""
import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from beancount import loader

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import budgets

MAIN = """option "operating_currency" "EUR"
include "budgets.beancount"
2020-01-01 open Assets:Me:Bank EUR
2020-01-01 open Expenses:Cash
2020-01-01 open Expenses:Food:Groceries
2020-01-01 open Expenses:Food:Restaurants
2020-01-01 open Expenses:Home
2026-10-03 * "Lidl"
  Assets:Me:Bank  -150.00 EUR
  Expenses:Food:Groceries
2026-11-02 * "Lidl"
  Assets:Me:Bank  -200.00 EUR
  Expenses:Food:Groceries
2026-11-10 * "Bistro"
  Assets:Me:Bank  -100.00 EUR
  Expenses:Food:Restaurants
2026-01-15 * "Ploty s.r.o." "advance before the budget" #fence
  Assets:Me:Bank  -999.00 EUR
  Expenses:Home
2026-02-10 * "Ploty s.r.o." "advance" #fence
  Assets:Me:Bank  -3000.00 EUR
  Expenses:Home
2026-06-01 * "Ploty s.r.o." "advance" #fence
  Assets:Me:Bank  -2000.00 EUR
  Expenses:Home
2026-06-02 * "Worker" "cash for the posts, named in cash.beancount" #fence
  Expenses:Cash  -500.00 EUR
  Expenses:Home
"""

BUDGETS = """2026-01-01 custom "budget" Expenses:Food "monthly" 400.00 EUR
2026-11-01 custom "budget" Expenses:Food "monthly" 600.00 EUR
2026-02-01 custom "budget-tag" "fence" 8000.00 EUR 2026-12-31 "New fence"
"""

TODAY = dt.date(2026, 11, 21)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "main.beancount").write_text(MAIN)
    (tmp_path / "budgets.beancount").write_text(BUDGETS)
    return tmp_path


def load(root, offset=0, today=TODAY):
    entries, errors, options = loader.load_file(str(root / "main.beancount"))
    assert not errors
    return budgets.overview(entries, options, lambda c, d: None, offset, today), entries


def test_account_budget_now_and_before(root):
    b, _ = load(root)
    food = b["accounts"][0]
    # November: the newer entry, the subaccount counted in, 10 days left with today
    assert (food["account"], food["limit"], food["spent"], food["left"]) == ("Expenses:Food", 600.0, 300.0, 300.0)
    assert (food["start"], food["end"], food["days_left"], food["per_day"]) == ("2026-11-01", "2026-11-30", 10, 30.0)
    assert (food["period"], food["amount"], food["since"], food["state"]) == ("monthly", 600.0, "2026-11-01", "good")
    october = load(root, -1)[0]["accounts"][0]
    assert (october["start"], october["limit"], october["spent"], october["days_left"]) == ("2026-10-01", 400.0, 150.0, 0)


def test_limit_as_fava_prorates_it(root):
    """A new limit from the middle of the month: Fava's own computation, by days."""
    (root / "budgets.beancount").write_text(BUDGETS + '2026-11-16 custom "budget" Expenses:Food "monthly" 300.00 EUR\n')
    food = load(root)[0]["accounts"][0]
    assert food["limit"] == pytest.approx(600 * 15 / 30 + 300 * 15 / 30)
    assert food["amount"] == 300.0


def test_zero_ends_a_budget(root):
    (root / "budgets.beancount").write_text(BUDGETS + '2026-11-01 custom "budget" Expenses:Food "monthly" 0 EUR\n')
    b, _ = load(root)
    assert b["accounts"] == [] and load(root, -1)[0]["accounts"][0]["limit"] == 400.0


def test_tag_budget_with_its_payments(root):
    b, _ = load(root)
    fence = b["tags"][0]
    # from its start date: the advance before it does not count; the cash payment does
    assert (fence["tag"], fence["name"], fence["spent"], fence["left"]) == ("fence", "New fence", 5500.0, 2500.0)
    assert [(p["date"], p["amount"]) for p in fence["payments"]] == [
        ("2026-06-02", 500.0), ("2026-06-01", 2000.0), ("2026-02-10", 3000.0)]
    assert (fence["days_left"], fence["per_day"]) == (41, round(2500 / 41, 2))
    assert b["used"] == ["fence"]


def test_state():
    s = budgets.state
    assert s(Decimal(101), Decimal(100), Decimal("0.5")) == "bad"
    assert s(Decimal(75), Decimal(100), Decimal("0.9")) == "warn"  # 75 %
    assert s(Decimal(50), Decimal(100), Decimal("0.3")) == "warn"  # ahead of the days
    assert s(Decimal(35), Decimal(100), Decimal("0.3")) == "good"
    assert s(Decimal(70), Decimal(100), None) == "good"  # a tag without an end: no days


def test_set_account_replaces_from_its_date(root):
    _, entries = load(root)
    budgets.set_account(root, entries, "EUR", "Expenses:Food", "quarterly", "1 500,5", today=TODAY)
    text = (root / "budgets.beancount").read_text()
    # the November entry goes: one budget per account from the quarter's start; the older one stays before it
    assert text.count('"budget" Expenses:Food') == 2
    assert text.endswith('2026-10-01 custom "budget" Expenses:Food "quarterly" 1500.50 EUR\n')
    food = load(root)[0]["accounts"][0]
    assert (food["period"], food["start"], food["end"], food["limit"]) == ("quarterly", "2026-10-01", "2026-12-31", 1500.5)
    assert budgets.set_account(root, load(root)[1], "EUR", "Expenses:Food", "monthly", 0, "2026-12-01") \
        == "Expenses:Food ends 2026-12-01"
    assert load(root, today=dt.date(2026, 12, 5))[0]["accounts"] == []


def test_set_account_refuses_bad_input(root):
    _, entries = load(root)
    assert budgets.expense_accounts(entries) == [
        "Expenses:Cash", "Expenses:Food", "Expenses:Food:Groceries", "Expenses:Food:Restaurants", "Expenses:Home"]
    for bad in (("Expenses:Home", "monthly", "nan"), ("Expenses:Home", "monthly", "inf"), ("Expenses:Nope", "monthly", 1), ("Expenses", "monthly", 1), ("Assets:Me:Bank", "monthly", 1), ("Expenses:Home", "weekly", 1),
                ("Expenses:Home", "monthly", -1), ("Expenses:Home", "monthly", "x")):
        with pytest.raises(budgets.BudgetError):
            budgets.set_account(root, entries, "EUR", *bad)
    assert (root / "budgets.beancount").read_text() == BUDGETS


def test_set_tag(root):
    tag, what = budgets.set_tag(root, "EUR", "Záloha plot", "300", "2026-03-01", None, "Záloha")
    assert (tag, what) == ("zaloha-plot", "#zaloha-plot 300.00 EUR from 2026-03-01")
    with pytest.raises(budgets.BudgetError, match="already"):  # a new one, or a rename, onto a tag with a budget
        budgets.set_tag(root, "EUR", "fence", 1, "2026-02-01", old="zaloha-plot")
    budgets.set_tag(root, "EUR", "fence", 9000, "2026-02-01", "2027-03-31", "New fence", old="fence")
    text = (root / "budgets.beancount").read_text()
    assert text.count('"budget-tag" "fence"') == 1
    assert '2026-02-01 custom "budget-tag" "fence" 9000.00 EUR 2027-03-31 "New fence"\n' in text
    assert '"zaloha-plot" 300.00 EUR "Záloha"' in text
    assert budgets.set_tag(root, "EUR", "fence", 0, "2026-02-01")[1] == "#fence removed"
    assert [t["tag"] for t in load(root)[0]["tags"]] == ["zaloha-plot"]
    with pytest.raises(budgets.BudgetError):
        budgets.set_tag(root, "EUR", "x", 10, "2026-03-01", "2026-02-01")
    with pytest.raises(budgets.BudgetError):
        budgets.set_tag(root, "EUR", "ščť!", 10, "2026-03-01", name='a "quote"')


def test_no_file(tmp_path):
    with pytest.raises(budgets.BudgetError, match="kingsmint upgrade"):
        budgets.set_tag(tmp_path, "EUR", "x", 1, "2026-01-01")


def test_averages(root):
    """The average month of the last 12, by the limit in the form: a parent sums its subaccounts."""
    avg = load(root)[0]["averages"]
    assert avg["Expenses:Food:Groceries"] == round(350 / 12, 2)
    assert avg["Expenses:Food"] == round(450 / 12, 2)
    assert avg["Expenses:Home"] == round((999 + 3000 + 2000 + 500) / 12, 2)
    assert "Expenses:Cash" not in avg  # it only gives money on to the categories


def test_tag_budget_that_cannot_count(root):
    """A hand-written entry that ends the day before it starts, or has a limit below 0: an error, not a crash."""
    (root / "budgets.beancount").write_text(BUDGETS + '2026-02-01 custom "budget-tag" "x" 100.00 EUR 2026-01-31\n'
                                            '2026-02-01 custom "budget-tag" "y" -5.00 EUR\n')
    b, _ = load(root)
    assert [t["tag"] for t in b["tags"]] == ["fence"] and len(b["errors"]) == 2
