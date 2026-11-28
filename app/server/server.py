"""The app's local server for one ledger: Fava at /fava, /ledger/<page>, and the files the app adds to Fava's pages
(theme, dark mode, bridge.js) from UI_DIR. The app's page comes from the app itself (tauri://localhost), another
origin: a script in Fava's frame cannot call the app's commands.

The app asks it for the ledger's data on stdin (rpc.py), with the methods in `app.state.methods`: `query` (BQL on
Fava's loaded ledger), `dashboard`, `transactions`, `entry` and `recurring` (the overview), the changes of transactions (`entry_save`, `rule_preview`,
`rule_save`, `entry_reset`, `cash_save`, `recurring_set`), the tags (`tags`, `tags_save`), the budgets (`budgets`, `budget_save`,
`budget_tag_save`), `reports` (reports/*.toml), `state` (statements
waiting, the check, a first import), `inbox`, `settings` and `save_settings`, and the versions (`history`, `versions_init`, `versions_restore`, `versions_save`).

The app runs it in the ledger, with the ledger's Python, so Fava and its kingsmint extensions are the ledger's version:

    uv run --no-sync python server/server.py main.beancount PORT UI_DIR

It needs nothing but the ledger's own packages: Fava brings werkzeug, which serves it.

It exits when its stdin closes, so it does not outlive the app, also when the app is killed. With KINGSMINT_FIRST_VERSION
(a new ledger), it first turns on versions with that message.
"""

import dataclasses
import functools
import json
import logging
import os
import re
import sys
import tomllib
from collections import Counter
from types import SimpleNamespace
from pathlib import Path

import beanquery
import budgets
import dashboard
import inbox
import jj_versions as versions
import ledger_settings
import ledger_state
import rpc
from babel.numbers import format_decimal
from beancount.core.data import Open, Transaction
from fava.application import create_app
from fava.beans.funcs import hash_entry
from fava.helpers import FavaAPIError
from werkzeug.exceptions import NotFound
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import make_server
from werkzeug.utils import redirect
from werkzeug.wrappers import Response

try:
    import edit
except ImportError:  # a ledger on a kingsmint without the merge of hand edits: no changes from the app
    edit = None


# The app's tokens on Fava's pages: Web Awesome's theme, the app's adjustments and themes (the app's setting), Fava's colors from them, dark mode;
# and bridge.js, which tells the app's page what happens in Fava's frame
THEME = (b'<link rel="stylesheet" href="/vendor/@awesome.me/webawesome/dist-cdn/styles/themes/default.css">'
         b'<link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/themes.css">'
         b'<link rel="stylesheet" href="/fava.css"><script src="/dark.js"></script>'
         b'<script src="/bridge.js"></script>')


# A ledger's own files that a browser would run (HTML, SVG, XML), served by Fava's document and statement pages
ACTIVE = {"text/html", "application/xhtml+xml", "image/svg+xml", "text/xml", "application/xml"}


def themed(wsgi_app):
    """Fava's WSGI app with THEME at the end of each HTML page's head. A ledger's document runs in a sandbox: on the
    app's origin, its scripts could call the app's commands, terminals included."""
    def app(environ, start_response):
        response = Response.from_app(wsgi_app, environ)
        if re.match(r"/[^/]+/(document|statement)/", environ.get("PATH_INFO", "")):
            if response.mimetype in ACTIVE:
                response.headers["Content-Security-Policy"] = "sandbox"
        elif response.mimetype == "text/html":
            response.set_data(response.get_data().replace(b"</head>", THEME + b"</head>", 1))
        return response(environ, start_response)
    return app


def make_app(ledger: Path, ui: Path):
    """The server's WSGI app; `app.state` holds the RPC methods and the ledger's Checker."""
    fava = create_app([ledger], load=True)
    fava.wsgi_app = themed(fava.wsgi_app)
    root = ledger.parent
    strings = json.loads((ui / "i18n.json").read_text())["app"]

    # the number formats the settings offer, as Fava's locale option names them
    locales = ["sk_SK", "cs_CZ", "de_DE", "de_AT", "hu_HU", "pl_PL", "en_GB", "en_US"]

    def reload_fava():
        """Fava loads the ledger again. A load that ran during `kingsmint reimport` counts the files written meanwhile
        as seen, so Fava would keep a ledger with files missing; the state reloads when the files stopped changing."""
        # a path that does not exist moves the watcher's time on; Fava's page reloads at its next /api/changed
        fava.config["LEDGERS"].ledgers[0].watcher.notify(ledger.with_name(".kingsmint-reload"))

    checker = ledger_state.Checker(root, reload_fava)
    # Fava under /fava (DispatcherMiddleware sets SCRIPT_NAME, so Fava's links start with /fava); the rest from UI_DIR
    files = DispatcherMiddleware(SharedDataMiddleware(NotFound(), {"/": str(ui)}), {"/fava": fava})

    def app(environ, start_response):
        # DNS rebinding: a web page whose name points to 127.0.0.1 reaches this server under that name
        if environ.get("HTTP_HOST", "").rsplit(":", 1)[0] not in ("127.0.0.1", "localhost"):
            return Response("Invalid host", 400)(environ, start_response)
        path = environ.get("PATH_INFO", "")
        if path.startswith("/ledger/"):
            # Fava's page of this ledger, without its slug, which comes from the ledger's title: the agent's links
            # start with KINGSMINT_FAVA_URL (the app sets it to this) and still work after the title changes
            query = f"?{environ['QUERY_STRING']}" if environ.get("QUERY_STRING") else ""
            to = f"/fava/{fava.config['LEDGERS'].first_slug()}/{path.removeprefix('/ledger/')}{query}"
            return redirect(to, 302)(environ, start_response)
        return files(environ, start_response)

    def query(bql: str) -> dict:
        """BQL on the ledger Fava has loaded, so the ledger is loaded once; columns and rows."""
        l = fava.config["LEDGERS"].ledgers[0]
        l.changed()  # loads the ledger again after a change, as Fava does before it answers a page
        cursor = beanquery.connect("beancount:", entries=l.all_entries, errors=l.errors, options=l.options).execute(bql)
        return {"columns": [c.name for c in cursor.description], "rows": cursor.fetchall()}

    def loaded():
        """Fava's ledger, loaded again after a change; and the price of a unit in the operating currency."""
        l = fava.config["LEDGERS"].ledgers[0]
        l.changed()
        currency = (l.options["operating_currency"] or ["EUR"])[0]
        return l, lambda c, day: l.prices.get_price((c, currency), day)

    def overview(period: str | None = None, unit: str = "month") -> dict:
        l, rate = loaded()
        try:
            b = budget_data()
        except Exception as e:  # a budgets bug, or an entry it cannot count with, leaves the rest of the overview
            logging.exception("budgets")
            b = {"accounts": [], "tags": [], "errors": [f"Budgets: {e}"]}
        return dashboard.overview(l.all_entries, l.errors, l.options, rate, period, unit) | {"budgets": b}

    def transactions(start: str, end: str, account: str | None = None) -> dict:
        l, rate = loaded()
        return dashboard.transactions(l.all_entries, l.options, rate, start, end, account) | {
            "editable": edit is not None, "accounts": open_accounts(l.all_entries)}

    def open_accounts(entries):
        return sorted(o.account for o in entries if isinstance(o, Open) and not o.account.startswith("Equity:"))

    def entry(hash: str | None = None, id: str | None = None) -> dict | None:
        """A transaction (the overview's transaction view) by its `id`, which a change keeps, else by Fava's hash, which
        each change makes new; None when the ledger no longer has it."""
        l, rate = loaded()
        try:
            e = (next((x for x in l.all_entries if isinstance(x, Transaction) and x.meta.get("id") == id), None) if id
                 else l.get_entry(hash))
        except FavaAPIError:
            return None
        if not isinstance(e, Transaction):
            return None
        try:
            statement = bool(l.statement_path(hash_entry(e), "document"))
        except FavaAPIError:
            statement = False
        name = e.payee or e.narration
        used = Counter(p.account for t in l.all_entries if isinstance(t, Transaction) and (t.payee or t.narration) == name
                       for p in t.postings[1:] if p.account.split(":")[0] in ("Expenses", "Income"))
        return dashboard.entry(e, l.all_entries, l.options, rate, statement) | {
            "editable": edit is not None and not edit.editable(e, l.all_entries),
            "edited": edit is not None and edit.hand_edited(root, e),
            "fee": edit is not None and edit.imported_fee(root, e),  # the import's bank fee: part of the statement row
            "suggested": [a for a, _ in used.most_common(5)],  # the payee's categories, the most used first
            "taggable": edit is not None and edit.in_ledger(root, e),  # tags also on transactions written by hand
            "accounts": open_accounts(l.all_entries)}

    def tags() -> dict:
        """Each tag with what its transactions spent (dashboard.tags)."""
        l, rate = loaded()
        return dashboard.tags(l.all_entries, l.options, rate)

    def tags_save(hash: str | None = None, id: str | None = None, items: list[dict] | None = None,
                  add: str | None = None, remove: str | None = None) -> dict:
        """Adds the tag `add` (turned into a tag Beancount takes: edit.tag_slug) to the transactions `items` ([{id} or
        {hash}]), or to the one `id` or `hash`, or removes `remove`, as written (#Croatia). `tag`: the tag as written; for one transaction,
        `hash` and `entry`: the transaction now."""
        try:
            can_edit()
            add = None if add is None else edit.tag_slug(add)
            remove = None if remove is None else remove.strip().lstrip("#")
            txns = [changed_entry(r.get("hash"), r.get("id"))[1] for r in items or [{"hash": hash, "id": id}]]
            l, _ = loaded()
            paths = edit.save_tags(root, txns, add, remove)
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = ""
        try:
            if paths and versions.enabled(root):
                what = f"+#{add}" if add else f"-#{remove}"
                versions.save(root, f"Tags: {what} on {len(txns)} transaction{'s' if len(txns) > 1 else ''}")
        except versions.VersionError as err:
            error = str(err)
        l.load_file()
        result = {"error": error, "tag": add or remove, "count": len(txns)}
        if items is None:
            e = txns[0]
            return result | changed(edit.hash_at(l.all_entries, e.meta["filename"], e.meta["lineno"]))
        return result | {"hash": None}  # no transaction to show; the page loads the rows again

    def recurring() -> dict:
        l, rate = loaded()
        return dashboard.recurring(l.all_entries, l.options, rate) | {"editable": edit is not None}

    def recurring_set(changes: list) -> dict:
        """What the recurring payments do with payees ([[payee, state, period]], edit.set_recurring); one version."""
        try:
            can_edit()
            what = edit.set_recurring(root, changes)
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = save_version("Recurring: " + what)
        loaded()[0].load_file()
        return {"error": error}

    def can_edit(reimport=False):
        if edit is None:
            raise ValueError("This ledger's kingsmint is too old to keep changes: update it (the import skill, step 0)")
        if reimport and not inbox.installed(root):  # checked before a rule is written, which reimport would apply
            raise ValueError("kingsmint is not installed in this ledger yet")

    def changed_entry(hash: str | None, id: str | None):
        """The transaction to change, from the files as they are now (their line numbers): by its `id`, which a change
        keeps, else by Fava's hash, which each change makes new (a transaction kingsmint did not write has no id)."""
        can_edit()
        l, _ = loaded()
        try:
            e = (next((x for x in l.all_entries if isinstance(x, Transaction) and x.meta.get("id") == id), None) if id
                 else l.get_entry(hash))
        except FavaAPIError:
            e = None
        if not isinstance(e, Transaction):
            raise ValueError("The ledger no longer has this transaction")
        return l, e

    def save_version(message: str) -> str:
        """A version of the change; its error, which leaves the files written."""
        try:
            if versions.enabled(root):
                versions.save(root, message)
        except versions.VersionError as e:
            return str(e)
        return ""

    def reimport() -> list[str]:
        """`kingsmint reimport`: the lines that need the user (warnings, failures). Not a conflict: it reports a hand
        edit that a rule would change and that stays, as the rule's preview showed."""
        status, out = inbox.run(root, "reimport")
        if status:  # it stopped: all it said
            return [line for line in out.splitlines() if line.strip()] or [f"kingsmint reimport failed ({status})"]
        return [line for line in out.splitlines() if line.startswith(("WARN", "FAIL")) and ": conflict " not in line]

    def entry_save(hash: str | None = None, id: str | None = None, postings: list[dict] | None = None, payee: str | None = None,
                   note: str | None = None) -> dict:
        """Writes one transaction's categories ([{account, amount}], the last without an amount; none keeps them),
        payee and note in its file, where a reimport keeps them; `hash` and `entry`: the transaction now."""
        try:
            l, e = changed_entry(hash, id)
            name, parts = edit.save_entry(root, e, l.all_entries, postings, payee, note)
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = ""
        try:  # changes to one transaction in a row are one version
            if versions.enabled(root):
                path = Path(e.meta["filename"]).resolve().relative_to(root.resolve()).as_posix()
                versions.save_change(root, f"Transaction: {name}", parts, [path])
        except versions.VersionError as err:
            error = str(err)
        l.load_file()
        return changed(edit.hash_at(l.all_entries, e.meta["filename"], e.meta["lineno"]), error=error)

    def cash_save(date: str, amount: str, account: str, payee: str, receipt: dict | None = None) -> dict:
        """Adds a cash payment to cash.beancount (edit.add_cash), with its receipt; a version of it."""
        try:
            can_edit()
            l, _ = loaded()
            message = edit.add_cash(root, l.all_entries, (l.options["operating_currency"] or ["EUR"])[0], date,
                                    amount, account, payee, receipt)
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = save_version(message)
        l.load_file()
        return {"saved": True, "error": error, "version": not error and versions.enabled(root)}

    def changed(hash: str | None, **result) -> dict:
        """What a change gives the page: the transaction's new hash and the transaction itself, so the page shows it
        without asking again."""
        return result | {"hash": hash, "entry": hash and entry(hash)}

    def rule_preview(account: str, hash: str | None = None, id: str | None = None) -> dict:
        """What a rule for the counterparty of a transaction would change (edit.rule_preview); nothing is written."""
        try:
            l, e = changed_entry(hash, id)
            return edit.rule_preview(root, e, l.all_entries, account)
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}

    def rule_save(account: str, hash: str | None = None, id: str | None = None) -> dict:
        """Adds the rule for the counterparty of a transaction and runs `kingsmint reimport`; `messages`: its
        conflicts and warnings; `hash`: the transaction's new hash."""
        try:
            can_edit(reimport=True)
            l, e = changed_entry(hash, id)
            what = edit.add_rule(root, e, account)
            messages = reimport()
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = save_version("Rule: " + what)
        l.load_file()
        return changed(edit.hash_of(l.all_entries, e.meta.get("id")), messages=messages, error=error)

    def entry_reset(hash: str | None = None, id: str | None = None) -> dict:
        """The transaction takes the categories and flag the rules give (`kingsmint reset`, then reimport); `hash`:
        its new hash."""
        try:
            can_edit(reimport=True)
            l, e = changed_entry(hash, id)
            if "id" not in e.meta:
                raise ValueError("kingsmint did not write this transaction: no rules apply to it")
            messages = [line for line in inbox.kingsmint(root, "reset", e.meta["id"]).splitlines()
                        if line.startswith("FAIL")] + reimport()
        except ValueError as err:  # edit.EditError too
            return {"error": str(err)}
        error = save_version(f"Back to the rules: {e.date} {e.payee or e.narration}")
        l.load_file()
        return changed(edit.hash_of(l.all_entries, e.meta["id"]), messages=messages, error=error)

    def budget_data(offset: int = 0) -> dict:
        """The budgets (budgets.py), the account budgets `offset` periods back; `expense_accounts`: those to budget,
        `file`: whether the ledger loads budgets.beancount, so what the app writes there counts."""
        l, rate = loaded()
        return budgets.overview(l.all_entries, l.options, rate, offset) | {
            "expense_accounts": budgets.expense_accounts(l.all_entries),
            "file": str((root / budgets.FILE).resolve()) in {str(Path(f).resolve()) for f in l.options["include"]}}

    def budget_save(account: str, period: str, limit, since: str | None = None) -> dict:
        """An account's budget from `since` (budgets.set_account), saved as a version; `error` when it is not written,
        `version_error` when the version fails after the file was written."""
        l, _ = loaded()
        try:
            currency = (l.options["operating_currency"] or ["EUR"])[0]
            what = budgets.set_account(root, l.all_entries, currency, account, period, limit, since)
        except budgets.BudgetError as e:
            return {"error": str(e)}
        error = save_version("Budget: " + what)
        l.load_file()
        return {"changed": what, "version_error": error}

    def budget_tag_save(tag: str, limit, start: str, end: str | None = None, name: str | None = None,
                        old: str | None = None) -> dict:
        """A tag's budget (budgets.set_tag), saved as a version; `tag`: as written."""
        l, _ = loaded()
        try:
            currency = (l.options["operating_currency"] or ["EUR"])[0]
            tag, what = budgets.set_tag(root, currency, tag, limit, start, end, name, old)
        except budgets.BudgetError as e:
            return {"error": str(e)}
        error = save_version("Budget: " + what)
        l.load_file()
        return {"tag": tag, "changed": what, "version_error": error}

    def reports() -> list[dict]:
        """The reports in reports/*.toml: name, query (BQL), view (table, bar, line). A broken file comes with its
        error, so it does not hide the others."""
        found = []
        for f in sorted((root / "reports").glob("*.toml")):
            try:
                d = tomllib.loads(f.read_text(encoding="utf-8"))
                found.append({"file": f.name, "name": d["name"], "query": d["query"], "view": d.get("view", "table")})
            except (OSError, ValueError, KeyError) as e:
                found.append({"file": f.name, "error": f"{type(e).__name__}: {e}"})
        return found

    def inbox_data(lang: str = "en") -> dict:
        """The statements in inbox/ (what `kingsmint scan` says), the imported periods, whether a statement was
        imported, and the last full month in `lang`, for the month close."""
        return {"statements": [dataclasses.asdict(s) for s in inbox.statements(root)],
                "coverage": [dataclasses.asdict(c) for c in inbox.coverage(root)],
                "imported": inbox.imported(root), "month": inbox.last_month(lang if lang in strings else "en")}

    def settings_data(lang: str = "en") -> dict:
        """The ledger's settings, the number formats to offer (with an example in each), and the accounts of its
        statements."""
        s = ledger_settings.read(root)
        names = strings.get(lang, strings["en"]).get("locales") or strings["en"]["locales"]
        offered = [[code, f"{names.get(code, code)} ({format_decimal(1098707.95, '#,##0.00', locale=code)})"]
                   for code in locales]
        if s.locale not in locales:  # keep a value we do not list
            offered.insert(0, [s.locale, s.locale])
        return {"settings": dataclasses.asdict(s), "locales": offered,
                "accounts": [dataclasses.asdict(a) for a in ledger_settings.accounts(root)]}

    def save_settings(title: str, locale: str, language: str) -> dict:
        """Writes the settings (SettingsError for a bad value): what changed; the files are written also when the
        version fails, which comes as `error`."""
        try:
            return {"changed": ledger_settings.save(root, title, locale, language), "error": ""}
        except versions.VersionError as e:
            return {"changed": None, "error": str(e)}

    def runway_edit(changes: dict | None = None) -> dict | None:
        """The runway with edits of the accounts' liquid, need and cut that are not saved yet: a preview."""
        l, _ = loaded()
        currency = (l.options["operating_currency"] or ["EUR"])[0]
        r = dashboard.runway_edit(l.all_entries, l.errors, l.options, currency, changes or {})
        return r and dataclasses.asdict(r)

    def runway_save(changes: dict) -> dict:
        """Writes the edits into the `open` entries (ValueError, SettingsError for a bad one): what changed; the files
        are written also when the version fails, which comes as `error`."""
        l, _ = loaded()  # the files as they are now: their line numbers
        try:
            changed = ledger_settings.save_meta(root, l.all_entries, dashboard.checked(l.all_entries, changes))
            error = ""
        except versions.VersionError as e:
            changed, error = None, str(e)
        l.load_file()  # now, not when Fava's watcher sees the file: the page loads the runway right after the save
        return {"changed": changed, "error": error}

    def history() -> dict:
        """The versions, newest first, and whether files changed since the last; `versions` is None before the
        versions are on. An error of jj comes as `error`, as in the other version methods."""
        if not versions.enabled(root):
            return {"versions": None}
        try:
            return {"versions": [dataclasses.asdict(v) for v in versions.history(root)], "dirty": versions.dirty(root)}
        except versions.VersionError as e:
            return {"versions": [], "dirty": False, "error": str(e)}

    def versions_init() -> dict:
        try:
            versions.init(root, "Start versions")
        except versions.VersionError as e:
            return {"error": str(e)}
        return {}

    def versions_restore(id: str | None = None) -> dict:
        """Back to version `id`, or without it, undo the last change: the version, and the statements moved back to
        inbox/."""
        try:
            return dataclasses.asdict(versions.restore(root, id))
        except versions.VersionError as e:
            return {"error": str(e)}
        finally:
            loaded()[0].load_file()  # now: Fava's watcher sees the files later, and a change meanwhile reads old lines

    def versions_save(message: str) -> None:
        """A point to return to, before a task for the agent; none without versions."""
        if versions.enabled(root):
            versions.save(root, message)

    app.state = SimpleNamespace(checker=checker)
    def exclusive(method):
        """A change of the ledger's files, under the check's lock: `kingsmint check` never reads the files while a
        method writes them (a reimport rewrites all of ledger/), so it never reports a ledger half written."""
        @functools.wraps(method)
        def run(*args, **kwargs):
            with checker.lock:
                return method(*args, **kwargs)
        return run

    app.state.methods = {"query": query, "dashboard": overview, "transactions": transactions, "entry": entry,
                         "entry_save": exclusive(entry_save), "rule_preview": rule_preview,
                         "rule_save": exclusive(rule_save), "entry_reset": exclusive(entry_reset), "cash_save": exclusive(cash_save),
                         "recurring": recurring, "recurring_set": exclusive(recurring_set),
                         "reports": reports, "tags": tags, "tags_save": exclusive(tags_save),
                         "budgets": budget_data, "budget_save": exclusive(budget_save),
                         "budget_tag_save": exclusive(budget_tag_save),
                         "inbox": inbox_data, "settings": settings_data,
                         "save_settings": exclusive(save_settings), "runway_edit": runway_edit,
                         "runway_save": exclusive(runway_save), "history": history, "versions_init": versions_init,
                         "versions_restore": exclusive(versions_restore), "versions_save": versions_save,
                         "state": lambda: dataclasses.asdict(checker.state())}
    return app


if __name__ == "__main__":
    out = rpc.claim_stdout()
    ledger, port, ui = Path(sys.argv[1]).resolve(), int(sys.argv[2]), Path(sys.argv[3])
    if first := os.environ.get("KINGSMINT_FIRST_VERSION"):
        try:
            versions.init(ledger.parent, first)
        except versions.VersionError as e:  # the ledger works without versions; History offers to turn them on
            print(f"cannot start the versions: {e}", file=sys.stderr)
    ledger_state.upgrade(ledger.parent)
    app = make_app(ledger, ui)
    rpc.serve(app.state.methods, out)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # not a line per request
    make_server("127.0.0.1", port, app, threaded=True).serve_forever()
