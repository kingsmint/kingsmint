# Kingsmint

*The king's mint*: where the crown's money was made and counted, for centuries.

Personal accounting with [Beancount](https://github.com/beancount/beancount) and
[Fava](https://github.com/beancount/fava), run by [Claude Code](https://claude.com/claude-code).
For developers who want one view of their personal money and their one-person company.

- Download bank statements into `inbox/`; `kingsmint import` parses them, checks that each one
  reconciles (opening balance + transactions = closing balance), categorizes the transactions, and
  archives the files.
- Categorization rules are Beancount `custom "rule"` directives, so the whole setup stays in Beancount.
- Claude Code skills import statements, ask you about unknown transactions and write rules,
  explain changes in net profit, and add parsers for new banks.
- No fixed chart of accounts: income and expense accounts are created from your own transactions.
- Local first: your statements and ledger stay in a private repository on your computer.

## Supported statements

| Bank | Format |
|---|---|
| VÚB (Slovakia) | monthly or yearly PDF, account history CSV |
| Tatra banka (Slovakia) | monthly PDF (old and 2025 layouts), account history CSV |
| Fio banka (Slovakia, Czechia) | monthly PDF |
| Interactive Brokers, also through Lynx | activity statement CSV |

Other banks: ask Claude to add one from a sample statement (`add-bank` skill).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and [Claude Code](https://claude.com/claude-code). uv installs Python
and all packages into `.venv/` of the ledger; `/kingsmint:setup` installs uv when it is missing.
Works on macOS, Linux, and Windows.

```
claude plugin marketplace add <path or git URL of this repository>
claude plugin install kingsmint@kingsmint
```

Then, in an empty folder, start Claude Code and run `/kingsmint:setup`. It asks about your banks,
company, and household, and creates your ledger repository from `template/`.

## Commands (in the ledger repository)

| Command | Does |
|---|---|
| `uv run kingsmint import` | import new files from `inbox/` |
| `uv run kingsmint reimport` | rebuild `ledger/` from `documents/` after changing rules |
| `uv run kingsmint check` | validate the ledger, and that each transfer between own accounts has both sides |
| `uv run kingsmint coverage` | the periods each account's statements cover, and the missing ones |
| `uv run kingsmint fava` | open Fava on http://localhost:5050 |
| `uv run kingsmint rates` | refresh month-end USD/EUR rates from the ECB |
| `uv run kingsmint doctor` | check the tools and the ledger files |

## Conventions

Accounts in your ledger tell the importer what they are:

```
2000-01-01 open Assets:Me:Bank:Current EUR
  iban: "SK..."                 ; statements with this IBAN belong here; transfers to it are internal
  statements_until: 2025-12-31  ; optional: after this date, transfers to it go through rules
2000-01-01 open Assets:Me:Broker:Cash
  ibkr: "U1234567"              ; IBKR account number; securities go to Assets:Me:Broker:Securities
```

Rules (`rules.beancount`):

```
2000-01-01 custom "rule" "REGEX" Account [Account share ...]
```

The regex is matched against `payee | narration | counterparty IBAN | amount`. The first matching
rule in file order wins; the date is the first day the rule applies.

## Privacy

- Your statements and ledger stay on your computer, in a repository that `/kingsmint:setup` creates
  without a remote. Keep it private: its history contains every statement.
- Kingsmint has no server and collects nothing. Network access: `uv` downloads packages, and
  `kingsmint rates` downloads exchange rates from the ECB.
- Claude Code sends what Claude reads (statements, ledger files, query results) to Anthropic as part
  of the conversation, under the terms of your Claude account.
- Fava listens on localhost only. To open it from your phone, use a private network (for example
  `tailscale serve`), never a public URL.

## License

MIT
