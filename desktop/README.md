# Kingsmint

Personal and one-person-company accounting with Beancount and Fava, in the Claude app.

## Install

Install two files:

1. `kingsmint.zip`, the skills: **Customize > Plugins > Add > Upload plugin**. It syncs to your other
   computers.
2. `kingsmint.mcpb`, the server that runs the accounting on your computer: drag it into **Settings >
   Extensions** on each computer; extensions do not sync. The first start takes a minute or two: Claude
   downloads Python and the packages.

## Use it

Put your bank statements into `inbox/` in a new folder, connect the folder to a chat, and ask Claude to set
up your accounting. Claude reads the statements, proposes the accounts, imports the transactions, asks you
about the ones it cannot categorize, and writes the answers as rules. Ask it to open Fava to browse the
ledger. Every change is saved as a version; ask Claude to undo one, or to show the versions.

The folder must be on your computer's disk: Claude does not accept network folders. On Windows in a
virtual machine, folders such as Documents may point to the host's disk; use a folder like
`C:\Users\<you>\Ledger`.

Supported statements: VÚB, Tatra banka, Fio banka, and Interactive Brokers.

## Data

The ledger and the statements stay in the folder on your computer. Claude reads the transactions it needs
to answer you, as in any conversation. Fava runs on your computer and is reachable only from it.
