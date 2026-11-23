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


def test_payee_rules(monkeypatch):
    from kingsmint import importer
    from kingsmint.banks.common import Statement

    monkeypatch.setattr(importer, "NAMES", [(D, re.compile(r"^Lidl\b", re.I), "Lidl", "rules.beancount:1")])
    txns = [Txn(D, Decimal("-10.00"), "LIDL dakuje 185 MESTO", "Platba kartou"),
            Txn(D, Decimal("-5.00"), "Lidl", "Platba kartou"),
            Txn(D, Decimal("-7.00"), "Bakery", "Platba kartou")]
    out = importer.render(Statement("SK00", Decimal(0), Decimal("-22.00"), D, D, txns), "Assets:Bank", {}, RULES, "s.csv")
    first, second, third = out.split("\n\n")[2:5]
    assert first.startswith('2025-06-01 * "Lidl" "Platba kartou"') and 'bank_payee: "LIDL dakuje 185 MESTO"' in first
    assert "Expenses:Food:Groceries" in first  # the category rule matches the bank's text
    assert '"Lidl"' in second and "bank_payee" not in second  # the name the bank wrote: nothing to keep
    assert '"Bakery"' in third and "bank_payee" not in third


def test_payee_rules_in_preview(tmp_path, monkeypatch, capsys):
    import shutil
    from pathlib import Path

    from kingsmint import importer

    shutil.copytree(Path(__file__).parent.parent / "template", tmp_path, dirs_exist_ok=True)
    with (tmp_path / "accounts.beancount").open("a", encoding="utf-8") as f:
        f.write('2000-01-01 open Assets:Me:Bank:Current EUR\n  iban: "SK00"\n2000-01-01 open Expenses:Uncategorized\n'
                "2000-01-01 open Expenses:Food\n2000-01-01 open Expenses:Shop\n")
    with (tmp_path / "rules.beancount").open("a", encoding="utf-8") as f:
        f.write('2020-01-01 custom "payee" "^LIDL" "Lidl"\n2000-01-01 custom "payee" "^LIDL 232" "Other"\n'
                '2000-01-01 custom "payee" "^SHOP" "Shop"\n'
                '2000-01-01 custom "rule" "^LIDL \\\\d" Expenses:Food\n2000-01-01 custom "rule" "^SHOP" Expenses:Shop\n')

    def entry(tid, payee, account, meta=""):
        return f'2025-06-01 * "{payee}" "Card"\n  id: "{tid}"\n{meta}  Assets:Me:Bank:Current  -10.00 EUR\n  {account}\n'
    renamed = entry("km-1", "Lidl", "Expenses:Food", '  bank_payee: "LIDL 185 TOWN"\n')  # nothing to change
    both = entry("km-2", "LIDL 232 CITY", "Expenses:Uncategorized")  # renamed and moved: one transaction
    base = entry("km-3", "SHOP 1", "Expenses:Shop")
    bare = entry("km-4", "X", "Expenses:Uncategorized").replace('"X" ', "")  # the bank gave no payee; the user adds one
    for folder, shop, plain in [("ledger", base.replace('"SHOP 1"', '"My shop"'), bare.replace('* "Card"', '* "Neighbour" "Card"')),
                                (".kingsmint/base/ledger", base, bare)]:
        (tmp_path / folder / "A").mkdir(parents=True, exist_ok=True)
        (tmp_path / folder / "A/2025-06.beancount").write_text(
            "; generated by kingsmint\n\n" + "\n".join([renamed, both, shop, plain]), encoding="utf-8")
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    monkeypatch.setattr(importer, "LEDGER", tmp_path / "main.beancount")

    importer.load()
    assert [name for _, _, name, _ in importer.NAMES] == ["Lidl", "Other", "Shop"]  # file order, not date order
    importer.preview()
    out = capsys.readouterr().out
    assert "rules.beancount:25  Expenses:Uncategorized -> Expenses:Food  1" in out
    assert "rules.beancount:22  payee 'LIDL 232 CITY' -> 'Lidl'  1" in out
    assert "no rule" not in out and "My shop" not in out  # km-1 and km-3 match the bank's text; km-3's name stays
    assert "1 transactions would change" in out
