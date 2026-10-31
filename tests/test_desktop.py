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
