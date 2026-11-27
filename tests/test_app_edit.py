"""Changes of transactions from the app (app/server/edit.py): they stay after `kingsmint reimport`."""
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from beancount import loader

from kingsmint import cli, importer

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
sys.path.insert(0, str(Path(__file__).parent))  # test_app_server: the server module, loaded as the app runs it
import edit


@pytest.fixture
def root(ledger, tmp_path, monkeypatch):
    root = tmp_path / "ledger"
    shutil.copytree(ledger, root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(importer, "ROOT", root)
    monkeypatch.setattr(importer, "LEDGER", root / "main.beancount")
    return root


def load(root):
    return loader.load_file(str(root / "main.beancount"))[0]


def by_payee(entries, payee):
    return [e for e in entries if getattr(e, "payee", None) == payee and "id" in e.meta]


def postings(e):
    return [(p.account, p.units.number) for p in e.postings[1:]]


def test_split_payee_and_note_stay_after_reimport(root):
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    tid, total = e.meta["id"], -e.postings[0].units.number
    assert not edit.hand_edited(root, e)
    edit.save_entry(root, e, entries, [{"account": "Expenses:Gifts", "amount": "5"},
                                       {"account": "Expenses:Food:Restaurants"}], payee="Bistro", note="obed a darček")
    cli.reimport()
    e = next(x for x in load(root) if x.meta.get("id") == tid)
    assert postings(e) == [("Expenses:Gifts", Decimal("5.00")), ("Expenses:Food:Restaurants", total - 5)]
    assert (e.payee, e.meta["note"], e.meta["bank_payee"], e.flag) == ("Bistro", "obed a darček", "Bistro Centrum", "*")
    assert edit.hand_edited(root, e)


def test_bad_split_writes_nothing(root):
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    before = Path(e.meta["filename"]).read_text()
    for bad in ([{"account": "Expenses:Gifts", "amount": "500"}, {"account": "Expenses:Food:Restaurants"}],
                [{"account": "Expenses:Nope"}], [{"account": "Expenses:Gifts", "amount": "1"}], []):
        with pytest.raises(edit.EditError):
            edit.save_entry(root, e, entries, bad)
    with pytest.raises(edit.EditError):
        edit.save_entry(root, e, entries, [{"account": "Expenses:Gifts"}], note='a "quote"')
    assert Path(e.meta["filename"]).read_text() == before


def test_narration_shown_as_payee_stays_narration(root):
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    path = Path(e.meta["filename"])
    path.write_text(path.read_text().replace(f'{e.date} * "Bistro Centrum" "Platba kartou"', f'{e.date} * "Platba kartou"', 1))
    entries = load(root)
    e = next(x for x in entries if x.meta.get("id") == e.meta["id"])
    edit.save_entry(root, e, entries, [{"account": "Expenses:Uncategorized"}], payee="Platba kartou")
    e = next(x for x in load(root) if x.meta.get("id") == e.meta["id"])
    assert (e.payee, e.narration, e.flag) == (None, "Platba kartou", "!")


def test_rule_moves_the_counterparty_and_keeps_a_hand_edit(root):
    entries = load(root)
    netflix = by_payee(entries, "Netflix")
    edit.save_entry(root, netflix[0], entries, [{"account": "Expenses:Gifts"}])
    entries = load(root)
    e = by_payee(entries, "Netflix")[-1]
    preview = edit.rule_preview(root, e, entries, "Expenses:Sport")
    assert preview["regex"] == r"^Netflix \|" and len(preview["rows"]) == len(netflix)
    assert [r["id"] for r in preview["rows"] if r["edited"]] == [netflix[0].meta["id"]]
    assert preview["moves"] == len(netflix) - 2  # not the edited one, not the one that offers the rule
    edit.add_rule(root, e, "Expenses:Sport")
    rules = [x for x in (root / "rules.beancount").read_text().splitlines() if edit.RULE.match(x)]
    assert rules[0] == '2000-01-01 custom "rule" "^Netflix \\\\|" Expenses:Sport' and len(rules) > 1  # above the others
    cli.reimport()
    assert not (root / ".kingsmint" / "writing").exists()  # the mark goes with the reimport
    after = {x.meta["id"]: postings(x)[0][0] for x in by_payee(load(root), "Netflix")}
    assert after.pop(netflix[0].meta["id"]) == "Expenses:Gifts"
    assert set(after.values()) == {"Expenses:Sport"}


def test_server_methods(root, tmp_path):
    """Through the app's RPC: a save gives the transaction's new hash; a bad one an error, no exception."""
    from test_app_server import server

    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(Path(server.__file__).parent.parent / "ui" / "i18n.json", ui)
    methods = server.make_app(root / "main.beancount", ui).state.methods
    e = by_payee(load(root), "Spotify")[0]
    from fava.beans.funcs import hash_entry
    shown = methods["entry"](hash=hash_entry(e))
    assert shown["editable"] and "Expenses:Gifts" in shown["accounts"]
    r = methods["entry_save"](hash=hash_entry(e), postings=[{"account": "Expenses:Gifts"}], note="pre syna")
    assert r["error"] == "" and methods["entry"](hash=r["hash"])["meta"]["note"] == "pre syna"
    assert methods["entry_save"](hash=r["hash"], postings=[])["error"] == "At least one category"
    again = methods["entry_save"](id=e.meta["id"], note="druhá")  # by id: the hash of before the last change is gone
    assert again["error"] == "" and again["entry"]["meta"]["note"] == "druhá"
    assert methods["entry"](id=e.meta["id"])["meta"]["note"] == "druhá"  # the detail finds it after each change
    assert methods["entry_save"](hash=hash_entry(e), note="x")["error"] == "The ledger no longer has this transaction"
    assert methods["rule_preview"](id=e.meta["id"], account="Expenses:Sport")["moves"] > 0
    rules = (root / "rules.beancount").read_text()
    assert "not installed" in methods["rule_save"](id=e.meta["id"], account="Expenses:Sport")["error"]  # no .venv here
    assert (root / "rules.beancount").read_text() == rules  # a rule that reimport cannot apply is not written


def test_a_fee_alone_is_the_category(root):
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    path = Path(e.meta["filename"])
    path.write_text(path.read_text().replace("  Expenses:Food:Restaurants\n", "  Expenses:Bank:Fees\n", 1))
    entries = load(root)
    e = next(x for x in entries if x.meta.get("id") == e.meta["id"])
    assert edit.rest_of(e, edit.imported_fee(root, e)) == -e.postings[0].units.number
    edit.save_entry(root, e, entries, [{"account": "Expenses:Food:Restaurants"}])
    e = next(x for x in load(root) if x.meta.get("id") == e.meta["id"])
    assert [p.account for p in e.postings[1:]] == ["Expenses:Food:Restaurants"]


def test_a_split_with_the_fee_account_is_categories(root):
    """A split by hand that puts a part to Expenses:Bank:Fees: the import wrote no fee, so it is a category, not part
    of the statement row, and the whole amount is shared."""
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    total = -e.postings[0].units.number
    edit.save_entry(root, e, entries, [{"account": "Expenses:Gifts", "amount": "1"}, {"account": "Expenses:Bank:Fees"}])
    entries = load(root)
    e = next(x for x in entries if x.meta.get("id") == e.meta["id"])
    assert not edit.imported_fee(root, e) and edit.rest_of(e, False) == total
    edit.save_entry(root, e, entries, [{"account": "Expenses:Food:Restaurants"}])  # back to one category
    e = next(x for x in load(root) if x.meta.get("id") == e.meta["id"])
    assert [(p.account, p.units.number) for p in e.postings[1:]] == [("Expenses:Food:Restaurants", total)]


def test_a_save_waits_for_the_check(root, tmp_path):
    """`kingsmint check` never reads a file the app is writing: a change waits for the check's lock."""
    import threading

    from fava.beans.funcs import hash_entry
    from test_app_server import server

    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(Path(server.__file__).parent.parent / "ui" / "i18n.json", ui)
    app = server.make_app(root / "main.beancount", ui)
    e = by_payee(load(root), "Spotify")[0]
    done = []
    with app.state.checker.lock:  # a check runs
        t = threading.Thread(target=lambda: done.append(app.state.methods["entry_save"](hash=hash_entry(e), note="x")))
        t.start()
        t.join(0.3)
        assert not done and "note:" not in Path(e.meta["filename"]).read_text().split(e.meta["id"])[1][:200]
    t.join(10)
    assert done[0]["error"] == "" and done[0]["entry"]["meta"]["note"] == "x"
    assert not list(Path(e.meta["filename"]).parent.glob(".*.tmp"))  # written at once, no temporary file left


def test_only_statement_transactions_change(root):
    """A hand-written entry (cash.beancount) has its category first: the app leaves it to Fava."""
    (root / "cash.beancount").write_text((root / "cash.beancount").read_text() + """
2025-03-01 * "Trh" "zelenina"
  Expenses:Food:Groceries  5.00 EUR
  Expenses:Cash
""")
    entries = load(root)
    e = next(x for x in entries if getattr(x, "payee", None) == "Trh")
    assert edit.editable(e, entries)
    with pytest.raises(edit.EditError, match="Fava"):
        edit.save_entry(root, e, entries, [{"account": "Expenses:Gifts"}])


def test_a_closed_account_or_a_price_is_refused(root):
    entries = load(root)
    e = by_payee(entries, "Bistro Centrum")[0]
    path = Path(e.meta["filename"])
    with pytest.raises(edit.EditError, match="not open"):
        edit.save_entry(root, e, entries + [__import__("beancount.core.data", fromlist=["Close"]).Close(
            {}, e.date, "Expenses:Gifts")], [{"account": "Expenses:Gifts"}])
    path.write_text(path.read_text().replace("  Expenses:Food:Restaurants\n",
                                             f"  Expenses:Food:Restaurants  {-e.postings[0].units.number} EUR @ 1 EUR\n", 1))
    entries = load(root)
    e = next(x for x in entries if x.meta.get("id") == e.meta["id"])
    with pytest.raises(edit.EditError, match="price"):
        edit.save_entry(root, e, entries, [{"account": "Expenses:Gifts"}])


def test_slug():
    assert edit.tag_slug("Záloha plot") == "zaloha-plot"
    assert edit.tag_slug("#croatia-2026") == "croatia-2026"
    assert edit.tag_slug("a/b.c_d") == "a/b.c_d"
    assert edit.tag_slug("Croatia") == "Croatia"  # Beancount takes it: kept, so the app finds and removes it
    assert edit.retag({"tags_links": "#Croatia ^x"}, None, "Croatia") == {"tags_links": "^x"}
    with pytest.raises(edit.EditError):
        edit.tag_slug(" ?! ")


def test_tags_stay_after_reimport(root):
    """Tags on several transactions in ledger/ and one in cash.beancount; reimport keeps the ones in ledger/, links and
    other tags stay, and a removed tag goes."""
    (root / "cash.beancount").write_text((root / "cash.beancount").read_text() + """
2025-03-01 * "Trh" "zelenina" #market ^receipt-1
  Expenses:Food:Groceries  5.00 EUR
  Expenses:Cash
""")
    entries = load(root)
    bistro = by_payee(entries, "Bistro Centrum")
    spotify = by_payee(entries, "Spotify")[0]
    cash = next(x for x in entries if getattr(x, "payee", None) == "Trh")
    picked = [*bistro[:2], spotify, cash]
    changed = edit.save_tags(root, picked, add=edit.tag_slug("Záloha plot"))
    assert "cash.beancount" in changed
    assert '"Trh" "zelenina" #market #zaloha-plot ^receipt-1\n' in (root / "cash.beancount").read_text()
    edit.save_tags(root, [spotify], remove="zaloha-plot")
    with pytest.raises(edit.EditError, match="not in the transactions"):  # gone: a remove that writes nothing says so
        edit.save_tags(root, [spotify], remove="zaloha-plot")
    ids = {e.meta["id"] for e in bistro[:2]}
    cli.reimport()
    entries = load(root)
    tagged = [e for e in entries if "zaloha-plot" in (getattr(e, "tags", None) or ())]
    assert {e.meta.get("id") for e in tagged} == ids | {None}  # the cash one has no id
    assert next(e for e in tagged if e.payee == "Trh").links == {"receipt-1"}
    assert not next(e for e in entries if e.meta.get("id") == spotify.meta["id"]).tags
    assert not any(edit.hand_edited(root, e) for e in tagged if "id" in e.meta)  # a tag is not a change of categories


def test_tags_server(root, tmp_path):
    from test_app_server import server

    ui = tmp_path / "ui"
    ui.mkdir()
    shutil.copy(Path(server.__file__).parent.parent / "ui" / "i18n.json", ui)
    (root / "cash.beancount").write_text((root / "cash.beancount").read_text() + """
2025-06-10 * "Stavebniny" "pletivo" #plot
  Expenses:Housing:Rent   300.00 EUR
  Expenses:Cash
""")
    methods = server.make_app(root / "main.beancount", ui).state.methods
    bistro = by_payee(load(root), "Bistro Centrum")
    r = methods["tags_save"](items=[{"id": e.meta["id"]} for e in bistro], add="Výlet")
    assert (r["error"], r["tag"], r["count"]) == ("", "vylet", len(bistro))
    one = methods["tags_save"](id=bistro[0].meta["id"], remove="vylet")
    assert one["entry"]["tags"] == [] and one["entry"]["taggable"]
    t = {x["tag"]: x for x in methods["tags"]()["tags"]}
    assert t["vylet"]["count"] == len(bistro) - 1 and t["vylet"]["total"] > 0
    assert t["plot"]["total"] == 300  # a cash payment counts its category, not the cash it came from
    assert methods["tags_save"](id=bistro[0].meta["id"], add="")["error"].startswith("Not a tag")
