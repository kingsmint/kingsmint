# Kingsmint

Personal and one-person-company accounting with Beancount and Fava, in the Claude app.

## Use it

Connect an empty folder with your bank statements in `inbox/` to a chat, and ask Claude to set up your
accounting. Claude reads the statements, proposes the accounts, imports the transactions, asks you about
the ones it cannot categorize, and writes the answers as rules. Ask it to open Fava to browse the ledger.

The plugin's server runs on your computer, so the chat must have the ledger folder connected (a session
that runs on your computer). Supported statements: VÚB, Tatra banka, Fio banka, and Interactive Brokers.

## Data

The ledger and the statements stay in the folder on your computer. Claude reads the transactions it needs
to answer you, as in any conversation. Fava runs on your computer and is reachable only from it.
