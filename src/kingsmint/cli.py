"""usage: uv run kingsmint COMMAND   (in the ledger directory)

  import [--force] [PATH ...]  import new statements from inbox/ (or PATHs)
  reimport                     rebuild ledger/ from documents/, re-applying the rules
  check                        validate the ledger
  fava [FAVA OPTIONS]          open Fava on http://localhost:5050
  rates                        refresh month-end USD/EUR rates from the ECB
  doctor                       check the tools and the ledger files
"""

import shutil
import subprocess
import sys
from pathlib import Path

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
        from beancount import loader

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
        run(["bean-check", "main.beancount"])
    elif cmd == "fava":  # port 5050: 5000 is taken by AirPlay on macOS
        run(["fava", "--port", "5050", *args, "main.beancount"])
    elif cmd == "rates":
        rates.main()
    elif cmd == "doctor":
        doctor()
    else:
        sys.exit(__doc__)
