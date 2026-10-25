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
2. Check that the current directory is empty, or ask before using a non-empty one.
3. Interview the user. Ask in one numbered list:
   1. Banks and brokers, and which accounts are personal or the company's.
   2. Company: legal form, VAT-registered, whether an accountant keeps the official books, whether
      the company pays personal costs.
   3. Household: a partner who shares the assets, children, regular support to family.
   4. A title for the ledger, the main currency, and the locale for Fava number formatting (for example `sk_SK`, `en_US`).
   5. Where kingsmint comes from: a git URL, or a local checkout for development.
4. Copy the template: `cp -R "${CLAUDE_PLUGIN_ROOT}/template/." .`
5. Fill it from the answers:
   - `pyproject.toml`: replace `KINGSMINT_SOURCE` with the git URL, or use `{ path = "...", editable = true }`.
   - `main.beancount`: replace `TITLE`, `CURRENCY` (also in the queries), and `LOCALE`.
   - `accounts.beancount`:
     - One `open` per bank account: `Assets:<Me|Co>:<Bank>:<Kind>`, where `<Bank>` is the short name
       people use, in ASCII (`Tatra`, `VUB`, `Fio`) and `<Kind>` is `Current`, `Savings`, or `USD` for a second currency.
       The `iban` comes from the first statement (the `import` skill adds it).
     - A broker, named the same way (`IBKR`): `Assets:Me:<Broker>:Cash` with `ibkr` metadata and `:Securities "FIFO"`,
       and the four investment accounts from the commented example.
     - A partner who shares the assets: `Equity:<Name>`.
     - Leave income and expenses as they are: the `categorize` skill builds them from the transactions.
     - What the user said (who pays what, arrangements) as comments next to the accounts; personal
       costs paid by the company become rules later, when their transactions appear.
     - Remove the commented examples.
6. Run `uv sync` (it installs the Python version in `.python-version` when missing), `uv run kingsmint rates`, `uv run kingsmint doctor`.
7. Create the repository (`jj git init` or `git init`), and commit `Initial ledger`. No remote: the
   ledger is private.
8. Ask the user to download their statements into `inbox/` (as far back as the bank allows), then run
   the `import` skill and then the `categorize` skill.

Done when `uv run kingsmint doctor` reports no `FAIL`, the first commit exists, and the user knows where to put statements.
