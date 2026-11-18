"""Versions of a ledger: a jj repository, colocated with git. The app saves a version before each task it gives an
agent, the agent after each change (`jj commit`), and jj snapshots the files at every jj command anyway. A restore is
a new version, so it can be undone too."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# the app's own jj (a sidecar of the app), else the one on PATH
JJ = os.environ.get("KINGSMINT_JJ") or "jj"

# The files a restore leaves as they are: which kingsmint the ledger runs. Going back to the accounting of last month
# must not quietly install last month's kingsmint, whose template the ledger no longer matches.
KEEP = '~(root-file:"pyproject.toml" | root-file:"uv.lock" | root-file:".kingsmint-version" | root-file:".python-version")'


class VersionError(Exception):
    pass


def jj(ledger: Path, *args: str) -> str:
    out = subprocess.run([JJ, *args, "--color", "never"], cwd=ledger, capture_output=True, text=True)
    if out.returncode:
        raise VersionError(out.stderr.strip())
    return out.stdout


def enabled(ledger: Path) -> bool:
    return (ledger / ".jj").exists()


def init(ledger: Path, message: str) -> None:
    """Makes the ledger a jj repository whose first version, `message`, holds the files as they are. A git
    repository (a ledger of the Claude app) keeps its history."""
    if not enabled(ledger):
        jj(ledger, "git", "init", "--colocate")
        # account history exports are often larger than jj's 1 MiB default, which jj leaves out of versions
        jj(ledger, "config", "set", "--repo", "snapshot.max-new-file-size", "100MiB")
        try:
            jj(ledger, "config", "get", "user.name")
        except VersionError:
            jj(ledger, "config", "set", "--repo", "user.name", "Kingsmint")
            jj(ledger, "config", "set", "--repo", "user.email", "kingsmint@localhost")
    jj(ledger, "commit", "-m", message)


def save(ledger: Path, message: str) -> None:
    """Saves a version, also with no change: then it marks a point to return to, such as "Before importing
    statements"."""
    if not enabled(ledger):
        raise VersionError("This ledger has no versions")
    jj(ledger, "commit", "-m", message)


@dataclass
class Version:
    id: str
    date: str
    message: str
    empty: bool  # changes no file: a mark such as "Before importing statements"


def dirty(ledger: Path) -> bool:
    """Files changed since the last version."""
    return jj(ledger, "log", "--no-graph", "-r", "@", "-T", "empty").strip() == "false"


def history(ledger: Path, limit: int = 30) -> list[Version]:
    """The last `limit` versions, newest first."""
    template = ('commit_id.short(8) ++ "\\x1f" ++ committer.timestamp().local().format("%Y-%m-%d %H:%M") ++ "\\x1f" '
                '++ if(empty, "1", "0") ++ "\\x1f" ++ description ++ "\\x1e"')
    out = jj(ledger, "log", "--no-graph", "-r", "::@- ~ root()", "-n", str(limit), "-T", template)
    versions = []
    for v in out.split("\x1e"):
        fields = v.lstrip("\n").split("\x1f", 3)
        if len(fields) == 4:
            versions.append(Version(fields[0], fields[1], fields[3].strip(), fields[2] == "1"))
    return versions


@dataclass
class Restored:
    id: str
    title: str
    back: list[str]  # statements moved back to inbox/, to import again


def restore(ledger: Path, id: str | None = None) -> Restored:
    """Returns to version `id`, or without it, undoes the last change: the files become as they were, saved as a new
    version. Unsaved changes are saved first. Statements in documents/ that the old version lacks go to inbox/."""
    if id is not None and not re.fullmatch(r"[0-9a-f]{4,}", id):
        raise VersionError(f"bad version id {id}")
    if not enabled(ledger):  # else jj finds a repository above the ledger and restores that one
        raise VersionError("This ledger has no versions")
    if dirty(ledger):
        jj(ledger, "commit", "-m", "Unsaved changes")
    # undo goes to the version before the newest one that changed files: marks such as "Before importing statements"
    # change nothing
    target = jj(ledger, "log", "--no-graph", "-r", id or "latest(::@- ~ empty())-", "-T", "commit_id").strip()
    if not target.strip("0"):
        raise VersionError("Nothing to undo: there is only one version")
    try:
        kept = set(jj(ledger, "file", "list", "-r", target, "documents").splitlines())
    except VersionError:  # the old version has no documents/
        kept = set()
    documents = ledger / "documents"
    statements = [(f.name, f.read_bytes()) for f in sorted(documents.rglob("*")) if f.is_file()
                  and f.relative_to(ledger).as_posix() not in kept] if documents.exists() else []
    jj(ledger, "restore", "--from", target, KEEP)
    inbox = ledger / "inbox"
    inbox.mkdir(exist_ok=True)
    for name, data in statements:
        if not (inbox / name).exists():
            (inbox / name).write_bytes(data)
    title = jj(ledger, "log", "--no-graph", "-r", target, "-T", "description.first_line()").strip()
    jj(ledger, "commit", "-m", f"Restore {target[:8]}: {title}")
    return Restored(target[:8], title, [name for name, _ in statements])
