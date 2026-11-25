"""The ledger's state, which the page polls: the statements waiting in inbox/, what `kingsmint check` says, whether a
statement was imported, and whether the ledger needs changes of a newer kingsmint. The check and `kingsmint upgrade`
run again only when a ledger file changed."""

import re
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import jj_versions
from inbox import imported, kingsmint

SKIP = {".venv", ".git", ".jj", "inbox", "documents", "node_modules"}
WRITING = Path(".kingsmint") / "writing"  # kingsmint.merge.WRITING: kingsmint writes ledger/ (import, reimport, reset)
STALE = 600  # seconds after which the mark is from a kingsmint that was killed


def writing(ledger: Path) -> bool:
    """Whether kingsmint writes the ledger's files now: a check would see them half written."""
    try:
        return time.time() - (ledger / WRITING).stat().st_mtime < STALE
    except OSError:
        return False


def newest(folder: Path) -> float:
    """The newest modification time of the ledger's own files (not .venv, .git, inbox/, documents/)."""
    t = 0.0
    for e in folder.iterdir():
        if e.name in SKIP:
            continue
        try:
            t = max(t, newest(e) if e.is_dir() else e.stat().st_mtime)
        except OSError:  # a file removed meanwhile
            pass
    return t


def upgrade(ledger: Path) -> None:
    """A ledger made with an older kingsmint gets the changes that kingsmint makes itself (`kingsmint upgrade --apply`),
    when the app opens it, before Fava loads it; they are saved as a version, which the owner can undo. What needs the
    agent stays: the state offers it (State.upgrade)."""
    if "kingsmint upgrade --done" not in kingsmint(ledger, "upgrade"):
        return
    out = kingsmint(ledger, "upgrade", "--apply")
    applied = re.findall(r"^applied the ledger changes of kingsmint (\S+)", out, re.M)
    if not applied or not jj_versions.enabled(ledger):
        return
    at = re.search(r"^ledger is at kingsmint (\S+)", out, re.M)
    body = "\n".join(f"- the changes of kingsmint {v} (src/kingsmint/CHANGELOG.md)" for v in applied)
    try:
        jj_versions.save(ledger, f"Upgrade the ledger to kingsmint {at[1] if at else applied[-1]}\n\n{body}\n\n"
                                 "Made by `kingsmint upgrade --apply` when the Kingsmint app opened the ledger.")
    except jj_versions.VersionError as e:  # the changes stay unsaved; the next version takes them
        print(f"cannot save the upgrade: {e}", file=sys.stderr)


@dataclass
class State:
    inbox: list[str]  # statements waiting in inbox/
    check: str  # output of `kingsmint check`: empty when the ledger is fine
    imported: bool  # a statement was imported (documents/ holds one): false for a new ledger
    upgrade: bool  # `kingsmint upgrade` lists changes for a ledger made with an older kingsmint


class Checker:
    """The last check of one ledger, and when its files were newest then. `reload` makes Fava load the ledger again."""

    def __init__(self, ledger: Path, reload: Callable[[], None]):
        self.ledger, self.reload = ledger, reload
        self.seen: tuple[float, str, bool] | None = None
        self.lock = threading.Lock()  # polls come in parallel; one check at a time

    def state(self) -> State:
        folder = self.ledger / "inbox"
        waiting = sorted(f.name for f in folder.iterdir() if not f.name.startswith(".")) if folder.exists() else []
        with self.lock:
            t = newest(self.ledger)
            # while kingsmint writes ledger/, the last check stands: the next poll checks the finished files
            if (not self.seen or self.seen[0] != t) and not writing(self.ledger):
                first = self.seen is None
                text = kingsmint(self.ledger, "check").strip()
                if text:  # the app shows it as Problems; the log keeps it, also after a next check clears it
                    print(f"kingsmint check:\n{text}", file=sys.stderr, flush=True)
                # Fava counts a write during its load as seen, so a load during `kingsmint reimport` keeps a ledger with
                # files missing. When the files have not changed for the whole check, Fava loads again, from complete files.
                if not first and newest(self.ledger) == t:
                    self.reload()
                # `upgrade --done` writes .kingsmint-version, a ledger file: this runs again after it
                upgrade = "kingsmint upgrade --done" in kingsmint(self.ledger, "upgrade")
                self.seen = (t, text, upgrade)
            # no check yet: kingsmint wrote the ledger since the app opened it
            return State(waiting, self.seen[1] if self.seen else "", imported(self.ledger), bool(self.seen and self.seen[2]))
