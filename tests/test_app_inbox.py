"""The inbox view of the desktop app (app/server/inbox.py): it reads the text of `kingsmint scan` and `coverage`."""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import inbox  # noqa: E402


def test_inbox(tmp_path, monkeypatch):
    out = {
        "scan": "a.pdf  vub  SK00X  EUR  2026-10-01..2026-10-31  holder: Test  -> Assets:Me:Bank:A\n"
                "b.csv  unknown bank\nc.pdf  FAIL ValueError: x\nd.pdf  vub  SK11Y  EUR  2026-10-01..2026-10-31  -> NEW\n",
        "coverage": "Assets:A  2025-01-01 .. 2026-10-31  missing 2026-03-01 .. 2026-03-31\nAssets:B  never imported\n",
    }
    monkeypatch.setattr(inbox, "kingsmint", lambda ledger, command: out[command])
    got = inbox.statements(tmp_path)
    assert [(s.name, s.account) for s in got] == [("a.pdf", "Assets:Me:Bank:A"), ("b.csv", None), ("c.pdf", None), ("d.pdf", "NEW")]
    assert got[0].detail == "vub · SK00X · EUR · 2026-10-01..2026-10-31 · holder: Test"
    assert [(c.account, c.period, c.missing) for c in inbox.coverage(tmp_path)] == [
        ("Assets:A", "2025-01-01 – 2026-10-31", ["2026-03-01 – 2026-03-31"]), ("Assets:B", None, [])]
    assert not inbox.imported(tmp_path)
    (tmp_path / "documents" / "A").mkdir(parents=True)
    (tmp_path / "documents" / "A" / "2026.pdf").write_text("x")
    assert inbox.imported(tmp_path)
    assert inbox.last_month("sk", datetime.date(2026, 11, 20)) == "október 2026"
    assert inbox.last_month("en", datetime.date(2026, 1, 5)) == "December 2025"
