# Changelog

Changes a user notices, newest first. A release takes its notes from the section of its version. Under
`### Ledger`, a version lists what to change in a ledger made with an older version, and why; `kingsmint
upgrade` shows these to the agent, which applies them with the owner. Ships in the package: the newest version
here is the installed version.

## Unreleased

- The Kingsmint app enters a cash payment without the agent: **+ Cash payment** above the list of transactions, or ⌘N. Date,
  amount, category, payee and a receipt go to `cash.beancount`, where the payment moves from `Expenses:Cash` to its
  category; the receipt goes to `documents/Expenses/Cash/`. On a Mac, a right click in the receipt's field offers
  **Import from iPhone**: take a photo or scan the receipt with the phone. A photo is made smaller (about 2000 px), so
  the ledger's versions do not grow by megabytes. The overview shows the cash withdrawn in the month, the cash
  entered, and the rest that no one categorized.
- Tags in the Kingsmint app: add or remove a tag in a transaction's detail, or choose rows in the transactions with
  ⌘ or Shift click and tag them together. **Tags** in the overview shows each tag's total, count and dates; a tag
  opens the transactions filtered by it, over all its months. The transactions have a tag filter, a new period
  **All** (every month of the ledger), and what they moved by category under the chart; both fold away. A name such as "Záloha plot" becomes `#zaloha-plot`: Beancount takes no other
  characters in a tag. Tags in `ledger/` stay after `kingsmint reimport`; tags also work on `cash.beancount`.
- The agent tags the transactions you name ("tag the holiday from 1 to 14 July as #croatia-2026") after you
  confirm the list (the categorize skill).
- **Recurring payments** in the Kingsmint app's overview: what you pay every month, quarter or year. The app finds
  the payees paid regularly in the last 2 years and offers them as **Suggestions**; **Confirm** (or **Confirm all**)
  puts them among the confirmed ones, whose monthly total the overview shows, each with its next payment expected,
  and whether it is new, more expensive than usual, or ended. **Not recurring** (in a row's menu) moves a payee to
  **Hidden**, where **Bring back** returns it. **Add**, or **Recurring payment** in a transaction's detail, confirms
  a payee that was not found. The decisions are lines in `rules.beancount`. The month close of the explain skill
  names new and more expensive subscriptions.
- The Kingsmint app has budgets: a limit per expense category for a month, a quarter or a year (**Set budget** in a
  category's view, beside the category's average month of the last 12), and a limit for a tag with a start and an
  optional end date, such as the advances for a fence (paid 5 500 of 8 000, 2 500 left), with its payments. A tile
  in the overview counts the budgets within their limits and shows the three nearest to them; its detail shows each
  budget's spending, what is left, per day, and the periods before. Yellow from 75 % or when the spending runs ahead
  of the days, red over the limit. Fava shows the category budgets too. The month close names the budgets over or
  near their limit.
- A rule the Kingsmint app adds to `rules.beancount` goes in a paragraph of its own above the first rule: before, it
  could come between a comment and the rule the comment explains, or join the template's last comment.
- The Kingsmint app's settings have a theme, picked from cards that show it: Web Awesome's, Catppuccin, Rosé Pine,
  Gruvbox, Solarized, Everforest or Nord, each light and dark; and dark mode: as the system, light or dark. The
  theme also colors Fava and the terminals.

### Ledger

- Optional: in `rules.beancount`, under the payee rules, add the comment
  `; DATE custom "recurring" "Payee" "include" "monthly" (or "quarterly", "yearly"; or "ignore"): the owner confirmed`
  `; the payee's payments as recurring in the app (or not).`, so the agent knows what the lines the app writes mean.
- Create `budgets.beancount` as in the kingsmint template (its header comment), add `include "budgets.beancount"`
  after `include "cash.beancount"` in `main.beancount`, and add the template's paragraph "Budgets live in" to
  `CLAUDE.md`, before "Talk to the owner". Why: the app writes the budgets there, and the agent needs to know where
  they are.

## 0.2.5

- The Kingsmint app no longer flashes "Loading" when you go from one transaction to another: the detail keeps
  the transaction before until the next one comes.
- In the Claude app, Claude tells the version of the kingsmint extension when you ask which one runs, and answers
  with the extension's tools, not with the ledger's own kingsmint, which may be another version.
- The Kingsmint app offers to add Kingsmint to the Claude app, and to update it there when it is older: a button
  above the panels and in the settings. The Claude app then asks you to install it; no download from GitHub.
- The Kingsmint app upgrades a ledger itself when it opens it: `kingsmint upgrade --apply` makes the changes of the
  newer versions and the app saves them as a version, which you can undo in History. Only a change the program cannot
  make, for example in a text you rewrote, goes to the agent, with the banner above the panels. The changes of 0.1.9
  and 0.2.0 are made this way; optional suggestions, such as payee rules, stay with you.
- After the Kingsmint app updates itself, a ledger it made takes kingsmint of the app's new version when it opens;
  before, it stayed at the version it was made with. When the new version brings changes for the ledger, a banner
  above the panels offers to go through them with the agent, who applies only what you agree to.
- `kingsmint upgrade` names the template its changes refer to: the package has it now, so the agent no longer
  looks for it on GitHub.
- The Kingsmint app's charts are sharp and use the app's font, and a month on their axis shows the full year
  ("Oct 2025", not "Oct 25", which read as a day).
- The Kingsmint app's settings have **Check for updates**: it offers a newer version, or says that you have the newest.
- The Kingsmint app changes a transaction without Fava, in place: click its category (in its detail or in the
  list of transactions) and type a few letters of another; click its payee or note to change them. **Split over
  several categories** gives each part an amount. `kingsmint reimport` keeps these changes. After a new category,
  the app offers to move the counterparty's other transactions there too, with a rule in `rules.beancount`.
  A transaction changed by hand is marked so in its detail, with **Back to the rules**.
- A statement or a Fava page that the Kingsmint app's overview opened has **Back to the overview** above it.
- The Kingsmint app no longer shows Problems while `kingsmint import`, `reimport` or `reset` writes the ledger:
  they mark it with `.kingsmint/writing`, and the app checks the ledger when they finish.

## 0.2.4

- The Kingsmint app's rail has **Feedback**, above Settings: it opens an email to feedback@kingsmint.org in your mail app.

## 0.2.3

- The Kingsmint app updates itself: at start it asks whether to install a newer release, then restarts. The app of
  0.2.2 and older does not have this yet: install this version once from kingsmint.org.

## 0.2.2

- The Kingsmint app for Windows, x64 and ARM, is in each release: an installer not signed yet, so Windows
  SmartScreen asks before the first start.

## 0.2.1

- The Kingsmint app installs an agent: without one, a bar offers **Install Claude Code** and **Install Codex**, for a
  Claude or a ChatGPT subscription; the sidebar's "+" offers the one not installed yet. A terminal runs the agent's
  official installer, then the agent, which asks you to sign in. The app also finds agents in `~/.local/bin`, where
  both installers put them, when the shell's PATH does not have it.

## 0.2.0

- In the Kingsmint app, the agent and the shell are tabs of a sidebar on the right: pinned beside the panels,
  or floating over them until a click elsewhere; it widens over the panels, its edge drags its width, and ⌘J
  shows or hides it. The buttons that give the agent a task open it. The terminals of a saved layout move into it.
- The app's rail shows Reports once the ledger has a report.
- The app's rail opens the overview's Transactions, Where the money went and Runway, in the overview used last
  (⌘-click: in a new one beside). ⌘1-6 follow the rail: Inbox, Overview, Transactions, Where the money went,
  Runway, Fava; ⌘J shows or hides the agent. ⌘6 shows the Fava view used last again.
- The overview's ★ pins a view (an account, a report) on the app's rail, per ledger: a click opens it in the
  overview used last, ⌘7-9 the first three, right-click renames or unpins it; more than three go in a "…" menu.
  A pin of transactions is named by their payee or account, and each pin has the icon of its kind of view.
- The app's rail items move when dragged, and right-click hides one; "+" at the end of the rail shows them again or
  restores the default rail. The order is the app's, the same for every ledger.
- The Kingsmint app's icons come from one set, Lucide, in the same style everywhere; a button that gives a task
  to the agent has sparkles.
- The Kingsmint app has an **Overview**: five tiles for a month (cash flow, the top spending category, net worth,
  savings rate and runway), each compared with the month before, the 12-month average or the goal. A tile opens
  its detail (a trend, categories, accounts), and a category, a payee or a bank account its transactions in the
  app: filtered by account, payee and text, as a list by day or a table, with a running total or the balance,
  under a chart of the days against the month before, where a drag picks days. A transaction opens its detail:
  its postings and details, its statement, and the payee's payments in 12 months; Fava edits it. The runway shows
  what the baseline is made of, by need and account, the liquid money by account, and the runway without
  investments; its **Edit** changes which accounts are liquid
  money, and the need and cut of the spending, shows the runway with the new values before you save, writes them
  into `accounts.beancount` as a version, and undoes the save; **Discuss with the agent** asks the agent to propose
  these values, with your changes not saved yet, and to change the file only after you agree. An agent's link to an account opens its detail here, not
  in Fava. A group's split opens one more overview beside it, on the same view, with its own period; in a wide
  panel a transaction's detail opens beside the transactions. After a restart, the overview goes on where it was. It is the first
  page of a ledger, and shows after the first import. Its tables and charts, and those of Reports, take Fava's
  look and colors.
- The Kingsmint app has **Reports**: your own reports in `reports/*.toml` (a name, a BQL query and a view), each as
  a table, and a bar or line chart too. Ask the agent for one ("my monthly expenses by category"); it writes the
  file, and the report shows at once, also after the next import.
- The Claude app extension only reads the ledger: ask about your money from any chat (`kingsmint_query`,
  `check`, `coverage`, `history`, `fava`, which opens Fava read-only). Importing, categorizing and undoing
  changes move to the Kingsmint app, so the two never write the same ledger at once. The extension finds the
  ledger the Kingsmint app opened last; the plugin keeps only the `explain` skill.
- While the Kingsmint app prepares a ledger, it shows what uv downloads (Python and the ledger's libraries, tens of
  MB on the first start), and the output of uv when the preparation fails.
- A new ledger in the Kingsmint app takes kingsmint from the release's wheel, not with git, so it works on a Mac
  without the Command Line Tools; `kingsmint upgrade --done` pins such a ledger to the wheel of the kingsmint it
  runs, as it pins a git source to its tag. Each release has the wheel among its files.
- The Kingsmint app shows Fava, the inbox, the settings and each terminal in **panels**: drag a tab to put the
  agent beside Fava, below it or in its own group; a double click on a tab maximizes its group and back. A group's header splits it, as in Herdr: Fava opens a second view of the same page beside it, a
  terminal one more terminal with the same agent; "+" also opens another view of Fava. The
  app keeps the layout and Fava's page for each ledger. Fava runs in the app's own local server, which also
  loads the ledger again after a reimport, without touching `main.beancount`.
- In the Kingsmint app, links in a terminal work: a link to the ledger's Fava opens in the app's Fava, any other
  link in the browser. The agent links its tables to the Fava pages with the same numbers (skill `explain`).
- In the Kingsmint app, ⌘-click on a link in Fava opens the page beside it, in a split, and the same split again
  next time; a middle click still opens a new tab behind.
- The Kingsmint app and its Fava share one look: Web Awesome's design tokens give the colors and fonts of the app,
  its panels, terminals and Fava, light or dark as the system.
- The Kingsmint app in Slovak calls a ledger "pokladnica" (treasury), which a new user understands better than
  "ledger"; the start screen is more compact.
- The inbox in the Kingsmint app has × beside each file: it moves the file to the Trash.
- The sample ledger in the Kingsmint app is made again when its first start failed (for example in `uv sync`),
  instead of opening empty.
- On Windows and Linux, the Kingsmint app keeps no empty room for the macOS window buttons above the rail: the
  system draws the title bar there.
- In the Kingsmint app, a terminal of an agent ends when the agent exits; it no longer becomes a shell. A task
  button then starts the agent again, and never types the task into a shell, which would run parts of it.
- An undo in the Kingsmint app puts every statement it takes out of `documents/` back into `inbox/`: one whose name
  is taken there by another file gets a number (`statement-2.pdf`).
- The runway no longer counts property and loans given as liquid money when their accounts lack
  `liquid: "false"`: the saved query `Liquid money` leaves out `Assets:<Me|Co>:Property` and `Assets:<Me|Co>:Loans` by
  their name. The `categorize` skill marks an asset that is not money at hand with `liquid: "false"`.
- A payee rule gives one name to a merchant whose bank text changes from store to store
  (`2000-01-01 custom "payee" "^LIDL\\b" "Lidl"` in `rules.beancount`). Fava and queries then group
  its payments under one payee. The bank's text stays in the transaction's `bank_payee:`, and the category rules
  still match it. `kingsmint rules` shows the payees a rule would rename.

### Ledger

- In `CLAUDE.md`, after the list of commands, add the two sentences about `$KINGSMINT_FAVA_URL` from the template:
  in the Kingsmint app the agent then links to the app's Fava and does not start a second Fava.
- In `CLAUDE.md`, before "Talk to the owner", add the paragraph about `reports/*.toml` from the template: the agent
  then knows how to write a report that the Kingsmint app shows.
- In `main.beancount`, in the query `Liquid money`, add `AND account !~ '^Assets:(Me|Co):(Property|Loans)(:|$)'` after
  `WHERE account ~ '^Assets:(Me|Co):'`. Without it, property and loans given whose `open` lacks
  `liquid: "false"` count as liquid money, and the runway is too long. A `Loans` account deeper down, such as P2P
  lending at a broker, still counts. Also add `liquid: "false"` to the `open`
  of any other asset that is not money at hand.
- Optional: add payee rules to `rules.beancount` (ask the agent: "give my merchants one name"; the header of the
  section is in the template's `rules.beancount`), then run `uv run kingsmint reimport`. Without payee rules nothing
  changes. A payee you renamed by hand stays.

## 0.1.9

- Fava has a **Trends** report: expenses per account and year with the change against the year before, red
  for a rise and green for a fall, so a jump shows at a glance. The last year, when its statements end before
  December, is compared with the same days of the year before. A click on an amount opens the account's
  transactions of that period. Switches above the table show months instead of years (each against the same
  month a year before) or fewer account levels, and a slider hides the rows without a
  marked change of at least the chosen size in the newest period, or in the one whose heading you click.
- The `explain` skill does the **month close**: it checks that each account has its statement for the last
  month, imports and categorizes it, and sums up the month against the 12 months before it.
- `kingsmint runway` prints the liquid money, the monthly baseline and how many months the money covers, from
  the saved queries; the month close reports it.
- `kingsmint sample` fills a new ledger with three years of made-up statements, to try kingsmint before
  adding your own.
- `kingsmint skills` copies the skills (`import`, `categorize`, `explain`, `add-bank`) into the ledger's
  `.claude/skills/kingsmint-*`, from the kingsmint the ledger runs. Claude Code without the plugin, Codex and
  Cursor (through `AGENTS.md`) then follow the same steps.
- Claude app: the install steps follow the new layout: upload the plugin in **Plugins** in the sidebar,
  then **Add > Upload plugin**.

### Ledger

- In `main.beancount`, add the line `2000-01-01 custom "fava-extension" "kingsmint.fava"` with its comment
  from the template, below the other `fava-option` lines: it turns on the Trends report in Fava.
- Add `AGENTS.md` from the template: agents other than Claude Code read it, and it sends them to `CLAUDE.md`
  and the skills.
- Add to `.gitignore` the two lines below `# copies of kingsmint's skills` from the template: the copies come from
  kingsmint and the agent settings belong to one computer, so neither belongs in the ledger's versions.
- In `CLAUDE.md`, say where the skills come from as the template's first paragraph does.

## 0.1.8

- With one transaction in two overlapping statements, `reimport` keeps your edit of it whichever file it
  reads first, and an unedited transaction no longer goes to `.kingsmint/orphans.beancount`.
- `kingsmint upgrade --done` sets the ledger's kingsmint tag in `pyproject.toml` to the upgraded version, also
  in the Claude app, whose own kingsmint did not change the ledger's. When the ledger takes kingsmint from a
  local checkout (`path`) of another version, it warns.

### Ledger

- When `pyproject.toml` takes kingsmint from a `path` that you do not develop in (an older setup wrote one),
  take the release instead: `uv add "git+https://github.com/kingsmint/kingsmint" --tag v<version>`. A checkout
  does not update itself, so `uv run kingsmint` ran an older kingsmint than the plugin.

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
