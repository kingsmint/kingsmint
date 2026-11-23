"""The ledger's state in the desktop app (app/server/ledger_state.py): the check runs again only after a change."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import ledger_state  # noqa: E402


def test_state(tmp_path, monkeypatch):
    checks, reloads = [], []
    monkeypatch.setattr(ledger_state, "kingsmint", lambda ledger, command: checks.append(command) or "FAIL x\n")
    (tmp_path / "main.beancount").write_text("x")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "a.pdf").write_text("x")
    (tmp_path / "inbox" / ".DS_Store").write_text("x")
    c = ledger_state.Checker(tmp_path, lambda: reloads.append(1))
    assert c.state() == ledger_state.State(["a.pdf"], "FAIL x", False)
    c.state()
    assert checks == ["check"] and reloads == []  # nothing changed: no second check
    (tmp_path / "inbox" / "b.pdf").write_text("x")  # inbox/ is not the ledger's own file
    assert c.state().inbox == ["a.pdf", "b.pdf"] and checks == ["check"]
    os.utime(tmp_path / "main.beancount", (1e9, 2e9))
    c.state()
    assert checks == ["check", "check"] and reloads == [1]  # a change after the first check: Fava loads again
