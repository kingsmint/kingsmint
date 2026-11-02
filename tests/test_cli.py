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
    assert "FAIL setup: TITLE, CURRENCY, LOCALE, LANGUAGE_CODE not replaced" in out
    assert "ok   ledger\n" in out  # the core accounts load without errors


def test_gaps():
    d = dt.date
    spans = [(d(2025, 1, 1), d(2025, 1, 31)), (d(2025, 2, 1), d(2025, 2, 28)), (d(2025, 4, 1), d(2025, 4, 30)),
             (d(2026, 1, 1), d(2026, 1, 1))]  # the last is an IBKR report: one date, no gap to it
    assert cli.gaps(spans) == [(d(2025, 3, 1), d(2025, 3, 31))]


def test_local_parser(tmp_path, monkeypatch, capsys):
    from kingsmint import banks
    (tmp_path / "banks").mkdir()
    (tmp_path / "banks" / "demo.py").write_text('"""Demo banka: PDF statements."""\nMARKER = "Demo banka"\n'
                                               'def parse_pdf(text):\n    return "parsed"\n', encoding="utf-8")
    monkeypatch.setattr(banks, "PARSERS", list(banks.PARSERS))
    monkeypatch.setattr(cli, "PARSERS", banks.PARSERS)
    banks.load_local(tmp_path / "banks")
    assert banks.PARSERS[0][0] == "Demo banka" and banks.PARSERS[0][1]("x") == "parsed"
    cli.banks()
    out = capsys.readouterr().out
    assert "local.demo  Demo banka: PDF statements." in out and "sk.vub  VÚB banka" in out and "intl.ibkr" in out


def test_upgrade(tmp_path, monkeypatch, capsys):
    log = tmp_path / "CHANGELOG.md"
    log.write_text("# Changelog\n\n## Unreleased\n\n### Ledger\n\n- not yet\n\n## 0.3.0\n\n- user note\n\n### Ledger\n\n"
                   "- add rule C\n\n## 0.2.0\n\n- no ledger change\n\n## 0.1.1\n\n### Ledger\n\n- add rule B\n\n"
                   "### Other\n\n- not ledger\n\n## 0.1.0\n\n### Ledger\n\n- old\n", encoding="utf-8")
    monkeypatch.setattr(cli, "CHANGELOG", log)
    monkeypatch.chdir(tmp_path)
    cli.upgrade([])  # no .kingsmint-version: a ledger from 0.1.0
    out = capsys.readouterr().out
    assert out.index("- add rule B") < out.index("- add rule C")  # oldest first
    assert "not yet" not in out and "not ledger" not in out and "- old" not in out and "0.2.0" not in out
    cli.upgrade(["--done"])
    assert (tmp_path / ".kingsmint-version").read_text() == "0.3.0\n"
    cli.upgrade([])
    assert "nothing to change" in capsys.readouterr().out.splitlines()[-1]
