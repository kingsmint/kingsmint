# Changelog

Changes a user notices, newest first. A release takes its notes from the section of its version. Under
`### Ledger`, a version lists what to change in a ledger made with an older version, and why; `kingsmint
upgrade` shows these to the agent, which applies them with the owner. Ships in the package: the newest version
here is the installed version.

## 0.1.7

- `reimport` keeps what you change in a transaction in `ledger/`: its account or a split, narration, tags,
  metadata such as `note:`, and comments. Each transaction gets an `id` (its account, date, amount and order
  that day), and `.kingsmint/base/` keeps what kingsmint wrote last time, to tell your edits from new rules.
  When both changed the same part, your edit stays and `reimport` says so. An edited transaction that a new
  import no longer writes goes to `.kingsmint/orphans.beancount`, and `check` fails until it is resolved.
- One transaction is categorized by editing it, not by a rule; the categorize skill does this.
  `Expenses:Uncategorized:Unidentified` and `Income:Uncategorized:Unidentified` hold what you could not
  explain, so Claude does not ask about it again.
- `check` fails when two statements hold the same movements (overlapping periods), naming both files.
- `kingsmint rules` lists transactions whose postings you edited and where a rule now says another account;
  `kingsmint reset ID` gives one back the postings and flag kingsmint wrote, so the rules apply again.
- A ledger runs the kingsmint release that matches the plugin: the import and categorize skills pin it with
  `uv add … --tag v<version>` when the plugin is newer.
- `reimport` stops before it deletes anything when it cannot read a file in `ledger/`, and `check` fails on
  it, naming the line; a comment after a metadata value (`key: "x" ; text`) is such a line: move the comment
  to its own line.

### Ledger

- Add after `2000-01-01 open Income:Uncategorized` in `accounts.beancount`:
  `2000-01-01 open Income:Uncategorized:Unidentified`, and after `Expenses:Uncategorized` (with its `need`):
  `2000-01-01 open Expenses:Uncategorized:Unidentified` with `need: "unknown"`. Then turn each comment under
  the "Unknown" heading at the end of `rules.beancount` into a rule for that counterparty to
  `Expenses:Uncategorized:Unidentified` (or `Income:…`), keeping the comment above it, and delete the heading.
  Why: the categorize skill no longer reads that heading; the account keeps these out of its list.
- In `CLAUDE.md`, replace the invariant that starts with "`ledger/` is generated" by the one in the kingsmint
  template (`template/CLAUDE.md`). Why: edits to transactions in `ledger/` now survive `reimport`.
- `uv run kingsmint upgrade --done` reimports the statements: every transaction gets an `id` line and the first
  line of each generated file changes. Check that nothing else changed in `ledger/` beyond the rules of the steps
  above, then commit, including the new `.kingsmint/` folder. Why: the ids and `.kingsmint/base/` make later edits
  survive; `check` fails until then.
- Optional, after `upgrade --done`: move rules for one transaction into the transaction. A rule is one when it is
  dated on the day of its only transaction and matches an exact amount. Delete these rules, run
  `uv run kingsmint reimport` once, then set each rule's account in its transaction and move the rule's own comment
  into its `note:` (see "Editing one transaction" in the categorize skill). Leave other rules. Why: fewer rules, and the
  explanation shows in Fava next to the transaction.

## 0.1.6

- Cash payments: `cash.beancount` holds the cash payments you name, each moved from `Expenses:Cash` to its
  category. `reimport` does not touch it, and the categorize skill writes there. A receipt in
  `documents/Expenses/Cash/` links to the entry.
- `reimport` skips a file it cannot read (a damaged PDF, a receipt) with `FAIL`; before, it stopped and left
  `ledger/` half rebuilt. It no longer prints false `ledger error` lines.
- The categorize skill writes a rule for one transaction and a split by amounts; `property.beancount` names
  tax accruals and accounts without statements.

### Ledger

- Create `cash.beancount` as in the kingsmint template (`template/cash.beancount`: the header comment and the
  commented example), add `include "cash.beancount"` after `include "property.beancount"` in `main.beancount`,
  and in `CLAUDE.md` after "live in `property.beancount`" add "; cash payments the owner names live in
  `cash.beancount`". Why: hand-written cash entries need a file that `reimport` keeps and that Claude knows.

## 0.1.5

- Claude app: the install steps follow the new settings. Upload the plugin in **Settings > Customize > Plugins >
  Add > Upload plugin**, and install the extension by double-clicking `kingsmint.mcpb`; Settings has no
  Extensions page now.

## 0.1.4

- Transactions get the variable symbol (`vs`) and the payment reference (`ref`) from VÚB and Fio statements and
  from the Tatra reference, and rules match the reference. The add-bank skill fills both in a new parser.

### Ledger

- Run `uv run kingsmint reimport`, so that imported transactions get the `vs` and `ref` metadata. Then check
  `uv run kingsmint rules`: a rule that matches a VS can now match VÚB and Fio payments too. Why: rules can
  split one counterparty by its variable symbol or reference.

## 0.1.3

- Commit messages and saved versions say why a change was made, not only what changed; in the Claude app,
  `kingsmint_history` shows it, and `kingsmint_reimport` takes a message.
- Releases have notes from this file.
- `kingsmint upgrade` lists what to change in a ledger made with an older kingsmint; `kingsmint doctor` warns
  about it, and the import skill applies it with you. The ledger records its version in `.kingsmint-version`.

### Ledger

- `CLAUDE.md`, under Invariants, after the line about `check` and commit: add "A commit message says what
  changed in the first line, and in the body why: what the user said, which statement or transaction showed
  it, what was wrong before, and what was checked. Later sessions read the history (`jj log`, `git log`) to
  learn why the ledger looks as it does." Why: the history then explains the ledger.

## 0.1.2

- Claude app: after the setup, Claude tells you to create a project with the ledger folder and to start a new
  chat in it for each task.
- README: how to continue a ledger made with Claude Code in the Claude app.

## 0.1.1

- Claude app: the plugin is `kingsmint.plugin`; Safari unpacked `kingsmint.zip` after the download.
- README: install the Claude Code plugin with `claude plugin marketplace add kingsmint/kingsmint`.
- Tests pass on Windows: LF line endings in the checkout, `/` in import messages.

## 0.1.0

- First release: the Claude Code plugin, and for the Claude app the plugin with the skills and the
  `kingsmint.mcpb` extension, which runs kingsmint on your computer.
- Guided setup in the Claude app, versions with undo, and parsers for new banks in the ledger's `banks/`.
- Banks: VÚB, Tatra banka, Fio banka, Interactive Brokers.
