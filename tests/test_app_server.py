"""The desktop app's server (app/server/server.py): Fava under /fava with the app's files, and the RPC methods."""
import base64
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest
from decimal import Decimal

from beancount import loader
from beancount.core.data import Document
from werkzeug.test import Client

SERVER = Path(__file__).parent.parent / "app" / "server"
sys.path.insert(0, str(SERVER))  # as `python server/server.py` has it: server.py imports jj_versions
spec = importlib.util.spec_from_file_location("app_server", SERVER / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_server(tmp_path):
    (tmp_path / "main.beancount").write_text('option "title" "Test"\n2000-01-01 open Assets:Cash EUR\n')
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<p>app</p>")
    shutil.copy(SERVER.parent / "ui" / "i18n.json", tmp_path / "ui")
    c = Client(server.make_app(tmp_path / "main.beancount", tmp_path / "ui"))
    assert c.get("/index.html").text == "<p>app</p>"  # the files Fava's pages get from the app
    r = c.get("/fava/", follow_redirects=False)
    base = r.headers["location"]
    assert r.status_code == 302 and base.startswith("/fava/test/"), base
    page = c.get(base).text
    assert 'href="/fava/static/' in page  # Fava's links start with the mount
    assert '<link rel="stylesheet" href="/fava.css">' in page
    r = c.get("/ledger/account/Assets:Cash/?time=2025", follow_redirects=False)
    assert r.headers["location"] == "/fava/test/account/Assets:Cash/?time=2025"
    changed = lambda: c.get("/fava/test/api/changed").json["data"]  # noqa: E731
    changed()
    assert changed() is False
    c.application.state.checker.reload()
    assert changed() is True  # Fava's page loads the ledger again
    assert c.application.state.methods["history"]() == {"versions": None}  # no versions yet
    assert c.application.state.methods["settings"](lang="sk")["settings"]["title"] == "Test"
    inbox = c.application.state.methods["inbox"](lang="sk")  # no kingsmint in tmp_path: nothing waits, nothing imported
    assert inbox["statements"] == [] and inbox["coverage"] == [] and inbox["imported"] is False and inbox["month"]


def app(tmp_path, main='option "title" "Test"\n'):
    (tmp_path / "main.beancount").write_text(main + '2000-01-01 open Assets:Cash EUR\n')
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<p>app</p>")
    shutil.copy(SERVER.parent / "ui" / "i18n.json", tmp_path / "ui")
    return Client(server.make_app(tmp_path / "main.beancount", tmp_path / "ui"))


def test_dns_rebinding_refused(tmp_path):
    # a page of evil.example whose name points to 127.0.0.1 reaches the server under that name
    c = app(tmp_path)
    evil = {"host": "evil.example:8123", "origin": "http://evil.example:8123"}
    assert c.get("/index.html", headers=evil).status_code == 400
    assert c.get("/fava/", headers=evil).status_code == 400
    assert c.get("/index.html").status_code == 200


def test_html_document_sandboxed(tmp_path):
    # a ledger's HTML file runs on the app's origin, where scripts could call the app's commands
    doc = tmp_path / "documents" / "Assets" / "Cash"
    doc.mkdir(parents=True)
    (doc / "2025-01-01.statement.html").write_text("<html><head></head><script>top.__TAURI__</script></html>")
    (doc / "2025-01-02.statement.pdf").write_bytes(b"%PDF-1.4")
    c = app(tmp_path, 'option "title" "Test"\noption "documents" "documents"\n')
    get = lambda name: c.get("/fava/test/document/", query_string={"filename": str(doc / name)})  # noqa: E731
    r = get("2025-01-01.statement.html")
    assert r.status_code == 200 and r.headers["content-security-policy"] == "sandbox"
    assert "/fava.css" not in r.text  # not themed as Fava's page
    r = get("2025-01-02.statement.pdf")
    assert r.status_code == 200 and "content-security-policy" not in r.headers
    assert "content-security-policy" not in c.get("/fava/test/income_statement/").headers


def test_settings_saved_without_version(tmp_path, monkeypatch):
    # jj fails after the files are written: the answer says so, and the files are saved
    c = app(tmp_path, 'option "title" "Test"\ncustom "fava-option" "locale" "en_US"\ncustom "fava-option" "language" "en"\n')
    (tmp_path / ".jj").mkdir()

    def broken(*_):
        raise server.versions.VersionError("jj broke")
    monkeypatch.setattr(server.versions, "save", broken)
    methods = c.application.state.methods
    assert methods["save_settings"](title="New", locale="en_US", language="sk") == {"changed": None, "error": "jj broke"}
    assert methods["settings"]()["settings"]["title"] == "New"  # the files are written anyway


def test_page_ids_unique():
    # main.js finds elements by id; a second element with the same id is never found
    ids = re.findall(r'\bid="([^"]+)"', (Path(__file__).parent.parent / "app" / "ui" / "index.html").read_text())
    assert not [i for i in set(ids) if ids.count(i) > 1]


def test_fava_css_maps_fava_variables():
    # a Fava release that renames a variable would leave its color unmapped
    import fava
    fava_css = (Path(fava.__file__).parent / "static" / "app.css").read_text()
    ours = re.findall(r"^\s*(--[a-z-]+):", (Path(__file__).parent.parent / "app" / "ui" / "public" / "fava.css").read_text(), re.M)
    assert ours and not [v for v in ours if f"{v}:" not in fava_css]


def test_rpc_query_and_reports(tmp_path):
    c = app(tmp_path, 'option "title" "Test"\n2000-01-01 open Expenses:Food EUR\n'
                      '2025-01-05 * "Shop"\n  Assets:Cash  -12.50 EUR\n  Expenses:Food\n')
    methods = c.application.state.methods
    r = methods["query"](bql="SELECT account, sum(number) AS total WHERE account ~ 'Expenses' GROUP BY account")
    assert r == {"columns": ["account", "total"], "rows": [("Expenses:Food", Decimal("12.50"))]}
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "food.toml").write_text('name = "Food"\nquery = "SELECT 1"\nview = "bar"\n')
    (tmp_path / "reports" / "broken.toml").write_text('name = "no query"\n')
    assert methods["reports"]() == [{"file": "broken.toml", "error": "KeyError: 'query'"},
                                    {"file": "food.toml", "name": "Food", "query": "SELECT 1", "view": "bar"}]
    assert methods["state"]() == {"inbox": [], "check": "", "imported": False, "upgrade": False}  # no kingsmint here: no check


def test_rpc_answers_on_the_first_stdout_and_exits_with_stdin():
    import json
    import subprocess

    script = ("import rpc, time; out = rpc.claim_stdout(); print('noise'); "
              "rpc.serve({'add': lambda a, b: a + b}, out); time.sleep(30)")
    p = subprocess.Popen([sys.executable, "-c", script], cwd=SERVER, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    p.stdin.write('{"id": 1, "method": "add", "params": {"a": 2, "b": 3}}\n{"id": 2, "method": "nope"}\n')
    p.stdin.flush()
    answers = sorted((json.loads(p.stdout.readline()) for _ in range(2)), key=lambda m: m["id"])
    assert answers == [{"id": 1, "result": 5}, {"id": 2, "error": "KeyError: 'nope'"}]
    p.stdin.close()
    assert p.wait(timeout=10) == 0 and "noise" in p.stderr.read()  # prints go to stderr, not into the answers


def test_dashboard(ledger, tmp_path):
    """The overview (app/server/dashboard.py) on the sample, through the server's RPC methods."""
    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(SERVER.parent / "ui" / "i18n.json", ui)
    methods = server.make_app(ledger / "main.beancount", ui).state.methods

    d = methods["dashboard"]()
    assert d["period"] <= d["periods"][0]  # the last full month, not after the statements
    assert len(d["window"]) == 13 and d["window"][-1] == d["period"] == d["ends"][-1]
    flows = d["flows"]
    income, expenses = flows["Income"][-1], flows["Expenses"][-1]
    assert income > 0 and expenses > 0 and all(len(v) == 13 for v in flows.values())
    areas = [a for a in flows if a.count(":") == 1 and a.startswith("Expenses:")]
    assert abs(sum(flows[a][-1] for a in areas) - expenses) < 0.05  # the areas add up to the expenses
    food = [a for a in flows if a.startswith("Expenses:Food:")]
    assert food and abs(sum(flows[a][-1] for a in food) - flows["Expenses:Food"][-1]) < 0.05
    assert {kind for kind in (a["kind"] for a in d["accounts"])} == {"current", "savings"}
    assert all(len(a["history"]) == 13 for a in d["accounts"])
    r = d["runway"]
    assert r["liquid"] == pytest.approx(sum(a["history"][-1] for a in d["accounts"]))  # both bank accounts are liquid
    assert [a["account"] for a in r["liquid_by_account"]] == ["Assets:Me:Bank"]  # the query's rows, by root(account, 3)
    assert r["liquid_by_account"][0]["amount"] == pytest.approx(r["liquid"])
    assert set(r["baseline"]) == {"today", "reduced", "minimum"} and r["baseline"]["today"] > 0
    assert r["query"].startswith("SELECT")  # Baseline by account: what the baseline is made of

    month = {"start": d["period"], "end": d["period"]}
    t = methods["transactions"](**month)
    assert abs(sum(r["amount"] for r in t["rows"]) - (income - expenses)) < 0.05
    top = methods["transactions"](**month, account="Expenses:Food")
    assert abs(sum(r["amount"] for r in top["rows"]) + flows["Expenses:Food"][-1]) < 0.05
    assert any(m["recurring"] for m in methods["transactions"](**month, account="Expenses")["merchants"])
    assert all(len(r["hash"]) == 32 and r["document"] for r in top["rows"])  # Fava's hash; the sample names statements
    row = top["rows"][-1]
    e = methods["entry"](hash=row["hash"])
    assert e["payee"] == row["payee"] and e["amount"] == row["amount"] and e["statement"]  # the sample has its statements
    assert abs(sum(p["value"] for p in e["postings"])) < 0.01 and e["history"][0]["hash"] == row["hash"]
    assert "filename" not in e["meta"] and methods["entry"](hash="0" * 32) is None
    bank = next(a for a in d["accounts"] if a["kind"] == "current")
    rows = methods["transactions"](**month, account=bank["account"])["rows"]
    assert rows[-1]["balance"] == pytest.approx(bank["history"][-1])  # money in positive, the balance after each
    assert all(abs(b["balance"] - a["balance"] - b["amount"]) < 0.01 for a, b in zip(rows, rows[1:]))

    # a year that is not over: it and the years before count the same months, up to the last full one
    y = methods["dashboard"](unit="year")
    assert y["period"] == d["period"][:4] and y["periods"][0] == y["period"] and y["window"][-1] == y["period"]
    n = int(d["period"][5:])
    assert y["months"] == n and y["ends"][-1] == d["period"]
    year = y["window"][-2]
    assert y["ends"][-2] == f"{year}-{n:02}"
    rows = methods["transactions"](start=f"{year}-01", end=f"{year}-{n:02}")["rows"]
    flows = y["flows"]
    assert abs(sum(r["amount"] for r in rows) - (flows["Income"][-2] - flows["Expenses"][-2])) < 0.05
    full = methods["dashboard"](period=year, unit="year")
    assert full["months"] == 12 and full["ends"][-1] == f"{year}-12"
    assert all(v > 0 for v in flows["Expenses"])  # no year without data in its counted months


def test_runway_edit_and_save(ledger, tmp_path):
    """The runway's edit view: a preview of liquid, need and cut without writing, then the save into accounts.beancount
    and its undo, which gives the file back as it was."""
    shutil.copytree(ledger, tmp_path / "l")
    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(SERVER.parent / "ui" / "i18n.json", ui)
    methods = server.make_app(tmp_path / "l" / "main.beancount", ui).state.methods
    accounts = tmp_path / "l" / "accounts.beancount"
    before = accounts.read_text()

    now = methods["runway_edit"]()
    assets = {a["account"]: a for a in now["assets"]}
    savings = assets["Assets:Me:Bank:VUB:Savings"]
    assert savings["counted"] and savings["amount"] > 0
    assert now["meta"]["Expenses:Cash"] == {"need": "unknown", "cut": "0.5"}
    assert now["by_account"]["columns"][:2] == ["need", "account"]

    edits = {"Assets:Me:Bank:VUB:Savings": {"liquid": "false"}, "Expenses:Cash": {"need": "essential"}}
    preview = methods["runway_edit"](changes=edits)
    assert preview["liquid"] == pytest.approx(now["liquid"] - savings["amount"])
    assert not {a["account"]: a for a in preview["assets"]}["Assets:Me:Bank:VUB:Savings"]["counted"]
    assert preview["meta"]["Expenses:Cash"] == {"need": "essential"}  # an essential need drops the cut
    assert preview["baseline"]["minimum"] > now["baseline"]["minimum"]  # cash now counts as essential
    assert accounts.read_text() == before  # a preview writes nothing

    for bad in ({"Expenses:Cash": {"cut": 1.5}}, {"Expenses:Food:Groceries": {"need": "optional", "cut": 0.5}},
                {"Assets:Me:Bank:VUB:Savings": {"need": "essential"}}, {"Expenses:Nope": {"need": "essential"}}):
        with pytest.raises(ValueError):
            methods["runway_edit"](changes=bad)

    assert methods["runway_save"](changes=edits)["changed"]
    text = accounts.read_text()
    assert 'open Assets:Me:Bank:VUB:Savings EUR\n  iban: "SK5400000000009876543210"\n  liquid: "false"\n' in text
    assert 'open Expenses:Cash\n  need: "essential"\n2000' in text
    assert methods["dashboard"]()["runway"]["liquid"] == pytest.approx(preview["liquid"])  # the ledger loads again
    methods["runway_save"](changes={"Assets:Me:Bank:VUB:Savings": {"liquid": None},
                                    "Expenses:Cash": {"need": "unknown", "cut": 0.5}})
    assert accounts.read_text() == before  # the undo: the old values


def test_cash_save(ledger, tmp_path):
    """A cash payment from the app goes to cash.beancount with its receipt; the overview shows the cash withdrawn,
    entered and the rest."""
    root = tmp_path / "ledger"
    shutil.copytree(ledger, root)
    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(SERVER.parent / "ui" / "i18n.json", ui)
    methods = server.make_app(root / "main.beancount", ui).state.methods
    d = methods["dashboard"]()
    day = d["period"] + "-20"
    assert d["cash"] == {"withdrawn": 100.0, "entered": 0.0}  # the sample withdraws 100 each month

    receipt = {"name": "Bloček.JPG", "data": base64.b64encode(b"jpeg").decode()}
    assert methods["cash_save"](date=day, amount="12,5", account="Expenses:Food:Groceries", payee="Trh Ďurčo",
                                receipt=receipt) == {"saved": True, "error": "", "version": False}
    assert methods["cash_save"](date=day, amount="3", account="Expenses:Gifts", payee="Trh Ďurčo",
                                receipt=None) == {"saved": True, "error": "", "version": False}
    moved = root / "documents" / "Expenses" / "Cash" / f"{day}.trh-durco.jpg"
    assert moved.read_bytes() == b"jpeg"
    text = (root / "cash.beancount").read_text()
    assert text.endswith(f'\n{day} * "Trh Ďurčo"\n  document: "{moved.name}"\n  Expenses:Food:Groceries  12.50 EUR\n'
                         f'  Expenses:Cash  -12.50 EUR\n\n{day} * "Trh Ďurčo"\n  Expenses:Gifts  3.00 EUR\n'
                         '  Expenses:Cash  -3.00 EUR\n')
    d = methods["dashboard"]()
    assert d["cash"] == {"withdrawn": 100.0, "entered": 15.5} and d["flows"]["Expenses:Cash"][-1] == 84.5
    # in the transactions, a cash payment is one row of its category, which counts 0: spent when withdrawn
    rows = methods["transactions"](start=d["period"], end=d["period"])["rows"]
    mine = [r for r in rows if r["payee"] == "Trh Ďurčo"]
    assert [(r["account"], r["amount"], r["cash"]) for r in mine] == [
        ("Expenses:Food:Groceries", 0.0, -12.5), ("Expenses:Gifts", 0.0, -3.0)]
    flows = d["flows"]
    assert abs(sum(r["amount"] for r in rows) - (flows["Income"][-1] - flows["Expenses"][-1])) < 0.05
    cash = methods["transactions"](start=d["period"], end=d["period"], account="Expenses:Cash")["rows"]
    assert sorted(r["amount"] for r in cash) == [-100.0, 3.0, 12.5] and not any("cash" in r for r in cash)
    assert methods["entry"](hash=mine[0]["hash"])["amount"] == -12.5  # the detail: what the category got
    entries, errors, _ = loader.load_file(str(root / "main.beancount"))
    assert not [e for e in errors if "cash" in str(e.source.get("filename", "")) or "document" in e.message.lower()]
    assert any(isinstance(e, Document) and e.filename == str(moved) for e in entries)  # Fava finds the receipt

    before = (root / "cash.beancount").read_text()
    for bad in (dict(amount="0"), dict(amount="x"), dict(amount="-5"), dict(payee='Trh "X"'), dict(payee="a\nb"),
                dict(payee=" "), dict(account="Expenses:Cash"), dict(account="Assets:Me:Bank:Current"),
                dict(account="Expenses:Nope"), dict(date="2026-13-01"), dict(date="1999-01-01"),
                dict(receipt={"name": "virus.exe", "data": "eA=="}), dict(receipt={"name": "a.pdf", "data": "not base64!"}),
                dict(receipt={"name": "a.pdf", "data": ""})):
        args = dict(date=day, amount="5", account="Expenses:Gifts", payee="Trh") | bad
        assert methods["cash_save"](**args)["error"], bad
    assert (root / "cash.beancount").read_text() == before
