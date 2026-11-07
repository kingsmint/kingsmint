---
name: setup
description: Set up kingsmint accounting from bank statements in the Claude app, guiding a new user step by step. Use when the user wants to start their accounting, track their money, spending or finances, create a ledger, or asks what kingsmint is or how to begin.
---

> **In the Claude app**: the kingsmint extension runs the commands on the user's computer through the `kingsmint_*` tools. Edit files directly in the connected folder. The `kingsmint_*` tools need `ledger_dir`, the folder's path on the user's computer (not the /sessions/... sandbox path), until one call remembers it; `kingsmint_start` remembers the folder it creates.

Use the language the user writes in for every message. The user may know nothing about accounting,
Beancount, or this plugin: guide them. Start each message of steps 1-4 with the step ("Step 2 of 5"),
and end it with the one thing the user does next. Never ask for what a tool or the statements can show.

0. Check: the `kingsmint_*` tools are missing → tell the user to install the kingsmint extension
   (double-click `kingsmint.mcpb`), and to start a new chat; stop. A connected folder that
   already holds `main.beancount` is a ledger: use the `import` skill instead.
1. Introduce kingsmint in three short sentences: it builds a ledger of all their accounts, personal and
   company, from the statements their banks give them, and shows it in Fava, a web page on their computer;
   the statements and the ledger stay on their computer; setup takes about 15 minutes. Call
   `kingsmint_banks` and list the supported banks by name and format in plain words. Ask which banks and
   brokers they use. A bank not in the list is fine: say that you will teach kingsmint its statements.
2. No folder connected: call `kingsmint_start`. It opens an `inbox` folder on their screen. Tell them to
   connect that folder to this chat (the folder button under the message box), to download from each bank
   the statements of every account, personal and company, also closed ones, as far back as the bank allows,
   and to drop them into `inbox`. PDF statements are best; some banks also give a CSV account history.
   Ask them to say "done". A folder is connected: tell them to put the statements into its `inbox/`.
3. Call `kingsmint_scan`, then report per file in plain words: which bank, account, and period, or what
   is wrong. Unknown bank: use the `add-bank` skill, then scan again. Several months of an account with a
   month missing: ask for it now. Keep going until every file is recognized, or the user says to leave one out.
4. Propose, in one message for the user to confirm or correct:
   - The accounts, as "Accounts from statements" in the `import` skill describes, as a table: account,
     bank, holder, currency, period. A company's accounts belong in the same ledger, as `Assets:Co:…`;
     never propose to leave them out. An account history CSV has no holder: list it as "after the PDFs",
     and derive its owner and kind from the transfers after importing the PDFs, as the `import` skill
     describes; do not ask the user about it now.
   - The title: the personal holder's name as people write it, without degrees and capitals
     (`ING. JÁN NOVÁK` and `Novák Ján, Ing.` are `Ján Novák`).
   - The main currency: the currency of most accounts.
   - The locale for Fava number formatting, from the IBAN country: `SK` is `sk_SK`, `CZ` is `cs_CZ`,
     `DE` is `de_DE`; `en_US` when unclear.
5. After the user confirms: call `kingsmint_new_ledger` with the title, currency, locale, and the user's
   language (in English, `Slovak`) and its code (`sk`). Add one `open` per account to `accounts.beancount`,
   with its `iban` or `ibkr` and the holder as a comment; a broker also gets the four investment accounts
   from the commented example. Remove the commented examples. Run the `import` skill, then the
   `categorize` skill. Then call `kingsmint_fava`.

End with what comes next. First, one step to do now: create a project (Projects > New, e.g. "Accounting"),
connect the ledger folder to it, and from now on start a new chat in that project for each task; the ledger
files remember what this chat learned, and one long chat only gets slower. Then, in three lines: each month,
drop the new statements into `inbox` and say "import"; ask anything about their money; say "undo" to go back
to an earlier version.

Done when `kingsmint_check` prints nothing but a Transit FAIL that the user was told about, the import
has run, and Fava is open.
