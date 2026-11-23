"""Settings of a ledger in the desktop app (app/server/ledger_settings.py): read and written in its files."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import ledger_settings as ls  # noqa: E402


def test_lines():
    main = ('option "title" "Ján Novák"\n; 2000-01-01 custom "fava-option" "locale" "xx"\n'
            '2000-01-01 custom "fava-option" "locale" "sk_SK"  ; numbers\n')
    assert ls.quoted(main, ls.TITLE) == "Ján Novák"
    assert ls.quoted(main, ls.LOCALE) == "sk_SK"  # a commented line does not count
    new = ls.set_quoted(main, ls.LOCALE, "cs_CZ")
    assert '"locale" "cs_CZ"  ; numbers\n' in new and '"locale" "xx"' in new
    assert ls.set_quoted(main, ls.LANGUAGE, "sk") is None
    accounts = ls.statement_accounts(
        '; 2000-01-01 open Assets:X EUR\n;   iban: "SK00"\n2000-01-01 open Assets:Me:Bank:A:Current EUR  ; salary\n'
        '  iban: "SK11"\n2000-01-01 open Expenses:Cash\n  need: "unknown"\n2000-01-01 open Assets:Me:Investments:B:Cash\n'
        '  ibkr: "U1"\n')
    assert [(a.account, a.currency, a.number, a.note) for a in accounts] == [
        ("Assets:Me:Bank:A:Current", "EUR", "SK11", "salary"), ("Assets:Me:Investments:B:Cash", "", "U1", "")]


@pytest.mark.skipif(not shutil.which("jj"), reason="needs jj")
def test_save(tmp_path):
    (tmp_path / "main.beancount").write_text(
        'option "title" "A"\noption "operating_currency" "EUR"\n2000-01-01 custom "fava-option" "locale" "sk_SK"\n'
        '2000-01-01 custom "fava-option" "language" "en"\n')
    (tmp_path / "CLAUDE.md").write_text("Talk to the owner in English, also when a skill is in English.\n")
    ls.versions.init(tmp_path, "New ledger")
    assert ls.read(tmp_path) == ls.Settings("A", "EUR", "sk_SK", "en")
    assert ls.save(tmp_path, "A", "sk_SK", "en") == []
    assert ls.save(tmp_path, " B ", "cs_CZ", "sk") == ["title B", "number format cs_CZ", "Fava language sk",
                                                         "agent language Slovak"]
    assert ls.read(tmp_path) == ls.Settings("B", "EUR", "cs_CZ", "sk")
    assert "Talk to the owner in Slovak, also" in (tmp_path / "CLAUDE.md").read_text()
    assert ls.versions.history(tmp_path)[0].message == "Settings: title B, number format cs_CZ, Fava language sk, agent language Slovak"
    with pytest.raises(ls.SettingsError):
        ls.save(tmp_path, 'B" x', "cs_CZ", "sk")
