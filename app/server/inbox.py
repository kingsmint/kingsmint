"""The inbox of a ledger: what `kingsmint scan` says of each statement in inbox/, and the imported periods with their
gaps (`kingsmint coverage`). The server calls the ledger's own kingsmint, so a ledger of an older kingsmint works too."""

import datetime
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from babel.dates import format_date


def kingsmint(ledger: Path, command: str, *args: str) -> str:
    """The output lines of a kingsmint command, its errors included."""
    exe = ledger / ".venv" / ("Scripts/kingsmint.exe" if sys.platform == "win32" else "bin/kingsmint")
    if not exe.exists():  # `uv sync` has not installed it yet
        return ""
    # not the server's stdin: on Windows, starting a child with it waits while the RPC thread reads it (rpc.py)
    out = subprocess.run([exe, command, *args], cwd=ledger, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return out.stdout + out.stderr


@dataclass
class Statement:
    name: str
    detail: str  # bank, IBAN, currency, period, holder; or why kingsmint cannot read it
    account: str | None = None  # where it goes: an account, "NEW", or None when kingsmint cannot read it


def statements(ledger: Path) -> list[Statement]:
    # shortcut: reads the text lines of `kingsmint scan`; add `--json` to it when its format needs to change
    found = []
    for line in kingsmint(ledger, "scan").splitlines():
        if "  " not in line:  # "nothing to scan in …"
            continue
        name, rest = line.split("  ", 1)
        detail, _, account = rest.partition("  -> ")
        found.append(Statement(name, detail.replace("  ", " · "), account or None))
    return found


@dataclass
class Coverage:
    account: str
    period: str | None  # first – last imported day; None: never imported
    missing: list[str] = field(default_factory=list)


def coverage(ledger: Path) -> list[Coverage]:
    rows = []
    for line in kingsmint(ledger, "coverage").splitlines():
        account, *rest = line.split("  ")
        if not rest:
            continue
        period = None if rest[0] == "never imported" else rest[0].replace(" .. ", " – ")
        rows.append(Coverage(account, period, [m.removeprefix("missing ").replace(" .. ", " – ") for m in rest[1:]]))
    return rows


def imported(ledger: Path) -> bool:
    """A statement was imported (documents/ holds one): false for a new ledger, whose inbox says how to start."""
    documents = ledger / "documents"
    return documents.exists() and any(f.is_file() and not f.name.startswith(".") for f in documents.rglob("*"))


def last_month(lang: str, today: datetime.date | None = None) -> str:
    """The last full calendar month, as "október 2026", for the month close."""
    day = (today or datetime.date.today()).replace(day=1) - datetime.timedelta(days=1)
    return format_date(day, "LLLL y", locale=lang)
