import json
import re

import pytest

from kingsmint import cli


def test_sample_reconciles(ledger, monkeypatch, capsys):
    monkeypatch.chdir(ledger)
    assert not list((ledger / "inbox").glob("*.csv"))  # all imported
    with pytest.raises(SystemExit) as e:
        cli.check()
    assert e.value.code == 0, capsys.readouterr().out
    capsys.readouterr()
    cli.runway()
    r = json.loads(capsys.readouterr().out)
    assert r["currency"] == "EUR" and r["liquid"] > 0 and r["baseline"] > 0 and r["months"] > 0


def test_trends(ledger):
    from fava.application import create_app

    app = create_app([str(ledger / "main.beancount")])
    page = app.test_client().get("/sample/extension/Trends/").get_data(as_text=True)
    assert "Trendy" in page and "Energy" in page
    assert '<small class="up2">+82 %</small>' in page  # the energy price jump of the sample's third year
    assert 'href="/sample/account/Expenses:Housing:Energy/?time=2025"' in page  # a cell opens the account in that year
    client = app.test_client()
    months = client.get("/sample/extension/Trends/?by=month").get_data(as_text=True)
    assert months.count("<th data-col=") == 13 and "?time=2026-" in months  # 13 months
    sport = months[months.index(">Sport<"):].split("</tr>")[0]
    assert "–" in sport and "nové" not in sport  # no gym a year before, but the months before it had one
    top = client.get("/sample/extension/Trends/?depth=1").get_data(as_text=True)
    assert ">Housing<" in top and ">Energy<" not in top
    energy = page[page.index('data-account="Expenses:Housing:Energy"'):].split("</tr>")[0]
    assert 'data-peak="82"' in energy  # in 2025: the slider keeps it up to 50 % when 2025 is the chosen column
    telecom = page[page.index('data-account="Expenses:Housing:Telecom"'):].split("</tr>")[0]
    assert set(re.findall(r'data-peak="(\d+)"', telecom)) == {"0"}  # the same price every year
    assert client.get("/sample/extension_js_module/Trends.js").status_code == 200
