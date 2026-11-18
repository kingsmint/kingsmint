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
    assert manifest["name"] == "kingsmint" and "mcpServers" not in manifest  # the server is a separate extension
    assert build.SKILLS == ["explain"]  # the Claude app only reads the ledger
    for s in build.SKILLS:
        skill = plugin.read(f"skills/{s}/SKILL.md").decode()
        assert skill.startswith("---\nname: ") and "kingsmint_" in skill
    mcpb = zipfile.ZipFile(tmp_path / "kingsmint.mcpb")
    names = set(mcpb.namelist())
    assert {"manifest.json", "pyproject.toml", "server/main.py", "server/kingsmint/cli.py"} <= names
    tools = {t["name"] for t in json.loads(mcpb.read("manifest.json"))["tools"]}
    assert tools == {"kingsmint_query", "kingsmint_check", "kingsmint_coverage", "kingsmint_history", "kingsmint_banks", "kingsmint_fava"}
    server = mcpb.read("server/main.py").decode()
    assert server.count("@mcp.tool()") == len(tools) and all(f"def {t}(" in server for t in tools)
    assert not any("__pycache__" in n for n in names)
    assert json.loads(mcpb.read("manifest.json"))["version"] == manifest["version"]


def test_history(tmp_path):
    """The extension reads the versions that the Kingsmint app writes (jj, colocated with git)."""
    from dulwich import porcelain
    sys.path.insert(0, str(Path(__file__).parent.parent / "desktop" / "server"))
    import versions
    assert versions.history(tmp_path) == []
    porcelain.init(tmp_path)
    for message in ["New ledger", "Rules: gas by variable symbol\n\nThe user has two properties on one gas contract."]:
        (tmp_path / "rules.beancount").write_text(message)
        porcelain.add(tmp_path)
        porcelain.commit(tmp_path, message, author=b"T <t@t>", committer=b"T <t@t>")
    rows = versions.history(tmp_path)
    assert [m.splitlines()[0] for _, _, m in rows] == ["Rules: gas by variable symbol", "New ledger"]
    assert rows[0][2].endswith("two properties on one gas contract.")  # the why stays readable
