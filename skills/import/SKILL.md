---
name: import
description: Import bank and broker statements from inbox/ into the ledger. Use when the user adds statements, asks to import, or asks which statements are missing.
---

# Import statements

1. List `inbox/`. Remove exact duplicates (same checksum, or the same text from `kingsmint.pdf.pdf_text`) before importing.
2. Run `uv run kingsmint import`. `nothing to import`: tell the user where to put statements and stop.
   Otherwise every file ends on one line:
   - `ok`: imported and archived to `documents/<account>/` as `<start>_<end>.<IBAN>`.
   - `FAIL … another statement for the same account and period`: two different files for one period.
     Compare them; delete the worse one (from `inbox/` or `documents/`) and import again.
   - `skip … exists`: the month is already imported. Compare the two statements; when the new one is
     the better source (full month, newer layout), rerun with `--force`.
   - `skip … unknown bank`: no parser matches. Use the `add-bank` skill.
   - `FAIL … sum`: the parser misread a row. Fix the parser with the `add-bank` skill.
   - `FAIL … no account with iban` (PDF), `FAIL … must start with an IBAN` (CSV), or `no account with
     ibkr` (broker): a new account. Run `uv run kingsmint scan`, propose the account as "Accounts from
     statements" below describes, and add its `open` when the user confirms. Import again.
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

## Accounts from statements

`uv run kingsmint scan` prints one line per file: bank, IBAN (or broker account), currency, period,
`holder`, `type`, and the account it belongs to, or `NEW`. Derive each new account from it:

- Owner: `Assets:Co` when the holder is a company (`s.r.o.`, `a.s.`, `spol.`, `GmbH`, `Ltd`, `Inc`, ...),
  `Assets:Me` when it is a person. A joint holder ("A and B") is `Assets:Me`; the other person is a
  partner who shares the assets: propose `Equity:<First name>` for the money they send.
- Name: `Assets:<Me|Co>:Bank:<Bank>:<Kind>`. `<Bank>` is the short name people use, in ASCII (`VUB`,
  `Tatra`, `Fio`). `<Kind>` comes from `type` and the currency: `Current` for a current account,
  `Savings` for a savings account, the currency code (`USD`) for a second currency at the same bank and
  owner. A broker is `Assets:<Me|Co>:Investments:<Broker>:Cash` with `ibkr` metadata, plus
  `:Securities "FIFO"` next to it; `<Broker>` is `IBKR` or the introducing broker such as `Lynx`.
- An account history CSV has no holder. Import the PDFs first, then look for transfers to its IBAN:
  `uv run bean-query -q main.beancount "SELECT date, account, payee, narration, position WHERE entry_meta('iban') = '<IBAN>'"`.
  The user's own name or "Sporenie" from their account shows the owner and the kind.

Ask the user, in one numbered list, only when the statements cannot show it: no holder and no
transfers, two accounts that would get the same name (ask for a short name), or a type that is neither
current nor savings. Write what they said as a comment next to the `open`.

Done when every inbox file is `ok` or explained to the user, the check prints nothing (or only a
Transit `FAIL` whose missing statement the user was told to download), and the coverage gaps are reported.
