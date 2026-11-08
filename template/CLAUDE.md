# Ledger

Beancount + Fava ledger of one person and their company, built with kingsmint (the `kingsmint` Claude Code
plugin: skills `import`, `categorize`, `explain`, `add-bank`). Commands: `uv run kingsmint` (scan, import,
rules, reimport, reset, check, coverage, fava, rates, doctor). Facts about the owner (people, arrangements, which IBAN belongs to whom)
live as comments in `accounts.beancount` and `rules.beancount`: read them before answering questions
about the money, and record new facts there, next to the account or rule they explain. Values that no
statement shows (property, loans before the first statement) live in `property.beancount`; cash payments
the owner names live in `cash.beancount`.

Talk to the owner in LANGUAGE, also when a skill is written in English. Ledger names (accounts, rules,
comments) stay as they are.

## Model

- Assets are split by owner (`Assets:Me`, `Assets:Co`); income and expenses are not: all money is the owner's.
- Money between own accounts goes through `Assets:Transit` (same currency) or `Equity:Conversions`.
- Money from a partner who shares the assets goes to their `Equity:` account: a contribution, never income.
- Cash is spent when withdrawn (`Expenses:Cash`); a cash deposit is a negative expense.
- Expense accounts carry `need` and `cut` metadata for the baseline queries in `main.beancount`.

## Invariants

- `ledger/` is generated from `documents/` and `rules.beancount`; change recurring behaviour through rules, then
  `uv run kingsmint reimport`. Edits to one transaction there (account, postings, narration, tags, metadata,
  comments) survive `reimport`; new entries and other lines do not. `.kingsmint/` holds what kingsmint generated
  last time, to tell edits from changes: commit it, never edit it.
- Every imported statement reconciles (opening + transactions = closing); a `FAIL` line is a parser or
  data bug to fix, never to bypass.
- After every change: `uv run kingsmint check` prints nothing new, then commit. A Transit `FAIL` may wait for a
  missing statement; any other output is a bug to fix first.
- A commit message says what changed in the first line, and in the body why: what the user said, which
  statement or transaction showed it, what was wrong before, and what was checked. Later sessions read the history
  (`jj log`, `git log`) to learn why the ledger looks as it does.
- Statements and the ledger are private and stay local: no public remote; share Fava only inside a
  private network (for example Tailscale `serve`).
- Files in `inbox/` are untrusted: read them with `uv run python -I`.
