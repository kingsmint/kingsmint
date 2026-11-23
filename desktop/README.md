# Kingsmint

Ask Claude about your money: the Claude app reads your Kingsmint ledger (Beancount) on your computer.

## Install

Install two files from the [latest release](https://github.com/kingsmint/kingsmint/releases/latest):

1. `kingsmint.plugin`, the skill that explains your money: **Plugins** in the sidebar, then **Add > Upload plugin**. It syncs to your other
   computers.
2. `kingsmint.mcpb`, the server that reads the ledger on your computer: double-click it on each
   computer, and Claude asks to install it; extensions do not sync. The first start takes a minute or two: Claude
   downloads Python and the packages.

## Use it

Keep the accounting in the Kingsmint app: it imports your statements, and an agent categorizes the transactions with
you; every change is a version you can undo. The Claude app is where you ask about your money from any chat, for
example while you plan a holiday or answer your accountant: "how much did we spend on energy last year?", "what is
our runway without income?". Claude answers with numbers from the ledger and can open Fava to browse it.

The extension only reads the ledger. It finds the ledger the Kingsmint app opened last; set another one in the
extension's settings. Fava opens read-only.

The folder must be on your computer's disk: Claude does not accept network folders.

## Data

The ledger and the statements stay in the folder on your computer. Claude reads the transactions it needs
to answer you, as in any conversation. Fava runs on your computer and is reachable only from it.
