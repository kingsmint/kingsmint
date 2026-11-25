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
    assert c.state() == ledger_state.State(["a.pdf"], "FAIL x", False, False)
    c.state()
    assert checks == ["check", "upgrade"] and reloads == []  # nothing changed: no second check
    (tmp_path / "inbox" / "b.pdf").write_text("x")  # inbox/ is not the ledger's own file
    assert c.state().inbox == ["a.pdf", "b.pdf"] and checks == ["check", "upgrade"]
    os.utime(tmp_path / "main.beancount", (1e9, 2e9))
    c.state()
    assert checks == ["check", "upgrade", "check", "upgrade"] and reloads == [1]  # a change after the first check: Fava loads again


def test_upgrade(tmp_path, monkeypatch):
    """`kingsmint upgrade` lists changes for the ledger: the page offers them to the agent."""
    out = {"check": "", "upgrade": "## 0.2.0\n\n- a change\n\nApply these ..., then run `kingsmint upgrade --done`.\n"}
    monkeypatch.setattr(ledger_state, "kingsmint", lambda ledger, command: out[command])
    (tmp_path / "main.beancount").write_text("x")
    c = ledger_state.Checker(tmp_path, lambda: None)
    assert c.state().upgrade
    out["upgrade"] = "nothing to change: the ledger is at kingsmint 0.2.4, installed 0.2.4\n"
    os.utime(tmp_path / "main.beancount", (1e9, 2e9))
    assert not c.state().upgrade
