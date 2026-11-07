import datetime as dt
import re
from decimal import Decimal

from kingsmint.banks.common import Txn, reference, sk_num
from kingsmint.banks.sk import tatra
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


def test_rule_vs():
    rules = [(dt.date(2000, 1, 1), re.compile(r"^VS123$"), "Expenses:Gas", [])]
    assert categorize(Txn(D, Decimal("-5"), vs="123"), {}, rules)[0] == "Expenses:Gas"
    assert categorize(Txn(D, Decimal("-5"), vs="1234"), {}, rules)[0] == "Expenses:Uncategorized"


def test_rule_ref():
    rules = [(dt.date(2000, 1, 1), re.compile(r"^RF18"), "Expenses:Gas", [])]
    assert categorize(Txn(D, Decimal("-5"), ref="RF18 5390"), {}, rules)[0] == "Expenses:Gas"
    assert categorize(Txn(D, Decimal("-5"), narration="RF18 5390"), {}, rules)[0] == "Expenses:Uncategorized"


def test_reference():
    assert (reference(Txn(D, 0), " /VS123/SS/KS0308 ").vs, reference(Txn(D, 0), "/VS123").ref) == ("123", "")
    assert reference(Txn(D, 0, vs="9"), "/VS/SS/KS").vs == "9"  # an empty VS keeps the one from a column
    assert reference(Txn(D, 0), "RF18 5390").ref == "RF18 5390"
    assert [reference(Txn(D, 0), s).vs for s in ["?/VS12/SS0046/KS0046", "VS12/SS/KS"]] == ["12", "12"]
    assert [reference(Txn(D, 0), s).ref for s in ["NOTPROVIDED", "Not provided", "NOT PROVIDED"]] == ["", "", ""]


def test_sk_num():
    assert sk_num("-5.989,27") == Decimal("-5989.27")
    assert sk_num("-2 500,00") == Decimal("-2500.00")


def test_tatra_csv_card():
    row = {"Dátum spracovania": "03.01.2025", "Suma": "12,50", "Typ": "Debet", "Popis": "Platba kartou", "IBAN": "",
           "Informácia pre príjemcu": "123456******7890 BRATISLAVA JAN NOVAK 20250102 10:00:00 12.50EUR SHOP ONE"}
    assert tatra.parse_csv([row])[0][0].payee == "SHOP ONE"
    assert tatra.parse_csv([{**row, "Informácia pre príjemcu": "Vklad"}])[0][0].payee == ""
    assert tatra.parse_csv([{**row, "Variabilný symbol": " 123 "}])[0][0].vs == "123"


def test_tatra_pdf_vs():
    t = tatra.tb_txn(Txn(D, Decimal("-5")), ["   Referencia platiteľa:   /VS123/SS/KS"])
    assert t.vs == "123"
