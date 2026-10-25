---
name: setup
description: Create a new kingsmint ledger repository in the current directory.
disable-model-invocation: true
---

# Set up a ledger

The template is `template/` in this plugin's directory (`${CLAUDE_PLUGIN_ROOT}/template`).

1. Check the tools: `uv`, and `jj` or `git`.
   - uv not on PATH: the installer puts it in `~/.local/bin`, which a shell started before the
     install does not have on PATH. If `~/.local/bin/uv` exists, use it. Otherwise ask the user for
     permission, then install it with the official installer:
     macOS and Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`, Windows
     `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
     When `uv --version` still fails in this shell, call uv by the full path the installer printed
     for the rest of the setup, and tell the user to open a new terminal.
   - jj and git missing: name the install page (https://jj-vcs.github.io/jj/latest/install-and-setup/
     or https://git-scm.com/downloads) and stop until one is installed.
2. Check that the current directory is empty (an `inbox/` with statements counts as empty), or ask before using a non-empty one.
3. Copy the template: `cp -R "${CLAUDE_PLUGIN_ROOT}/template/." .`
4. `pyproject.toml`: replace `{ git = "KINGSMINT_SOURCE" }`. When `${CLAUDE_PLUGIN_ROOT}` is a checkout the
   user develops (it is outside `~/.claude/plugins/`, for example from `claude --plugin-dir`), use
   `{ path = "${CLAUDE_PLUGIN_ROOT}", editable = true }`; otherwise `{ git = "https://github.com/kingsmint/kingsmint" }`.
   Run `uv sync` (it installs the Python version in `.python-version` when missing).
5. Ask the user to download their statements into `inbox/`, as far back as each bank allows, for every
   account (personal and company, also closed ones), and to say when they are done. Ask nothing else:
   the rest comes from the statements.
6. Run `uv run kingsmint scan`. Propose, in one message for the user to confirm or correct:
   - The accounts, as "Accounts from statements" in the `import` skill describes, as a table: account,
     IBAN, holder, currency, period.
   - The title: the personal holder's name as people write it, without degrees and capitals (`ING. JÁN NOVÁK`
     and `Novák Ján, Ing.` are `Ján Novák`).
   - The main currency: the currency of most accounts.
   - The locale for Fava number formatting, from the IBAN country: `SK` is `sk_SK`, `CZ` is `cs_CZ`,
     `DE` is `de_DE`, and so on; `en_US` when the country is unclear.

   Ask a short question only for what the statements cannot show; the `import` skill names these cases.
7. Fill the template from the confirmed answers:
   - `main.beancount`: replace `TITLE`, `CURRENCY` (also in the queries), and `LOCALE`.
   - `accounts.beancount`: one `open` per account with its `iban` or `ibkr`, and the holder as a
     comment. A broker also gets the four investment accounts from the commented example. Remove the
     commented examples.
8. Run `uv run kingsmint rates` and `uv run kingsmint doctor`.
9. Create the repository (`jj git init` or `git init`), and commit `Initial ledger`. No remote: the
   ledger is private.
10. Run the `import` skill, then the `categorize` skill.

Done when `uv run kingsmint doctor` reports no `FAIL`, the first commit exists, and the import has run.
