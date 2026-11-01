# Kingsmint

Personal and one-person-company accounting with Beancount and Fava, in the Claude app.

## Install

Install two files from the [latest release](https://github.com/kingsmint/kingsmint/releases/latest):

1. `kingsmint.plugin`, the skills: **Customize > Plugins > Add > Upload plugin**. It syncs to your other
   computers.
2. `kingsmint.mcpb`, the server that runs the accounting on your computer: drag it into **Settings >
   Extensions** on each computer; extensions do not sync. The first start takes a minute or two: Claude
   downloads Python and the packages.

## Use it

Start a chat and ask Claude to set up your accounting. It guides you: it creates a folder, tells you to
connect it to the chat and to put your bank statements into it, and checks each file. Claude reads the statements, proposes the accounts, imports the transactions, asks you
about the ones it cannot categorize, and writes the answers as rules. Ask it to open Fava to browse the
ledger. Every change is saved as a version; ask Claude to undo one, or to show the versions.

After the setup, create a project (**Projects > New**), connect the ledger folder to it, and start a new
chat in the project for each task: "import" each month, a question about your money, "open Fava". The
ledger remembers what Claude learned (rules, notes about your accounts) in its files, so a new chat
continues where the last one stopped; one long chat only gets slower.

A ledger made with Claude Code works as it is: connect its folder, and Claude continues with it. Use it
from one app only, or from a copy (`git clone`): the extension saves versions with its own git.

The folder must be on your computer's disk: Claude does not accept network folders. On Windows in a
virtual machine, folders such as Documents may point to the host's disk; use a folder like
`C:\Users\<you>\Ledger`.

Supported statements: VÚB, Tatra banka, Fio banka, and Interactive Brokers. For another bank, Claude
writes a parser into the folder's `banks/`, and offers to share it with other users.

## Data

The ledger and the statements stay in the folder on your computer. Claude reads the transactions it needs
to answer you, as in any conversation. Fava runs on your computer and is reachable only from it.
