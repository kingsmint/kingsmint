# Changelog

Changes a user notices, newest first. A release takes its notes from the section of its version.

## Unreleased

- Commit messages and saved versions say why a change was made, not only what changed; in the Claude app,
  `kingsmint_history` shows it, and `kingsmint_reimport` takes a message.
- Releases have notes from this file.

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
