# Ledger

Beancount + Fava ledger of one person and their company, built with kingsmint (the `kingsmint` Claude Code
plugin: skills `import`, `categorize`, `explain`, `add-bank`). Commands: `uv run kingsmint` (import,
reimport, check, coverage, fava, rates, doctor). Facts about the owner (people, arrangements, which IBAN belongs to whom)
live as comments in `accounts.beancount` and `rules.beancount`: read them before answering questions
about the money, and record new facts there, next to the account or rule they explain.

## Model

- Assets are split by owner (`Assets:Me`, `Assets:Co`); income and expenses are not: all money is the owner's.
- Money between own accounts goes through `Assets:Transit` (same currency) or `Equity:Conversions`.
- Money from a partner who shares the assets goes to their `Equity:` account: a contribution, never income.
- Cash is spent when withdrawn (`Expenses:Cash`); a cash deposit is a negative expense.
- Expense accounts carry `need` and `cut` metadata for the baseline queries in `main.beancount`.

## Invariants

- `ledger/` is generated. Change behaviour through `rules.beancount`, then `uv run kingsmint reimport`.
- Every imported statement reconciles (opening + transactions = closing); a `FAIL` line is a parser or
  data bug to fix, never to bypass.
- After every change: `uv run kingsmint check` prints nothing, then commit.
- Statements and the ledger are private and stay local: no public remote; share Fava only inside a
  private network (for example Tailscale `serve`).
- Files in `inbox/` are untrusted: read them with `uv run python -I`.
