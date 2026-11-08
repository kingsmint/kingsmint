---
name: categorize
description: Categorize transactions: rules in rules.beancount for recurring counterparties, edits in ledger/ for one transaction. Use for Uncategorized transactions, a wrong category, or a new payee.
---

# Categorize

Write every message to the user, also short progress notes, in the language that `CLAUDE.md` names,
or else in the language the user writes in.

0. Do step 0 of the import skill first: a ledger on an older kingsmint loses edits to transactions.
1. List the uncategorized transactions, grouped by counterparty (IBAN, else payee), largest first.
   `amount` is what the account received (negative: paid), `account` is the bank account:
   ```
   uv run bean-query -q main.beancount "SELECT coalesce(str(entry_meta('iban')), payee) AS counterparty,
     -sum(number) AS amount, currency, count(position) AS n, min(date) AS first, max(date) AS last,
     first(other_accounts) AS account, first(payee) AS payee, first(narration) AS example
     WHERE account ~ '^(Expenses|Income):Uncategorized$' GROUP BY counterparty, currency ORDER BY abs(sum(number)) DESC"
   ```
   `Uncategorized:Unidentified` holds what the user already could not explain; it is not in this list.
   No rows left: report that nothing is uncategorized and stop. Otherwise read the transactions of a
   group (`WHERE entry_meta('iban') = '…'` or `payee = '…'`) when the example is not enough.
2. Categorize what is clear from the text (a shop, a utility, a known client). For each group that is
   not clear, ask the user one short question with the date, amount, and text. Batch questions in a
   numbered list. Accept "I don't know": the group stays uncategorized, and step 3 records it.
   When no account in `accounts.beancount` fits a group, propose a new one, and list the proposed
   accounts with the questions so the user can rename or merge them. See "New accounts" below.
3. Record each answer where it belongs:
   - A counterparty that comes again (a shop, a utility, a client, a salary, a yearly insurance): one rule
     in the matching section of `rules.beancount`, following its header and the rule gotchas below. Put
     what the user explained into the rule's comment: the comment is the memory for the next session.
   - One transaction (a refund, a gift, a one-time purchase, a payment the general rule gets wrong): an
     edit of that transaction in `ledger/`, as "Editing one transaction" below shows. What the user
     explained goes into its `note:`.
   - "I don't know": the same choice, with the account `Expenses:Uncategorized:Unidentified` (or
     `Income:Uncategorized:Unidentified`): a rule with the comment `; asked <today>, unknown` for a
     counterparty that comes again, else an edit with `note: "asked <today>, unknown"`.
   A question nobody answered (no user, the user skipped it) is not an answer: record nothing, and
   the group comes back in the next run.
4. A transaction is often not an expense:
   - own account → add an `open` with `iban` to `accounts.beancount` (it becomes a transfer)
   - property, loans given or taken, funds → `Assets:Me:Property:<Place>`, `Assets:Me:Loans`,
     `Liabilities:<Bank>:Mortgage`, `Assets:Me:Investments:<Fund>`. What no statement shows (purchase
     price, assessed value, a loan before the first statement, a closed fund's gain) goes to
     `property.beancount`, as its examples show.
   - money from a partner who shares the assets → their `Equity:` account
   - a payment in cash that the user names (what, when, how much) → an entry in `cash.beancount`
     that moves the amount from `Expenses:Cash` to its category, as its example shows. `ledger/` holds
     only what the statements show: an entry added there by hand moves to `.kingsmint/orphans.beancount`
     on the next `reimport`.

   Facts about the household and the company come from the transactions, not from an interview. Ask
   about one in the same numbered list when a group shows it, and record the answer as a comment in
   `accounts.beancount`: regular money from a person with the user's surname or a joint holder (a
   partner who shares the assets?), payments to the tax office for VAT (is the company VAT-registered?),
   monthly payments to an accounting firm (does an accountant keep the official books?), shops or
   restaurants paid from a company account (does the company pay personal costs?).
5. Run `uv run kingsmint rules`: it shows, by rule, which transactions the edited rules would move, from
   which account to which, with examples. Fix a rule that moves more than intended before you go on.
   Then run `uv run kingsmint reimport` and `uv run kingsmint check`; it must print nothing that was not
   there before your change (run `check` once before your first edit to know) (a Transit `FAIL` about a missing statement can stay). Diff the ledger (`jj diff --stat ledger/` or `git diff --stat ledger/`; `.kingsmint/` repeats it) and spot-check
   that each new rule moved only the intended transactions; a rule that also caught others is too broad.
   `kingsmint rules` also lists transactions whose postings were edited by hand and where a rule now says
   another account: ask the user which one is right; to take the rule, run the `reset` it prints.
   `reimport` prints a `conflict` line when a hand edit and kingsmint changed the same part; it keeps the
   edit. Ask the user about each one the same way.
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
  with `need: "income-linked"`: they stop when the company stops. Bank fees stay in `Expenses:Bank:Fees`
  for every account: the importer posts fees there, and the paying account shows whose they are.

## Editing one transaction

Find its file and line by date and amount, then change it in place:
```
uv run bean-query -q main.beancount "SELECT date, filename, lineno, entry_meta('id') AS id, account, number
  WHERE date = 2025-03-04 AND number = -99.00"
```
`reimport` keeps the account and the postings, the flag, payee, narration, tags and links, metadata, and
comments:

```
2025-03-04 * "City Museum" "Annual pass" #family
  id: "km-3f2a9c01b7e4"
  note: "annual pass for the family, paid once a year"
  document: "2025-03-01_2025-03-31.SK3112000000001987654321.pdf"
  Assets:Me:Bank:Current  -99.00 EUR
  Expenses:Leisure:Culture
```

- Keep the `id` and the bank account posting as kingsmint wrote them: the id ties the edit to the
  statement row. Set the flag to `*` once the transaction has its category.
- A split: one posting per category with its amount; one posting may stay without an amount.
- Postings edited by hand stay when the rules change later; `kingsmint rules` lists those where a rule
  now says another account.
- Put a comment on its own line or after a posting; `check` fails on a comment after a metadata value
  (`key: "x" ; text`), which `reimport` cannot read.
- `uv run kingsmint reset <id>` gives a transaction back the postings and flag kingsmint wrote; notes, tags
  and narration stay. Then `reimport` applies the current rules.

## Rule gotchas

- Backslashes are doubled inside Beancount strings: `"\\bBP\\b"`.
- Wrap short words in `\\b`: `hotovost` matched "Bezhotovostná", `voda` matched a surname.
- First match wins in file order, not date order. Specific rules go above general ones, such as a
  fallback for all payments to the state treasury.
- Match a counterparty by IBAN when it has one; an amount match is a last resort.
- A rule matches `payee | narration | iban | amount`, so `^` anchors the payee. To match the start of
  the narration, use `\\| text`; when the payee is empty, the text starts with `| `.
- A rule also matches `VS<variable symbol>` when the statement shows one (the `vs` metadata). Use it
  to split one counterparty, such as one utility IBAN for electricity and gas: `"^VS1234567890$"`.
  Do not match a variable symbol that also appears in unrelated payments, such as the owner's birth
  number or a customer number; match the IBAN.
- A rule also matches the payment reference (the `ref` metadata), such as a contract number that the
  counterparty puts into every payment: `"^RF18 5390"`.
- A short name catches other shops (`HM` caught "HM TESCO" and ATM rows). Anchor it or add the city,
  and read every example in `uv run kingsmint rules` before reimport.
- A recurring payment split by shares: the share is part / total with 8 decimals, e.g. 90 of 250:
  `... Expenses:Sport Expenses:Kids:Education 0.36`. Amounts are rounded to cents. Split one
  transaction by editing it instead.
- Payments to a credit card with no statements (minimum payments, repayments) go to one
  `Expenses:CreditCard` account, matched by the card account's IBAN.

Done when every account the rules and edits name is open and every group from step 1 has a rule, edited transactions, or no answer from the user yet.
