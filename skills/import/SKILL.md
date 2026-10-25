---
name: import
description: Import bank and broker statements from inbox/ into the ledger. Use when the user adds statements, asks to import, or asks which statements are missing.
---

# Import statements

1. List `inbox/`. Remove exact duplicates (same checksum, or the same text from `kingsmint.pdf.pdf_text`) before importing.
2. Run `uv run kingsmint import`. `nothing to import`: tell the user where to put statements and stop.
   Otherwise every file ends on one line:
   - `ok`: imported and archived to `documents/`.
   - `skip … exists`: the month is already imported. Compare the two statements; when the new one is
     the better source (full month, newer layout), rerun with `--force`.
   - `skip … unknown bank`: no parser matches. Use the `add-bank` skill.
   - `FAIL … sum`: the parser misread a row. Fix the parser with the `add-bank` skill.
   - `FAIL … no account with iban` (PDF) or `FAIL … must start with an IBAN` (CSV, named after the
     account's IBAN): add the IBAN as `iban` metadata to the matching account in
     `accounts.beancount` (same bank and owner, no IBAN yet), or ask the user what the new account is
     and add an `open`. Import again.
3. Run `uv run kingsmint check`. A failing `balance` usually means a missing statement month; find the gap.
   On the account's first statement it means the account had money before the oldest statement: add
   `<open date> pad <account> Equity:Opening-Balances` under its `open`.
   `FAIL Assets:Transit`: a transfer between own accounts has one side only, because the other
   account's statement for that period is missing. Find which one with step 4. When an account has
   no more statements to import (closed, or history ends), add `statements_until` to its `open`.
4. Run `uv run kingsmint coverage` and report it: per account, the first and last imported day,
   every `missing` period (between statements, and from the last one to the end of last month), and
   the accounts `never imported`. These are what the user must download next.
5. Run the `categorize` skill on the new transactions.
6. Commit: `Import <banks> <months>`.

Done when every inbox file is `ok` or explained to the user, the check prints nothing (or only a
Transit `FAIL` whose missing statement the user was told to download), and the coverage gaps are reported.
