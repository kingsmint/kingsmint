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
    assert "FAIL setup: TITLE, CURRENCY, LOCALE not replaced" in capsys.readouterr().out
