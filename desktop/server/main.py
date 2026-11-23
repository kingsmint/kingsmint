"""Kingsmint MCP server for the Claude app: reads the ledger on this computer to answer questions; it never changes it."""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import versions

HERE = Path(__file__).parent  # in the bundle, holds the kingsmint package (desktop/build.py copies it)
PORT = 5057

mcp = MCPServer("kingsmint", instructions="""Kingsmint keeps a Beancount ledger in a folder on the user's computer.
These tools only read it, to answer questions about the user's money from any chat. They run on the user's computer,
not in your sandbox.
- Answer with numbers from kingsmint_query (bean-query SQL), and say which periods kingsmint_coverage shows as
  missing when they affect the answer. kingsmint_history tells why the ledger looks as it does.
- Do not change the ledger's files. Importing statements, categories, rules and fixes happen in the Kingsmint app,
  where an agent works on the ledger and every change is a version the user can undo; send the user there.""")

fava = None


REMEMBERED = Path.home() / ".kingsmint" / "ledger_dir"  # the last ledger folder a tool got: Cowork cannot set user_config
APP = {"darwin": Path.home() / "Library" / "Application Support", "win32": Path(os.environ.get("APPDATA", "."))}.get(
    sys.platform, Path.home() / ".config") / "org.kingsmint.app" / "ledger"  # the Kingsmint app's ledgers, newest first


def first_line(p: Path) -> str:
    return next(iter(p.read_text(encoding="utf-8").splitlines()), "").strip() if p.exists() else ""


def ledger(ledger_dir: str = "") -> Path:
    d = ledger_dir or os.environ.get("LEDGER_DIR", "") or first_line(REMEMBERED) or first_line(APP)
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
def kingsmint_banks(ledger_dir: str = "") -> str:
    """The supported banks and statement formats, also the ones this ledger adds in banks/."""
    return run(ledger_dir, "banks")


@mcp.tool()
def kingsmint_check(ledger_dir: str = "") -> str:
    """Validate the ledger and the transfers between own accounts. No output means OK."""
    return run(ledger_dir, "check")


@mcp.tool()
def kingsmint_coverage(ledger_dir: str = "") -> str:
    """The periods each account's statements cover, and the missing periods to download."""
    return run(ledger_dir, "coverage")


@mcp.tool()
def kingsmint_history(limit: int = 20, ledger_dir: str = "") -> str:
    """The saved versions of the ledger, newest first: id, date, what changed and why."""
    rows = versions.history(ledger(ledger_dir), limit)
    # shortcut: the body is cut at 8 lines (an import lists every file); add a version parameter when the rest is needed
    return "\n".join(f"{v}  {date}  " + "\n    ".join(msg.splitlines()[:9]) for v, date, msg in rows) or "No versions yet."


@mcp.tool()
def kingsmint_query(query: str, ledger_dir: str = "") -> str:
    """Run a bean-query (BQL) query on main.beancount, e.g. uncategorized transactions:
    SELECT date, coalesce(str(entry_meta('bank_payee')), payee) AS bank_text, narration, position
    WHERE account ~ '^(Expenses|Income):Uncategorized$'
    (bank_text is what rules match; payee may be a name a payee rule gave)"""
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
    """Start Fava for the ledger on this computer (only reachable from this computer, read-only) and open it in the
    browser."""
    global fava
    main = ledger(ledger_dir) / "main.beancount"
    if not main.exists():
        raise ValueError(f"No main.beancount in {main.parent}; the user creates a ledger in the Kingsmint app")
    if fava and fava.args[-1] != str(main):
        fava.terminate()
        fava.wait()
        fava = None
    if not up():
        exe = Path(sys.executable).parent / ("fava.exe" if os.name == "nt" else "fava")
        fava = subprocess.Popen([str(exe), "--read-only", "--host", "127.0.0.1", "--port", str(PORT), str(main)],
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
