"""The versions of a ledger folder, read with dulwich (pure Python): the Kingsmint app writes them with jj, colocated
with git, and the Claude app only reads them."""

from pathlib import Path

from dulwich.repo import Repo


def history(d: Path, limit: int = 20) -> list[tuple[str, str, str]]:
    """(id, ISO date, message), newest first."""
    import datetime as dt
    if not (d / ".git").exists():
        return []
    return [(e.commit.id.decode()[:7], dt.datetime.fromtimestamp(e.commit.commit_time).isoformat(" ", "minutes"),
             e.commit.message.decode().strip()) for e in Repo(str(d)).get_walker(max_entries=limit)]
