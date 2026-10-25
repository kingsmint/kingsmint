---
name: categorize
description: Categorize transactions by writing rules in rules.beancount. Use for Uncategorized transactions, a wrong category, or a new payee.
---

# Categorize

1. List the uncategorized transactions, grouped by counterparty (IBAN, else payee), largest total first:
   ```
   uv run bean-query -q main.beancount "SELECT coalesce(str(entry_meta('iban')), payee) AS counterparty,
     sum(position) AS total, count(position) AS n, first(payee) AS payee, first(narration) AS example
     WHERE account ~ 'Uncategorized' GROUP BY counterparty ORDER BY abs(sum(number)) DESC"
   ```
   No rows: report that nothing is uncategorized and stop. Otherwise read the transactions of each
   group (`WHERE entry_meta('iban') = '…'` or `payee = '…'`) before deciding.
2. Categorize what is clear from the text (a shop, a utility, a known client). For each group that is
   not clear, ask the user one short question with the date, amount, and text. Batch questions in a
   numbered list; accept "I don't know" and leave that group uncategorized.
   When no account in `accounts.beancount` fits a group, propose a new one, and list the proposed
   accounts with the questions so the user can rename or merge them. See "New accounts" below.
3. Write one rule per answer in the matching section of `rules.beancount`, following its header and the
   rule gotchas below. Put what the user explained into the rule's comment: the comment is the memory
   for the next session.
4. A transaction is often not an expense:
   - own account → add an `open` with `iban` to `accounts.beancount` (it becomes a transfer)
   - property, loans given or taken, funds → the `Assets:` or `Liabilities:` account
   - money from a partner who shares the assets → their `Equity:` account
5. Run `uv run kingsmint reimport` and `uv run kingsmint check`. Diff the ledger (`jj diff --stat` or `git diff --stat`) and spot-check
   that each new rule moved only the intended transactions; a rule that also caught others is too broad.
6. Commit, naming the categories that changed.

## New accounts

The tree grows from the user's transactions; there is no default tree.

- Name: `Expenses:<Area>:<Item>` (`Expenses:Food:Groceries`, `Expenses:Housing:Energy`) or
  `Income:<Area>`, at most 3 levels. Reuse an existing `<Area>` when one fits; English, ASCII.
- An account is for a kind of spending the user wants to see, not for one payee: a new shop goes
  into an existing account.
- Add the `open` next to its siblings, dated `2000-01-01`. Give every expense account `need`, and
  `cut` when `need` is flexible or unknown, as the comment in `accounts.beancount` defines.
- Taxes the user pays go to `Expenses:Taxes:<Kind>`; a company's costs to `Expenses:Business:<Item>`
  with `need: "income-linked"`: they stop when the company stops.

## Rule gotchas

- Backslashes are doubled inside Beancount strings: `"\\bBP\\b"`.
- Wrap short words in `\\b`: `hotovost` matched "Bezhotovostná", `voda` matched a surname.
- First match wins in file order, not date order. Specific rules go above general ones, such as a
  fallback for all payments to the state treasury.
- Match a counterparty by IBAN when it has one; an amount match is a last resort.

Done when every account the rules name is open and every group from step 1 has a rule or an answer from the user that leaves it uncategorized.
