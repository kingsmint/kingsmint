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
    with (ledger / "accounts.beancount").open("a", encoding="utf-8") as f:
        f.write(ACCOUNTS)
    with (ledger / "rules.beancount").open("a", encoding="utf-8") as f:
        f.write('\n2000-01-01 custom "rule" "\\\\bLidl\\\\b" Expenses:Food:Groceries\n')
    for src in (HERE / "statements").iterdir():
        if src.suffix == ".txt":
            text_pdf(ledger / "inbox" / f"{src.stem}.pdf", src.read_text(encoding="utf-8"))
        else:
            shutil.copy(src, ledger / "inbox")

    run = kingsmint(ledger, "import")
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == 7 and all(line.startswith("ok ") for line in lines), run.stdout
    assert not [f for f in (ledger / "inbox").iterdir() if f.name != ".keep"]  # all archived
    check = kingsmint(ledger, "check")
    assert check.returncode == 0 and not check.stdout + check.stderr, check.stdout + check.stderr

    out = "".join(f.read_text(encoding="utf-8") for f in sorted((ledger / "ledger").rglob("*.beancount")))
    for expected in ['"Lidl Bratislava" "Platba kartou"\n  document: "2025-06-30.vub.pdf"\n  Assets:Me:VUB:Current  -45.20 EUR\n'
                     '  Expenses:Food:Groceries\n',  # VUB
                     '"Example s.r.o." "Mzda 05/2025"', '"Jana Testová" "Nájom 06/2025"',
                     '"Lidl 123"', '"Test Payer"', '"Kaufland"',  # Tatra
                     '"Client Ltd" "Faktura 2025-01"', '"Alza.sk"',  # FIO
                     "Assets:Me:IBKR:Securities  50 VWCE {{5000 EUR}}",  # IBKR
                     '"Buy 50 VWCE"\n  document: "2025-12-31.ibkr.csv"',
                     'document: "2025-02-05.SK6611000000002987654321.csv"',  # CSV
                     "Assets:Transit"]:  # transfers from an own account
        assert expected in out, expected
