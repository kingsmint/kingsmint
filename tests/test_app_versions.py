"""Versions of a ledger in the desktop app (app/server/jj_versions.py), with the real jj: undo, restore, and statements
going back to inbox/."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "server"))
import jj_versions as versions  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("jj"), reason="needs jj")


def test_versions(tmp_path):
    d = tmp_path

    def write(f, text):
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text(text)

    read = lambda f: (d / f).read_text()  # noqa: E731
    write(".gitignore", "inbox/*\n")
    write("rules.beancount", "v1\n")
    write("pyproject.toml", "kingsmint 1\n")
    versions.init(d, "New ledger")
    first = versions.history(d)[0].id
    with pytest.raises(versions.VersionError, match="only one version"):
        versions.restore(d)
    write("documents/s.pdf", "pdf")  # an import moved it from inbox/
    write("rules.beancount", "v2\n")
    write("pyproject.toml", "kingsmint 2\n")
    versions.save(d, "Import statements")
    versions.save(d, "Before fixing check problems")  # a mark: undo skips it
    write("rules.beancount", "v3\n")  # not saved: restore saves it first
    assert versions.dirty(d)
    assert versions.restore(d).back == []  # undo the unsaved change only
    assert read("rules.beancount") == "v2\n"
    done = versions.restore(d, first)
    assert read("rules.beancount") == "v1\n"
    assert read("pyproject.toml") == "kingsmint 2\n"  # the kingsmint version stays
    assert not (d / "documents/s.pdf").exists() and read("inbox/s.pdf") == "pdf" and done.back == ["s.pdf"]
    history = versions.history(d)
    assert [v.message for v in history] == [
        f"Restore {first}: New ledger", history[1].message, "Unsaved changes", "Before fixing check problems",
        "Import statements", "New ledger"]
    assert history[1].message.endswith(": Before fixing check problems") and history[3].empty and not history[4].empty
    with pytest.raises(versions.VersionError, match="bad version id"):
        versions.restore(d, "x; rm")


def test_restore_needs_the_ledgers_own_versions(tmp_path):
    # a ledger without versions inside another jj repository: jj would find that one and restore it
    outer, ledger = tmp_path, tmp_path / "ledger"
    ledger.mkdir()
    versions.jj(outer, "git", "init", "--colocate")
    (outer / "work.txt").write_text("v1\n")
    versions.jj(outer, "commit", "-m", "a")
    (outer / "work.txt").write_text("v2\n")
    versions.jj(outer, "commit", "-m", "b")
    (ledger / "main.beancount").write_text("x\n")
    with pytest.raises(versions.VersionError, match="no versions"):
        versions.restore(ledger)
    assert (ledger / "main.beancount").exists() and (outer / "work.txt").read_text() == "v2\n"
