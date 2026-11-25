"""`kingsmint upgrade --apply`: the migrations make a ledger of an older template equal to the current one."""
import shutil
from pathlib import Path

from kingsmint import cli, migrations

TEMPLATE = Path(__file__).parent.parent / "template"
NEW = ["main.beancount", "CLAUDE.md", "AGENTS.md", ".gitignore"]


def old_ledger(tmp_path):
    """The current template as a ledger of 0.1.8 had it: the migrations' changes reversed."""
    shutil.copytree(TEMPLATE, tmp_path, dirs_exist_ok=True)
    led = migrations.Ledger(tmp_path, TEMPLATE)
    for fn in migrations.MIGRATIONS.values():
        fn(led)  # nothing to do on the current template ...
    assert led.before == {}  # ... and nothing done
    claude = (tmp_path / "CLAUDE.md").read_text()
    claude = claude.replace(led.paragraph("CLAUDE.md", "The owner's own reports") + "\n\n", "")
    claude = claude.replace(" In the Kingsmint app, Fava already runs at\n`$KINGSMINT_FAVA_URL`: do not start another one, "
                            "and link its pages as the `explain` skill says.", "")
    claude = claude.replace("(skills `import`,\n`categorize`, `explain`, `add-bank`: from the `kingsmint` Claude Code "
                            "plugin, or copied into\n`.claude/skills/kingsmint-*` by `uv run kingsmint skills`).",
                            "(the `kingsmint` Claude Code\nplugin: skills `import`, `categorize`, `explain`, `add-bank`).")
    (tmp_path / "CLAUDE.md").write_text(claude)
    main = (tmp_path / "main.beancount").read_text()
    main = main.replace("AND account !~ '^Assets:(Me|Co):(Property|Loans)(:|$)' ", "")
    main = main.replace("; Fava: the Trends report, expenses by year with the change against the year before (in kingsmint)\n"
                        '2000-01-01 custom "fava-extension" "kingsmint.fava"\n', "")
    main = main.replace('Mark illiquid assets with liquid: "false"; property and loans given\n'
                        "; (Assets:Me:Property, Assets:Me:Loans, and the same under Co) count as illiquid by their name too.",
                        'Mark illiquid assets (property, loans given) with liquid: "false".')
    (tmp_path / "main.beancount").write_text(main)
    (tmp_path / "AGENTS.md").unlink()
    gitignore = (tmp_path / ".gitignore").read_text().split("# copies of kingsmint")[0]
    (tmp_path / ".gitignore").write_text(gitignore)
    (tmp_path / ".kingsmint-version").write_text("0.1.8\n")
    for name in NEW:
        assert name == "AGENTS.md" or (tmp_path / name).read_text() != (TEMPLATE / name).read_text()


def changelog(tmp_path, monkeypatch):
    log = tmp_path / "CHANGELOG.md"
    log.write_text("## 0.2.1\n\n- no ledger change\n\n## 0.2.0\n\n### Ledger\n\n- step of 0.2.0\n\n"
                   "## 0.1.9\n\n### Ledger\n\n- step of 0.1.9\n\n## 0.1.8\n\n### Ledger\n\n- old\n")
    monkeypatch.setattr(cli, "CHANGELOG", log)
    monkeypatch.setattr(cli, "pin", lambda installed: None)


def test_apply(tmp_path, monkeypatch, capsys):
    ledger = tmp_path / "ledger"
    old_ledger(ledger)
    changelog(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "check_text", lambda: "")
    monkeypatch.chdir(ledger)
    cli.upgrade(["--apply"])
    assert "ledger is at kingsmint 0.2.1" in capsys.readouterr().out
    for name in NEW:
        assert (ledger / name).read_text() == (TEMPLATE / name).read_text(), name
    assert (ledger / ".kingsmint-version").read_text() == "0.2.1\n"


def test_owner_text_goes_to_the_agent(tmp_path, monkeypatch, capsys):
    """The owner rewrote the first paragraph of CLAUDE.md: 0.1.9 stops there, and 0.2.0 waits for it."""
    ledger = tmp_path / "ledger"
    old_ledger(ledger)
    claude = (ledger / "CLAUDE.md").read_text().replace("(the `kingsmint` Claude Code\nplugin:", "(our plugin:")
    (ledger / "CLAUDE.md").write_text(claude)
    changelog(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "check_text", lambda: "")
    monkeypatch.chdir(ledger)
    cli.upgrade(["--apply"])
    out = capsys.readouterr().out
    assert "## 0.1.9\n\n- In `CLAUDE.md`, say where the skills come from" in out and "## 0.2.0\n\n- step of 0.2.0" in out
    assert "kingsmint upgrade --done" in out and (ledger / "AGENTS.md").exists()  # what it could do, it did
    assert (ledger / ".kingsmint-version").read_text() == "0.1.8\n"


def test_a_failing_check_undoes(tmp_path, monkeypatch, capsys):
    ledger = tmp_path / "ledger"
    old_ledger(ledger)
    changelog(tmp_path, monkeypatch)
    checks = iter(["", "FAIL something"])
    monkeypatch.setattr(cli, "check_text", lambda: next(checks))
    monkeypatch.chdir(ledger)
    before = {n: (ledger / n).read_text() for n in NEW if (ledger / n).exists()}
    cli.upgrade(["--apply"])
    assert "made `kingsmint check` fail" in capsys.readouterr().out
    assert {n: (ledger / n).read_text() for n in NEW if (ledger / n).exists()} == before
