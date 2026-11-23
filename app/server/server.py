"""The app's local server for one ledger: Fava at /fava, /ledger/<page>, and the files the app adds to Fava's pages
(theme, dark mode, bridge.js) from UI_DIR. The app's page comes from the app itself (tauri://localhost), another
origin: a script in Fava's frame cannot call the app's commands.

The app asks it for the ledger's data on stdin (rpc.py), with the methods in `app.state.methods`: `query` (BQL on
Fava's loaded ledger), `reports` (reports/*.toml), `state` (statements waiting, the check, a first import), `inbox`,
`settings` and `save_settings`, and the versions (`history`, `versions_init`, `versions_restore`, `versions_save`).

The app runs it in the ledger, with the ledger's Python, so Fava and its kingsmint extensions are the ledger's version:

    uv run --no-sync python server/server.py main.beancount PORT UI_DIR

It needs nothing but the ledger's own packages: Fava brings werkzeug, which serves it.

It exits when its stdin closes, so it does not outlive the app, also when the app is killed. With KINGSMINT_FIRST_VERSION
(a new ledger), it first turns on versions with that message.
"""

import dataclasses
import json
import logging
import os
import re
import sys
import tomllib
from types import SimpleNamespace
from pathlib import Path

import beanquery
import inbox
import jj_versions as versions
import ledger_settings
import ledger_state
import rpc
from babel.numbers import format_decimal
from fava.application import create_app
from werkzeug.exceptions import NotFound
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import make_server
from werkzeug.utils import redirect
from werkzeug.wrappers import Response


# The app's tokens on Fava's pages: Web Awesome's theme, the app's adjustments, Fava's colors from them, dark mode;
# and bridge.js, which tells the app's page what happens in Fava's frame
THEME = (b'<link rel="stylesheet" href="/vendor/@awesome.me/webawesome/dist-cdn/styles/themes/default.css">'
         b'<link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fava.css"><script src="/dark.js"></script>'
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

    def versions_save(message: str) -> None:
        """A point to return to, before a task for the agent; none without versions."""
        if versions.enabled(root):
            versions.save(root, message)

    app.state = SimpleNamespace(checker=checker)
    app.state.methods = {"query": query, "reports": reports, "inbox": inbox_data, "settings": settings_data,
                         "save_settings": save_settings, "history": history, "versions_init": versions_init,
                         "versions_restore": versions_restore, "versions_save": versions_save,
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
    app = make_app(ledger, ui)
    rpc.serve(app.state.methods, out)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # not a line per request
    make_server("127.0.0.1", port, app, threaded=True).serve_forever()
