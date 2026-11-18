"""Build the plugin for the Claude app (chat and Cowork): `uv run python desktop/build.py` -> desktop/dist/kingsmint.plugin.

Two files, both installed on each computer: desktop/dist/kingsmint.plugin holds the skills (Plugins in the sidebar >
Add > Upload plugin), desktop/dist/kingsmint.mcpb the kingsmint MCP server (double-click it to install). The server is a separate
extension because Claude starts an MCPB inside a plugin with the `uv` on PATH, which most users lack; an extension
gets Claude's own uv, which installs Python and the dependencies.
"""

import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

DESKTOP = Path(__file__).parent
ROOT = DESKTOP.parent
SKILLS = ["explain"]  # the Claude app only reads the ledger; the Kingsmint app changes it
NOTE = (
    "> **In the Claude app** (chat or Cowork): the kingsmint extension reads the ledger on the user's computer. Run "
    "`uv run bean-query -q main.beancount \"<query>\"` as the tool `kingsmint_query`, and `uv run kingsmint check` and "
    "`coverage` as `kingsmint_check` and `kingsmint_coverage`. Do not change the ledger's files: the user changes "
    "the ledger in the Kingsmint app. The first `kingsmint_*` call needs `ledger_dir` when the Kingsmint app has not "
    "opened a ledger on this computer: the ledger folder's path on the user's computer (not the /sessions/... sandbox "
    "path); later calls remember it. If you do not know that path, ask the user. If the tools are missing: tell the "
    "user to install the kingsmint extension (`kingsmint.mcpb`) by double-clicking it on this computer."
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
        for f in ["main.py", "versions.py"]:
            z.write(DESKTOP / "server" / f, f"server/{f}")
        for name, f in files(ROOT / "src" / "kingsmint", "server/kingsmint"):
            z.write(f, name)

    plugin = {"name": "kingsmint", "displayName": "Kingsmint", "version": version, "description": manifest["description"],
              "author": {"name": "kingsmint"}, "license": "MIT"}
    zip_path = out / "kingsmint.plugin"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(".claude-plugin/plugin.json", json.dumps(plugin, indent=2))
        z.write(DESKTOP / "README.md", "README.md")
        z.write(ROOT / "LICENSE", "LICENSE")
        for s in SKILLS:
            z.writestr(f"skills/{s}/SKILL.md", desktop_skill((ROOT / "skills" / s / "SKILL.md").read_text(encoding="utf-8")))
    return zip_path


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else DESKTOP / "dist"))
