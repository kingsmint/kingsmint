---
name: import
description: Import bank and broker statements from inbox/ into the ledger. Use when the user adds statements, asks to import, or asks which statements are missing.
---

# Import statements

1. List `inbox/`. Remove exact duplicates (same checksum, or the same text from `kingsmint.pdf.pdf_text`) before importing.
2. Run `uv run kingsmint import`. Every file ends on one line:
   - `ok`: imported and archived to `documents/`.
   - `skip … exists`: the month is already imported. Compare the two statements; when the new one is
     the better source (full month, newer layout), rerun with `--force`.
   - `skip … unknown bank`: no parser matches. Use the `add-bank` skill.
   - `FAIL … sum`: the parser misread a row. Fix the parser with the `add-bank` skill.
   - `FAIL … no account with iban`: add the IBAN as `iban` metadata to the matching account in
     `accounts.beancount` (same bank and owner, no IBAN yet), or ask the user what the new account is
     and add an `open`. Import again.
3. Run `uv run kingsmint check`. A failing `balance` usually means a missing statement month; find the gap.
   On the account's first statement it means the account had money before the oldest statement: add
   `<open date> pad <account> Equity:Opening-Balances` under its `open`.
4. Report coverage: for each account in `accounts.beancount` with `iban`, the first and last imported
   month and every missing month in between. Missing months are what the user must download next.
5. Run the `categorize` skill on the new transactions.
6. Commit: `Import <banks> <months>`.

Done when every inbox file is `ok` or explained to the user, the check is clean, and the coverage gaps are reported.
