---
name: setup
description: Set up a new kingsmint ledger from bank statements in the Claude app. Use when the user wants to start their accounting, create a ledger, or has statements but no ledger yet.
---

> **In the Claude app**: the plugin's kingsmint server runs the commands on the user's computer through the `kingsmint_*` tools. Edit files directly in the connected folder. The first `kingsmint_*` call needs `ledger_dir`: the connected folder's path on the user's computer (not the /sessions/... sandbox path); later calls remember it. If you do not know that path, ask the user. If the tools are missing, the session does not run on the user's computer: tell the user to connect the ledger folder to the chat.

Use the language the user writes in for every message.

1. The ledger folder must be connected to this chat, . It must be empty, or hold only `inbox/` with statements.
2. No statements in `inbox/`: ask the user to download their statements into `inbox/`, as far back as each bank allows, for every account (personal and company, also closed ones), and to say when they are done. Ask nothing else.
3. Call `kingsmint_scan`. Propose, in one message for the user to confirm or correct:
   - The accounts, as "Accounts from statements" in the `import` skill describes, as a table: account, IBAN, holder, currency, period.
   - The title: the personal holder's name as people write it, without degrees and capitals (`ING. JÁN NOVÁK` and `Novák Ján, Ing.` are `Ján Novák`).
   - The main currency: the currency of most accounts.
   - The locale for Fava number formatting, from the IBAN country: `SK` is `sk_SK`, `CZ` is `cs_CZ`, `DE` is `de_DE`; `en_US` when unclear.
4. After the user confirms: call `kingsmint_new_ledger` with the title, currency, locale, and the user's language (in English, `Slovak`) and its code (`sk`). Then add one `open` per account to `accounts.beancount`, with its `iban` or `ibkr` and the holder as a comment; a broker also gets the four investment accounts from the commented example. Remove the commented examples.
5. Run the `import` skill, then the `categorize` skill.

Done when `kingsmint_check` prints nothing but a Transit FAIL that the user was told about, and the import has run.
