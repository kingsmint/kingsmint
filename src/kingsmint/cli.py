"""usage: uv run kingsmint COMMAND   (in the ledger directory)

  import [--force] [PATH ...]  import new statements from inbox/ (or PATHs)
  reimport                     rebuild ledger/ from documents/, re-applying the rules
  check                        validate the ledger, and that transfers between own accounts have both sides
  coverage                     the periods each account's imported statements cover, and the gaps
  fava [FAVA OPTIONS]          open Fava on http://localhost:5050
  rates                        refresh month-end USD/EUR rates from the ECB
  doctor                       check the tools and the ledger files
"""

import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

from beancount import loader
from beancount.core import data, inventory
from beancount.parser import printer

from kingsmint import importer, rates


def run(cmd):
    try:
        sys.exit(subprocess.run(cmd).returncode)
    except KeyboardInterrupt:  # Ctrl+C stops the child too; exit without a traceback
        sys.exit(130)


TOOLS = [  # (any of these programs, why, where to get it)
    (["jj", "git"], "version control of the ledger", "https://jj-vcs.github.io/jj/latest/install-and-setup/ or https://git-scm.com/downloads"),
    (["curl"], "`kingsmint rates` downloads with it", "included in macOS, Windows 10+, and most Linux; https://curl.se/download.html"),
    (["claude"], "the kingsmint skills run in Claude Code", "https://claude.com/claude-code"),
]
LEDGER = ["main.beancount", "accounts.beancount", "rules.beancount", "inbox", "documents"]
PLACEHOLDERS = ["TITLE", "CURRENCY", "LOCALE"]  # in template/main.beancount, filled by /kingsmint:setup


def coverage(entries):
    """{account: [(first, last), ...]}: the days each imported statement covers, from the importer's balances."""
    spans = {}
    for e in entries:
        if isinstance(e, data.Balance) and Path(e.meta["filename"]).parent.parent.name == "ledger":
            first, last = spans.get((e.account, e.meta["filename"]), (e.date, e.date))
            spans[(e.account, e.meta["filename"])] = (min(first, e.date), max(last, e.date))
    out = {}
    for (account, _), (first, last) in sorted(spans.items(), key=lambda kv: kv[1]):
        # the closing balance is dated the day after the statement; an IBKR report has one balance date
        out.setdefault(account, []).append((first, last - dt.timedelta(days=1) if last > first else last))
    return out


def gaps(spans):
    return [(a[1] + dt.timedelta(days=1), b[0] - dt.timedelta(days=1)) for a, b in zip(spans, spans[1:])
            if a[0] < a[1] and b[0] < b[1] and b[0] > a[1] + dt.timedelta(days=1)]


def transit(entries):
    """Assets:Transit balance on the last day every current account is imported; not empty = a missing side."""
    ends = [spans[-1][1] for spans in coverage(entries).values()]
    if not ends:
        return None, inventory.Inventory()
    # shortcut: an account whose statements stop 2 months before the newest one counts as finished,
    # and transfers take up to a week; mark finished accounts with `statements_until` if this misfires
    day = min(d for d in ends if d >= max(ends) - dt.timedelta(days=62)) - dt.timedelta(days=7)
    total = inventory.Inventory()
    for e in entries:
        if isinstance(e, data.Transaction) and e.date <= day:
            for p in e.postings:
                if p.account == "Assets:Transit":
                    total.add_amount(p.units)
    return day, total


def check():
    entries, errors, _ = loader.load_file("main.beancount")
    printer.print_errors(errors)
    day, total = transit(entries)
    if not total.is_empty():
        print(f"FAIL Assets:Transit is {', '.join(str(p.units) for p in total)} on {day}: a transfer between own accounts has one side only; "
              "import the missing statement (see `uv run kingsmint coverage`)")
    sys.exit(1 if errors or not total.is_empty() else 0)


def show_coverage():
    entries = loader.load_file("main.beancount")[0]
    cov = coverage(entries)
    for e in entries:
        if isinstance(e, data.Open) and ("iban" in e.meta or "ibkr" in e.meta) and e.account not in cov:
            print(f"{e.account}  never imported")
    for account, spans in cov.items():
        missing = "".join(f"  missing {a} .. {b}" for a, b in gaps(spans))
        print(f"{account}  {spans[0][0]} .. {spans[-1][1]}{missing}")


def doctor():
    problems = 0

    def report(ok, name, hint):
        nonlocal problems
        problems += not ok
        print(f"ok   {name}" if ok else f"FAIL {name}: {hint}")

    for names, why, where in TOOLS:
        report(any(shutil.which(n) for n in names), " or ".join(names), f"{why}; install: {where}")
    missing = [f for f in LEDGER if not Path(f).exists()]
    report(not missing, "ledger files", f"missing {', '.join(missing)}; run in the ledger directory, or create one with /kingsmint:setup")
    if not missing:
        left = [p for p in PLACEHOLDERS if f'"{p}"' in Path("main.beancount").read_text(encoding="utf-8")]
        report(not left, "setup", f"{', '.join(left)} not replaced in main.beancount; see the setup skill")
        errors = loader.load_file("main.beancount")[1]
        report(not errors, "ledger", f"{len(errors)} errors; see `uv run kingsmint check`")
    sys.exit(1 if problems else 0)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "import":
        importer.main(args)
    elif cmd == "reimport":
        importer.main(["--force", "documents"])
    elif cmd == "check":
        check()
    elif cmd == "coverage":
        show_coverage()
    elif cmd == "fava":  # port 5050: 5000 is taken by AirPlay on macOS
        run(["fava", "--port", "5050", *args, "main.beancount"])
    elif cmd == "rates":
        rates.main()
    elif cmd == "doctor":
        doctor()
    else:
        sys.exit(__doc__)
