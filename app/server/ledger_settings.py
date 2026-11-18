"""Settings of a ledger live in its files, where Fava and the agent read them: the title, currency, number format and
Fava's language in main.beancount, the agent's language in CLAUDE.md. Accounts are read only: they come from the
statements, and the agent changes them."""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

import jj_versions as versions

TITLE = 'option "title" "'
CURRENCY = 'option "operating_currency" "'
LOCALE = 'custom "fava-option" "locale" "'
LANGUAGE = 'custom "fava-option" "language" "'
TALK = "Talk to the owner in "
AGENT_LANGUAGES = {"sk": "Slovak", "en": "English"}  # as CLAUDE.md names them


def quoted(text: str, marker: str) -> str | None:
    """The value in the quotes that follow `marker` on the first line, not a comment, that has it."""
    for line in text.splitlines():
        if marker in line and not line.lstrip().startswith(";"):
            rest = line[line.index(marker) + len(marker):]
            return rest[:rest.index('"')] if '"' in rest else None
    return None


def set_quoted(text: str, marker: str, value: str) -> str | None:
    """`text` with the value after `marker` replaced; None when no line has the marker."""
    lines = text.split("\n")
    for n, line in enumerate(lines):
        i = line.find(marker)
        if i >= 0 and not line.lstrip().startswith(";") and '"' in line[i + len(marker):]:
            a = i + len(marker)
            lines[n] = line[:a] + value + line[line.index('"', a):]
            return "\n".join(lines)
    return None


@dataclass
class Settings:
    title: str
    currency: str
    locale: str
    language: str  # "sk" or "en": Fava's and the agent's


def agent_language(claude: str) -> str:
    i = claude.find(TALK)
    return re.split(r"[,.\n]", claude[i + len(TALK):])[0] if i >= 0 else ""


def read(ledger: Path) -> Settings:
    main = (ledger / "main.beancount").read_text()
    claude = (ledger / "CLAUDE.md").read_text() if (ledger / "CLAUDE.md").exists() else ""
    return Settings(quoted(main, TITLE) or "", quoted(main, CURRENCY) or "", quoted(main, LOCALE) or "",
                    "sk" if agent_language(claude) == "Slovak" else "en")


@dataclass
class Account:
    account: str
    currency: str
    number: str  # IBAN or broker account number
    note: str


def statement_accounts(text: str) -> list[Account]:
    """The accounts that statements go to: an `open` with `iban` or `ibkr` metadata, and its comment."""
    out, last = [], None
    for line in text.splitlines():
        code, _, note = line.partition(";")
        words = code.split()
        if len(words) >= 3 and words[1] == "open" and not line[:1].isspace():
            last = Account(words[2], words[3] if len(words) > 3 else "", "", note.strip())
        elif last and line[:1].isspace():
            number = quoted(code, 'iban: "') or quoted(code, 'ibkr: "')
            if number:
                out.append(Account(**{**asdict(last), "number": number}))
        else:
            last = None
    return out


def accounts(ledger: Path) -> list[Account]:
    path = ledger / "accounts.beancount"
    return statement_accounts(path.read_text()) if path.exists() else []


class SettingsError(Exception):
    pass


def save(ledger: Path, title: str, locale: str, language: str) -> list[str]:
    """Writes the changed settings into the ledger's files and saves a version that lists them; returns what changed.
    The currency is not written: it is in the saved queries too, so the agent changes it."""
    title, locale = title.strip(), locale.strip()
    for value in (title, locale):
        if not value or any(c in value for c in '"\\\n'):
            raise SettingsError(f"Not a valid value: {value!r}")
    if language not in AGENT_LANGUAGES:
        raise SettingsError(f"Not a language: {language!r}")
    path = ledger / "main.beancount"
    main = path.read_text()
    changed = []
    for marker, value, what in ((TITLE, title, "title"), (LOCALE, locale, "number format"),
                                (LANGUAGE, language, "Fava language")):
        if quoted(main, marker) != value:
            main = set_quoted(main, marker, value)
            if main is None:
                raise SettingsError(f"main.beancount has no {what} line")
            changed.append(f"{what} {value}")
    claude_path = ledger / "CLAUDE.md"
    claude = claude_path.read_text() if claude_path.exists() else ""
    new_claude = None
    if TALK in claude and agent_language(claude) != AGENT_LANGUAGES[language]:
        i = claude.index(TALK) + len(TALK)
        new_claude = claude[:i] + AGENT_LANGUAGES[language] + claude[i + len(agent_language(claude)):]
        changed.append(f"agent language {AGENT_LANGUAGES[language]}")
    if not changed:
        return []
    path.write_text(main)
    if new_claude is not None:
        claude_path.write_text(new_claude)
    if versions.enabled(ledger):
        versions.save(ledger, "Settings: " + ", ".join(changed))
    return changed
