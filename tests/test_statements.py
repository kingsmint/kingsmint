"""End to end: fake statements of every supported bank -> `kingsmint import` -> a valid ledger."""
import shutil
import subprocess
import sys
from pathlib import Path

from pdf import text_pdf

HERE = Path(__file__).parent
ACCOUNTS = """
2000-01-01 open Assets:Me:VUB:Current EUR
  iban: "SK3102000000001234567890"
2000-01-01 open Assets:Me:VUB:Savings EUR
  iban: "SK0702000000009876543210"
2000-01-01 open Assets:Me:Tatra:Current EUR
  iban: "SK5511000000002912345678"
2000-01-01 open Assets:Me:Tatra:Second EUR
  iban: "SK5511000000002912345679"
2000-01-01 open Assets:Co:Tatra:Current EUR
  iban: "SK6611000000002987654321"
2000-01-01 open Assets:Co:Fio:Current EUR
  iban: "SK2083300000002012345678"
2000-01-01 open Assets:Me:IBKR:Cash
  ibkr: "U1234567"
2000-01-01 open Assets:Me:IBKR:Securities "FIFO"
2000-01-01 open Income:Investments:Gains
2000-01-01 open Income:Investments:Interest
2000-01-01 open Expenses:Investments:Fees
2000-01-01 open Expenses:Taxes:Withholding
2000-01-01 open Expenses:Food:Groceries
""" + "".join(f"2000-01-01 pad {a} Equity:Opening-Balances\n"  # the first statements do not start at 0
              for a in ["Assets:Me:VUB:Current", "Assets:Me:Tatra:Current", "Assets:Me:Tatra:Second", "Assets:Co:Fio:Current"])


def kingsmint(ledger, *args):
    return subprocess.run([sys.executable, "-c", "from kingsmint.cli import main; main()", *args], cwd=ledger,
                          capture_output=True, text=True, encoding="utf-8")


def test_import_every_bank(tmp_path):
    ledger = tmp_path / "ledger"
    shutil.copytree(HERE.parent / "template", ledger)
    main = ledger / "main.beancount"  # what /kingsmint:setup fills in
    main.write_text(main.read_text(encoding="utf-8").replace("TITLE", "Test").replace("CURRENCY", "EUR")
                    .replace("LOCALE", "sk_SK"), encoding="utf-8")
    with (ledger / "rules.beancount").open("a", encoding="utf-8") as f:
        f.write('\n2000-01-01 custom "rule" "\\\\bLidl\\\\b" Expenses:Food:Groceries\n')
    for src in (HERE / "statements").iterdir():
        if src.suffix == ".txt":
            text_pdf(ledger / "inbox" / f"{src.stem}.pdf", src.read_text(encoding="utf-8"))
        else:
            shutil.copy(src, ledger / "inbox")
    scan = kingsmint(ledger, "scan").stdout  # what /kingsmint:setup proposes the accounts from, before they exist
    for expected in ["fio.pdf  fio  SK2083300000002012345678  EUR  2025-06-01..2025-06-30  holder: Demo s.r.o.  "
                     "type: BU - běžný účet  -> NEW\n",
                     "tatra.pdf  tatra  SK5511000000002912345678  EUR  2025-06-01..2025-06-30  holder: Tester Test, Ing.  "
                     "type: Osobný účet  -> NEW\n",
                     "holder: Tester Test  type: bežný účet  -> NEW\n", "holder: TEST TESTER  type: BEŽNÝ ÚČET  -> NEW\n",
                     "ibkr.csv  ibkr  U1234567  EUR  2025-01-01..2025-12-31  holder: Tester Test  ", "SK6611000000002987654321.csv  tatra csv  SK6611000000002987654321  "]:
        assert expected in scan, scan
    with (ledger / "accounts.beancount").open("a", encoding="utf-8") as f:
        f.write(ACCOUNTS)

    run = kingsmint(ledger, "import")
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == 9 and all(line.startswith("ok ") for line in lines), run.stdout  # the savings CSV: 2023, 2024 (no movements), 2025
    assert not [f for f in (ledger / "inbox").iterdir() if f.name != ".keep"]  # all archived
    empty = (ledger / "ledger/Assets-Me-VUB-Savings/csv-2024.beancount").read_text(encoding="utf-8")
    assert "2024-01-01 balance Assets:Me:VUB:Savings 0.00 EUR" in empty and " * " not in empty  # a year without movements
    # the January transfers from VUB Current have no other side: its statements start in June
    check = kingsmint(ledger, "check")
    assert check.stdout.startswith("FAIL Assets:Transit is -11100.00 EUR since 2025-01-02:") and check.stdout.count("\n") == 1, \
        check.stdout + check.stderr
    coverage = kingsmint(ledger, "coverage").stdout
    assert "Assets:Me:VUB:Current  2025-06-01 .. 2025-06-30  missing 2025-07-01 .. " in coverage  # up to last month
    assert "Assets:Me:IBKR:Cash  2025-01-01 .. 2025-12-31  missing 2026-01-01 .. " in coverage, coverage
    assert kingsmint(ledger, "import").stdout.startswith("nothing to import in ")

    out = "".join(f.read_text(encoding="utf-8") for f in sorted((ledger / "ledger").rglob("*.beancount")))
    for expected in ['"Lidl Bratislava" "Platba kartou"\n  document: "2025-06-01_2025-06-30.SK3102000000001234567890.pdf"\n  Assets:Me:VUB:Current  -45.20 EUR\n'
                     '  Expenses:Food:Groceries\n',  # VUB
                     '"Example s.r.o." "Mzda 05/2025"', '"Jana Testová" "Nájom 06/2025"',
                     '"Zeleninarstvo T Testovo"',  # a 13-letter merchant name is not the bank reference
                     '"Lidl 123"', '"Test Payer"', '"Kaufland"',  # Tatra
                     '"Client Ltd" "Faktura 2025-01"', '"Alza.sk"',  # FIO
                     "Assets:Me:IBKR:Securities  50 VWCE {{5000 EUR}}",  # IBKR
                     '"Buy 50 VWCE"\n  document: "2025-01-01_2025-12-31.U1234567.csv"',
                     'document: "2025-01-03_2025-02-05.SK6611000000002987654321.csv"',  # CSV
                     'iban: "SK1209000000005123456789"',  # counterparty
                     "Assets:Transit"]:  # transfers from an own account
        assert expected in out, expected

    # `rules` previews a rule change; `reimport` applies it and drops files of accounts that no longer exist
    assert kingsmint(ledger, "rules").stdout == "no changes\n"  # the preview categorizes like the import
    with (ledger / "rules.beancount").open("a", encoding="utf-8") as f:
        f.write('2000-01-01 custom "rule" "Kaufland" Expenses:Food:Groceries\n')
    preview = kingsmint(ledger, "rules").stdout
    assert "rules.beancount:" in preview and "Expenses:Uncategorized -> Expenses:Food:Groceries  1\n" in preview \
        and "Kaufland" in preview, preview
    stale = ledger / "ledger/Assets-Renamed/2025-06.beancount"
    stale.parent.mkdir()
    stale.write_text("; generated by kingsmint from old.pdf\n", encoding="utf-8")
    assert kingsmint(ledger, "reimport").returncode == 0
    assert not stale.parent.exists() and (ledger / "ledger/README/README.beancount").exists()
    assert kingsmint(ledger, "rules").stdout == "no changes\n"

    # the archive name comes from the statement: a second copy is dropped, another file for the period is refused
    vub = ledger / "documents/Assets/Me/VUB/Current/2025-06-01_2025-06-30.SK3102000000001234567890.pdf"
    shutil.copy(vub, ledger / "inbox/statement.pdf")
    assert kingsmint(ledger, "import", "--force").stdout.startswith("ok   statement.pdf")
    assert not (ledger / "inbox/statement.pdf").exists()
    text_pdf(ledger / "inbox/statement.pdf", (HERE / "statements/vub.txt").read_text(encoding="utf-8") + "other text\n")
    run = kingsmint(ledger, "import", "--force").stdout
    assert run.startswith("FAIL statement.pdf: documents/") and "another statement for the same account" in run, run
    assert (ledger / "inbox/statement.pdf").exists()
