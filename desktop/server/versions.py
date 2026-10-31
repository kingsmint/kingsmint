"""Versions of a ledger folder for the Claude app: a plain git repository written with dulwich (pure Python),
because the app's users have neither git nor jj. `jj git init --colocate` can take it over later."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

AUTHOR = b"Kingsmint <kingsmint@localhost>"


def save(d: Path, message: str) -> str | None:
    """Commit every change in the folder (.gitignore applies); None when nothing changed."""
    if not (d / ".git").exists():
        porcelain.init(d)
    porcelain.add(d)
    staged = porcelain.status(d).staged
    if Repo(str(d)).refs.as_dict().get(b"HEAD") and not any(staged.values()):
        return None
    return porcelain.commit(d, message, author=AUTHOR, committer=AUTHOR).decode()[:7]


def history(d: Path, limit: int = 20) -> list[tuple[str, str, str]]:
    """(id, ISO date, first line of the message), newest first."""
    import datetime as dt
    if not (d / ".git").exists():
        return []
    return [(e.commit.id.decode()[:7], dt.datetime.fromtimestamp(e.commit.commit_time).isoformat(" ", "minutes"),
             e.commit.message.decode().splitlines()[0]) for e in Repo(str(d)).get_walker(max_entries=limit)]


def restore(d: Path, version: str = "") -> str:
    """Make the folder look like `version` (default: before the last change), as a new version on top, so a restore
    can be undone too. Statements in documents/ that the old version lacks go back to inbox/, never lost."""
    save(d, "Unsaved changes")
    repo = Repo(str(d))
    commits = [e.commit for e in repo.get_walker()]
    if version:
        target = next((c for c in commits if c.id.decode().startswith(version)), None)
        if target is None:
            raise ValueError(f"No version {version}; see kingsmint_history")
    elif len(commits) < 2:
        raise ValueError("Nothing to undo: there is only one version")
    else:
        target = commits[1]
    docs = {p: p.read_bytes() for p in (d / "documents").rglob("*") if p.is_file()} if (d / "documents").exists() else {}
    head = repo.head()
    porcelain.reset(d, "hard", target.id)
    porcelain.reset(d, "soft", head)  # keep the history: the restore becomes the newest version
    back = []
    for p, data in docs.items():
        if not p.exists():
            (d / "inbox").mkdir(exist_ok=True)
            (d / "inbox" / p.name).write_bytes(data)
            back.append(p.name)
    title = target.message.decode().splitlines()[0]
    save(d, f"Restore {target.id.decode()[:7]}: {title}")
    return f"Restored the version {target.id.decode()[:7]} ({title})." + (
        f" Statements moved back to inbox/ to import again: {', '.join(back)}." if back else "")
