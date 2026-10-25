import datetime as dt
import shutil
from pathlib import Path

import pytest

from kingsmint import cli


def test_doctor_fails_outside_a_ledger(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as e:
        cli.doctor()
    assert e.value.code == 1
    assert "FAIL ledger files: missing main.beancount" in capsys.readouterr().out


def test_doctor_finds_unfilled_template(tmp_path, monkeypatch, capsys):
    shutil.copytree(Path(__file__).parent.parent / "template", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        cli.doctor()
    out = capsys.readouterr().out
    assert "FAIL setup: TITLE, CURRENCY, LOCALE not replaced" in out
    assert "ok   ledger\n" in out  # the core accounts load without errors


def test_gaps():
    d = dt.date
    spans = [(d(2025, 1, 1), d(2025, 1, 31)), (d(2025, 2, 1), d(2025, 2, 28)), (d(2025, 4, 1), d(2025, 4, 30)),
             (d(2026, 1, 1), d(2026, 1, 1))]  # the last is an IBKR report: one date, no gap to it
    assert cli.gaps(spans) == [(d(2025, 3, 1), d(2025, 3, 31))]
