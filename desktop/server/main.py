"""Kingsmint MCP server (prototype): runs the kingsmint commands on this computer, in the ledger folder."""

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import versions

HERE = Path(__file__).parent  # in the bundle, holds the kingsmint package (desktop/build.py copies it)
TEMPLATE = HERE.parent / "template"
PORT = 5057

mcp = MCPServer("kingsmint", instructions="""Kingsmint keeps a Beancount ledger in a folder on the user's computer.
Use these tools for every kingsmint command; they run on the user's computer, not in your sandbox.
- `ledger/` is generated: change categories by editing rules.beancount and accounts.beancount in the
  ledger folder, then call kingsmint_rules (preview), kingsmint_reimport, and kingsmint_check.
- A rule: `2000-01-01 custom "rule" "REGEX" Account`; the regex matches `payee | narration | iban | amount`
  (and `VS<variable symbol>`); the first matching rule in file order wins.
- New statements go to inbox/; then kingsmint_import. Ask the user only what the statements cannot show.
- kingsmint_check must print nothing new after each change. Then save a version with kingsmint_save.
- The user can go back: kingsmint_history lists the versions, kingsmint_restore undoes the last change.""")
fava = None


REMEMBERED = Path.home() / ".kingsmint" / "ledger_dir"  # the last ledger folder a tool got: Cowork cannot set user_config


def ledger(ledger_dir: str = "") -> Path:
    d = ledger_dir or os.environ.get("LEDGER_DIR", "") or (REMEMBERED.read_text(encoding="utf-8").strip() if REMEMBERED.exists() else "")
    if not d:
        raise ValueError("No ledger folder yet: pass ledger_dir, the folder's path on the user's computer (not a /sessions/... "
                         "sandbox path; ask the user for it if you do not know it). It is remembered for later calls.")
    if not Path(d).is_dir():
        raise ValueError(f"Not a folder on the user's computer: {d}. Pass the path as the user's computer sees it, "
                         "for example /Users/<name>/Documents/Ledger; ask the user if unsure.")
    if ledger_dir:
        REMEMBERED.parent.mkdir(exist_ok=True)
        REMEMBERED.write_text(ledger_dir, encoding="utf-8")
    return Path(d)


def run(ledger_dir: str, *args: str) -> str:
    """A kingsmint command in the ledger folder, with this extension's Python and kingsmint copy."""
    code = f"import sys; sys.path.insert(0, {str(HERE)!r}); sys.argv[0] = 'kingsmint'; from kingsmint.cli import main; main()"
    p = subprocess.run([sys.executable, "-c", code, *args], cwd=ledger(ledger_dir), capture_output=True, text=True,
                       encoding="utf-8", timeout=600)
    out = (p.stdout + p.stderr).strip()
    return f"{out}\n(exit {p.returncode})" if p.returncode else out or "(no output)"


@mcp.tool()
def kingsmint_new_ledger(title: str, currency: str = "EUR", locale: str = "sk_SK", language: str = "Slovak",
                         language_code: str = "sk", ledger_dir: str = "") -> str:
    """Create a new ledger from the template in an empty ledger folder. title: the owner's name, e.g. "Ján Novák"."""
    d = ledger(ledger_dir)
    if (d / "main.beancount").exists() or any(p.name not in ("inbox", ".DS_Store") for p in d.iterdir()):
        raise ValueError(f"{d} is not empty; use an empty folder (an inbox/ with statements is fine)")
    shutil.copytree(TEMPLATE, d, dirs_exist_ok=True)
    for name, values in {"main.beancount": {"TITLE": title, "CURRENCY": currency, "LOCALE": locale, "LANGUAGE_CODE": language_code},
                         "CLAUDE.md": {"LANGUAGE": language},
                         "pyproject.toml": {"KINGSMINT_SOURCE": "https://github.com/kingsmint/kingsmint"}}.items():
        f = d / name
        text = f.read_text(encoding="utf-8")
        for k, v in values.items():
            text = re.sub(rf'\b{k}\b', v, text)
        f.write_text(text, encoding="utf-8")
    versions.save(d, "New ledger")
    return f"Created a ledger in {d}. Put statements into {d / 'inbox'}, then call kingsmint_scan."


@mcp.tool()
def kingsmint_scan(ledger_dir: str = "") -> str:
    """Show what the statements in inbox/ are: bank, IBAN, period, holder, and the account they belong to or NEW."""
    return run(ledger_dir, "scan")


@mcp.tool()
def kingsmint_import(ledger_dir: str = "") -> str:
    """Import new statements from inbox/; each file ends on an ok, skip, or FAIL line. Saves a version."""
    out = run(ledger_dir, "import")
    versions.save(ledger(ledger_dir), "Import statements\n\n" + out)
    return out


@mcp.tool()
def kingsmint_check(ledger_dir: str = "") -> str:
    """Validate the ledger and the transfers between own accounts. No output means OK."""
    return run(ledger_dir, "check")


@mcp.tool()
def kingsmint_coverage(ledger_dir: str = "") -> str:
    """The periods each account's statements cover, and the missing periods to download."""
    return run(ledger_dir, "coverage")


@mcp.tool()
def kingsmint_rules(ledger_dir: str = "") -> str:
    """Preview what a reimport would change with the current rules, by rule, with examples."""
    return run(ledger_dir, "rules")


@mcp.tool()
def kingsmint_reimport(ledger_dir: str = "") -> str:
    """Rebuild ledger/ from documents/ with the current rules. Saves a version."""
    out = run(ledger_dir, "reimport")
    versions.save(ledger(ledger_dir), "Reimport with the current rules")
    return out


@mcp.tool()
def kingsmint_save(message: str, ledger_dir: str = "") -> str:
    """Save a version of the ledger folder after a change, e.g. "Rules: SSE gas and electricity by variable symbol"."""
    v = versions.save(ledger(ledger_dir), message)
    return f"Saved version {v}." if v else "Nothing changed since the last version."


@mcp.tool()
def kingsmint_history(limit: int = 20, ledger_dir: str = "") -> str:
    """The saved versions of the ledger, newest first: id, date, what changed."""
    rows = versions.history(ledger(ledger_dir), limit)
    return "\n".join(f"{v}  {date}  {title}" for v, date, title in rows) or "No versions yet."


@mcp.tool()
def kingsmint_restore(version: str = "", ledger_dir: str = "") -> str:
    """Go back: without version, undo the last change; with a version id from kingsmint_history, return to it.
    The restore is saved as a new version, so it can be undone too. Run kingsmint_check afterwards."""
    return versions.restore(ledger(ledger_dir), version)


@mcp.tool()
def kingsmint_query(query: str, ledger_dir: str = "") -> str:
    """Run a bean-query (BQL) query on main.beancount, e.g. uncategorized transactions:
    SELECT date, payee, narration, position WHERE account ~ 'Uncategorized'"""
    exe = Path(sys.executable).parent / ("bean-query.exe" if os.name == "nt" else "bean-query")
    p = subprocess.run([str(exe), "-q", "main.beancount", query], cwd=ledger(ledger_dir),
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (p.stdout + p.stderr).strip() or "(no rows)"


def up():
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).status
    except Exception:
        return 0


@mcp.tool()
def kingsmint_fava(ledger_dir: str = "") -> str:
    """Start Fava for the ledger on this computer (only reachable from this computer) and open it in the browser."""
    global fava
    main = ledger(ledger_dir) / "main.beancount"
    if not main.exists():
        raise ValueError(f"No main.beancount in {main.parent}; create a ledger with kingsmint_new_ledger")
    if fava and fava.args[-1] != str(main):
        fava.terminate()
        fava.wait()
        fava = None
    if not up():
        exe = Path(sys.executable).parent / ("fava.exe" if os.name == "nt" else "fava")
        fava = subprocess.Popen([str(exe), "--host", "127.0.0.1", "--port", str(PORT), str(main)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if up():
                break
            time.sleep(1)
    if not up():
        raise RuntimeError("Fava did not start; run kingsmint_check for errors in the ledger")
    webbrowser.open(f"http://127.0.0.1:{PORT}/")
    return f"Fava is open at http://127.0.0.1:{PORT}/ on the user's computer."


if __name__ == "__main__":
    try:
        mcp.run()
    finally:
        if fava:
            fava.terminate()
