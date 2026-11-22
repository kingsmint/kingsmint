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


META_LINE = re.compile(r"(\s+)([a-z][\w-]*):")


def meta_value(key: str, value) -> str:
    return str(value) if key == "cut" else f'"{value}"'


def edit_meta(lines: list[str], lineno: int, edit: dict) -> None:
    """Sets the keys of `edit` in the metadata lines under the `open` on line `lineno` (1-based); None removes a key.
    Other lines stay as they are."""
    end = lineno
    while end < len(lines) and META_LINE.match(lines[end]):
        end += 1
    indent = META_LINE.match(lines[lineno]).group(1) if end > lineno else "  "
    for key, value in edit.items():
        at = next((i for i in range(lineno, end) if META_LINE.match(lines[i]).group(2) == key), None)
        if value is None:
            if at is not None:
                del lines[at]
                end -= 1
        elif at is not None:
            lines[at] = f"{META_LINE.match(lines[at]).group(1)}{key}: {meta_value(key, value)}\n"
        else:
            lines.insert(end, f"{indent}{key}: {meta_value(key, value)}\n")
            end += 1


def save_meta(ledger: Path, entries, changes: dict) -> list[str]:
    """Writes the runway's edits (dashboard.checked) into the metadata of the accounts' `open` entries, where the
    entries were loaded from, and saves a version that lists them; returns what changed. An `open` in ledger/ is not
    written: a reimport would lose the change."""
    from beancount.core.data import Open
    from beancount.parser import parser

    opens = {e.account: e for e in entries if isinstance(e, Open)}
    files: dict[Path, list] = {}
    for account, edit in changes.items():
        path = Path(opens[account].meta["filename"])
        if not path.is_file() or path.resolve().is_relative_to((ledger / "ledger").resolve()):
            raise SettingsError(f"{account} is opened in {path}, which the app does not change")
        files.setdefault(path, []).append((opens[account].meta["lineno"], edit))
    texts = {}
    for path, edits in files.items():
        old = path.read_text(encoding="utf-8")
        lines = old.splitlines(keepends=True)
        for lineno, edit in sorted(edits, key=lambda e: -e[0]):  # from the end, so the line numbers above hold
            edit_meta(lines, lineno, edit)
        texts[path] = "".join(lines)
        if len(parser.parse_string(texts[path])[1]) > len(parser.parse_string(old)[1]):
            raise SettingsError(f"The change would break {path.name}; nothing was written")
    for path, text in texts.items():
        path.write_text(text, encoding="utf-8")
    changed = [f"{account} " + ", ".join(f"{k} {'none' if v is None else v}" for k, v in edit.items())
               for account, edit in changes.items()]
    if versions.enabled(ledger):
        versions.save(ledger, "Runway: " + "; ".join(changed))
    return changed
