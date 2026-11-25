"""The ledger's state, which the page polls: the statements waiting in inbox/, what `kingsmint check` says, whether a
statement was imported, and whether the ledger needs changes of a newer kingsmint. The check and `kingsmint upgrade`
run again only when a ledger file changed."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from inbox import imported, kingsmint

SKIP = {".venv", ".git", ".jj", "inbox", "documents", "node_modules"}


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
            if not self.seen or self.seen[0] != t:
                first = self.seen is None
                text = kingsmint(self.ledger, "check").strip()
                # Fava counts a write during its load as seen, so a load during `kingsmint reimport` keeps a ledger with
                # files missing. When the files have not changed for the whole check, Fava loads again, from complete files.
                if not first and newest(self.ledger) == t:
                    self.reload()
                # `upgrade --done` writes .kingsmint-version, a ledger file: this runs again after it
                upgrade = "kingsmint upgrade --done" in kingsmint(self.ledger, "upgrade")
                self.seen = (t, text, upgrade)
            return State(waiting, self.seen[1], imported(self.ledger), self.seen[2])
