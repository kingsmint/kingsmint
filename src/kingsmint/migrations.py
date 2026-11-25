"""The `### Ledger` changes of a version (CHANGELOG.md) as code, for `kingsmint upgrade --apply`.

A migration takes a Ledger and returns what it could not do, in words for the agent; [] means done. It can run again:
it changes nothing that is already as the template has it, and a part the owner changed it leaves to the agent.
Optional steps of the CHANGELOG (suggestions to the owner) are not migrations.
"""

from pathlib import Path


class Ledger:
    """The ledger's files, with what they held before this run, so that a migration that breaks the check is undone."""

    def __init__(self, root: Path, template: Path):
        self.root, self.template, self.before = root, template, {}

    def read(self, name: str) -> str | None:
        p = self.root / name
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write(self, name: str, text: str) -> None:
        self.before.setdefault(name, self.read(name))
        (self.root / name).write_text(text, encoding="utf-8")

    def restore(self) -> None:
        for name, text in self.before.items():
            if text is None:
                (self.root / name).unlink(missing_ok=True)
            else:
                (self.root / name).write_text(text, encoding="utf-8")
        self.before = {}

    def add_file(self, name: str) -> None:
        """The template's file, when the ledger has none."""
        if self.read(name) is None:
            self.write(name, (self.template / name).read_text(encoding="utf-8"))

    def add_lines(self, name: str, lines: list[str]) -> None:
        """The lines the file lacks, at its end."""
        text = self.read(name) or ""
        if missing := [line for line in lines if line not in text.splitlines()]:
            self.write(name, text + ("\n" if text and not text.endswith("\n") else "") + "\n".join(missing) + "\n")

    def replace(self, name: str, old: str, new: str, done: str) -> bool:
        """`old` becomes `new`; True also when `done` shows that it already happened. False: the owner changed the
        text, or the file is missing."""
        text = self.read(name)
        if text is None:
            return False
        if done in text:
            return True
        if old not in text:
            return False
        self.write(name, text.replace(old, new, 1))
        return True

    def paragraph(self, name: str, start: str) -> str:
        """The template's paragraph that begins with `start`."""
        text = (self.template / name).read_text(encoding="utf-8")
        return next(p for p in text.split("\n\n") if p.startswith(start))


def v0_1_9(led: Ledger) -> list[str]:
    left = []
    invert = '2000-01-01 custom "fava-option" "invert-income-liabilities-equity" "true"\n'
    trends = ('; Fava: the Trends report, expenses by year with the change against the year before (in kingsmint)\n'
              '2000-01-01 custom "fava-extension" "kingsmint.fava"\n')
    if not led.replace("main.beancount", invert, invert + trends, '"fava-extension" "kingsmint.fava"'):
        left.append('In `main.beancount`, add the line `2000-01-01 custom "fava-extension" "kingsmint.fava"` with its '
                    "comment from the template, below the other `fava-option` lines.")
    led.add_file("AGENTS.md")
    led.add_lines(".gitignore", ["# copies of kingsmint's skills (`kingsmint skills`) and this computer's agent settings",
                                 ".claude/skills/kingsmint-*/", ".claude/settings.local.json"])
    if not led.replace("CLAUDE.md",
                       "built with kingsmint (the `kingsmint` Claude Code\nplugin: skills `import`, `categorize`, "
                       "`explain`, `add-bank`).",
                       "built with kingsmint (skills `import`,\n`categorize`, `explain`, `add-bank`: from the `kingsmint` "
                       "Claude Code plugin, or copied into\n`.claude/skills/kingsmint-*` by `uv run kingsmint skills`).",
                       "`uv run kingsmint skills`"):
        left.append("In `CLAUDE.md`, say where the skills come from as the template's first paragraph does.")
    return left


def v0_2_0(led: Ledger) -> list[str]:
    left = []
    if not led.replace("CLAUDE.md", "rates, doctor). Facts about the owner",
                       "rates, doctor). In the Kingsmint app, Fava already runs at\n`$KINGSMINT_FAVA_URL`: do not start "
                       "another one, and link its pages as the `explain` skill says. Facts about the owner",
                       "$KINGSMINT_FAVA_URL"):
        left.append("In `CLAUDE.md`, after the list of commands, add the two sentences about `$KINGSMINT_FAVA_URL` from "
                    "the template.")
    reports = led.paragraph("CLAUDE.md", "The owner's own reports")
    if not led.replace("CLAUDE.md", "\n\nTalk to the owner", f"\n\n{reports}\n\nTalk to the owner", "reports/*.toml"):
        left.append('In `CLAUDE.md`, before "Talk to the owner", add the paragraph about `reports/*.toml` from the '
                    "template.")
    where = "WHERE account ~ '^Assets:(Me|Co):' AND "
    if not led.replace("main.beancount", where + "coalesce",
                       where + "account !~ '^Assets:(Me|Co):(Property|Loans)(:|$)' AND coalesce",
                       "(Property|Loans)(:|$)"):
        left.append("In `main.beancount`, in the query `Liquid money`, add "
                    "`AND account !~ '^Assets:(Me|Co):(Property|Loans)(:|$)'` after `WHERE account ~ '^Assets:(Me|Co):'`.")
    led.replace("main.beancount",
                '; Runway = liquid money / baseline. Mark illiquid assets (property, loans given) with liquid: "false".\n',
                '; Runway = liquid money / baseline. Mark illiquid assets with liquid: "false"; property and loans given\n'
                "; (Assets:Me:Property, Assets:Me:Loans, and the same under Co) count as illiquid by their name too.\n",
                "count as illiquid by their name too")  # the comment only: an owner's own comment stays
    return left


MIGRATIONS = {"0.1.9": v0_1_9, "0.2.0": v0_2_0}
