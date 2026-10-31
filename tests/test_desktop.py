"""The Claude app plugin: desktop/build.py packs the skills and the server bundle."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "desktop"))
import build  # noqa: E402


def test_build(tmp_path):
    plugin = zipfile.ZipFile(build.build(tmp_path))
    manifest = json.loads(plugin.read(".claude-plugin/plugin.json"))
    assert manifest["name"] == "kingsmint" and manifest["mcpServers"] == "./servers/kingsmint.mcpb"
    for s in ["setup", *build.SKILLS]:
        skill = plugin.read(f"skills/{s}/SKILL.md").decode()
        assert skill.startswith("---\nname: ") and "kingsmint_" in skill
    mcpb = zipfile.ZipFile(tmp_path / "kingsmint.mcpb")
    names = set(mcpb.namelist())
    assert {"manifest.json", "pyproject.toml", "server/main.py", "server/kingsmint/cli.py", "template/main.beancount"} <= names
    assert not any("__pycache__" in n for n in names)
    assert json.loads(mcpb.read("manifest.json"))["version"] == manifest["version"]


def test_versions(tmp_path):
    sys.path.insert(0, str(Path(__file__).parent.parent / "desktop" / "server"))
    import versions
    (tmp_path / ".gitignore").write_text("inbox/*\n")
    (tmp_path / "rules.beancount").write_text("v1\n")
    first = versions.save(tmp_path, "New ledger")
    assert versions.save(tmp_path, "Nothing") is None
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "s.pdf").write_bytes(b"pdf")  # an import moved it from inbox/
    (tmp_path / "rules.beancount").write_text("v2\n")
    versions.save(tmp_path, "Import statements")
    (tmp_path / "rules.beancount").write_text("v3\n")  # not saved: restore saves it first
    assert "s.pdf" not in versions.restore(tmp_path)  # undo the unsaved change only
    assert (tmp_path / "rules.beancount").read_text() == "v2\n"
    out = versions.restore(tmp_path, first)
    assert (tmp_path / "rules.beancount").read_text() == "v1\n" and not (tmp_path / "documents" / "s.pdf").exists()
    assert (tmp_path / "inbox" / "s.pdf").read_bytes() == b"pdf" and "s.pdf" in out  # the statement is never lost
    titles = [t for _, _, t in versions.history(tmp_path)]
    assert titles[0] == f"Restore {first}: New ledger" and titles[2:] == ["Unsaved changes", "Import statements", "New ledger"]
