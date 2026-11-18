"""The desktop app's server (app/server/server.py): Fava under /fava with the app's files, and the RPC methods."""
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest
from decimal import Decimal

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
    assert methods["state"]() == {"inbox": [], "check": "", "imported": False}  # no kingsmint here: no check


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
