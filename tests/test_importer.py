import datetime as dt
import re
from decimal import Decimal

from kingsmint.banks.common import Txn, sk_num
from kingsmint.importer import categorize

D = dt.date(2025, 6, 1)
OWN = {"SK11": (dt.date.max, "EUR"), "SK22": (dt.date.max, "USD"), "SK33": (dt.date(2025, 1, 1), "EUR")}
RULES = [(dt.date(2025, 1, 1), re.compile(r"\bLidl\b", re.I), "Expenses:Food:Groceries", []),
         (dt.date(2000, 1, 1), re.compile("Lidl|Shell", re.I), "Expenses:Transport:Fuel", []),
         (dt.date(2000, 1, 1), re.compile(r"\| -10\.00$"), "Expenses:Gifts", [("Expenses:Taxes:VAT", Decimal("0.2"))])]


def cat(payee, amount="-10.00", iban="", date=D):
    return categorize(Txn(date, Decimal(amount), payee, "", iban), OWN, RULES)


def test_own_accounts():
    assert cat("", iban="SK11")[0] == "Assets:Transit"
    assert cat("", iban="SK22")[0] == "Equity:Conversions"
    assert cat("Shell", iban="SK33")[0] == "Expenses:Transport:Fuel"  # after statements_until: rules decide


def test_rules():
    assert cat("Lidl 185")[0] == "Expenses:Food:Groceries"
    assert cat("Lidl 185", date=dt.date(2024, 1, 1))[0] == "Expenses:Transport:Fuel"  # first rule not yet valid
    assert cat("Lidlova", "-5.00")[0] == "Expenses:Transport:Fuel"  # \b keeps the first rule off
    assert cat("Somebody") == ("Expenses:Gifts", [("Expenses:Taxes:VAT", Decimal("0.2"))])
    assert cat("Somebody", "-11.00")[0] == "Expenses:Uncategorized"
    assert cat("Somebody", "11.00")[0] == "Income:Uncategorized"


def test_sk_num():
    assert sk_num("-5.989,27") == Decimal("-5989.27")
    assert sk_num("-2 500,00") == Decimal("-2500.00")
