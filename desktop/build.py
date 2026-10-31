"""Build the plugin for the Claude app (chat and Cowork): `uv run python desktop/build.py` -> desktop/dist/kingsmint.zip.

The zip holds the skills and the kingsmint MCP server as an MCPB bundle (desktop/dist/kingsmint.mcpb). Upload it in
Claude: Customize > Plugins > Add > Upload plugin. The server runs on the user's computer; Claude installs its Python
and dependencies with its own uv.
"""

import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

DESKTOP = Path(__file__).parent
ROOT = DESKTOP.parent
SKILLS = ["import", "categorize", "explain"]  # add-bank changes the parser code, which is inside the bundle
NOTE = (
    "> **In the Claude app** (chat or Cowork): the plugin's kingsmint server runs the commands on the user's computer. "
    "Run `uv run kingsmint <command>` as the tool `kingsmint_<command>` (`kingsmint_scan`, `kingsmint_import`, "
    "`kingsmint_rules`, `kingsmint_reimport`, `kingsmint_check`, `kingsmint_coverage`), and "
    "`uv run bean-query -q main.beancount \"<query>\"` as `kingsmint_query`. Edit `accounts.beancount`, "
    "`rules.beancount` and `property.beancount` directly in the connected folder. There is no version control yet: "
    "skip the commit and diff steps. The first `kingsmint_*` call needs `ledger_dir`: the connected folder's path on "
    "the user's computer (not the /sessions/... sandbox path); later calls remember it. If you do not know that path, "
    "ask the user. If the tools are missing, the session does not run on the user's computer: tell the user to "
    "connect the ledger folder to the chat."
)


def files(folder, prefix):
    """(path in the zip, file) for every file in folder, without caches."""
    return [(f"{prefix}/{f.relative_to(folder).as_posix()}", f) for f in sorted(folder.rglob("*"))
            if f.is_file() and "__pycache__" not in f.parts and f.name != ".DS_Store"]


def desktop_skill(text):
    """A Claude Code skill for the Claude app: the note goes right after the front matter."""
    m = re.match(r"---\n.*?\n---\n", text, re.S)
    return m[0] + "\n" + NOTE + "\n" + text[m.end():]


def build(out=DESKTOP / "dist"):
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    out.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((DESKTOP / "manifest.json").read_text(encoding="utf-8")) | {"version": version}
    mcpb = out / "kingsmint.mcpb"
    with zipfile.ZipFile(mcpb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        z.write(DESKTOP / "pyproject.toml", "pyproject.toml")
        z.write(DESKTOP / "server" / "main.py", "server/main.py")
        for name, f in files(ROOT / "src" / "kingsmint", "server/kingsmint") + files(ROOT / "template", "template"):
            z.write(f, name)

    plugin = {"name": "kingsmint", "displayName": "Kingsmint", "version": version, "description": manifest["description"],
              "author": {"name": "kingsmint"}, "license": "MIT", "mcpServers": "./servers/kingsmint.mcpb"}
    zip_path = out / "kingsmint.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(".claude-plugin/plugin.json", json.dumps(plugin, indent=2))
        z.write(DESKTOP / "README.md", "README.md")
        z.write(ROOT / "LICENSE", "LICENSE")
        z.write(mcpb, "servers/kingsmint.mcpb")
        z.write(DESKTOP / "setup.md", "skills/setup/SKILL.md")
        for s in SKILLS:
            z.writestr(f"skills/{s}/SKILL.md", desktop_skill((ROOT / "skills" / s / "SKILL.md").read_text(encoding="utf-8")))
    return zip_path


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else DESKTOP / "dist"))
