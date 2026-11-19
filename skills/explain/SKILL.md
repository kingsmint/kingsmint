---
name: explain
description: Explain the money with numbers from the ledger. Use for the month close, net profit or spending changes between periods, a year forecast, tax rate, or the baseline and runway without income.
---

# Explain the money

Write every message to the user, also short progress notes, in the language that `CLAUDE.md` names,
or else in the language the user writes in.

Answer with tables of numbers from `bean-query`, then the causes in plain words. State what was not checked.

`bean-query` gotchas:
- Sum in EUR: `sum(number(convert(position, 'EUR', date)))`. An inventory cannot be divided.
- Account metadata: `open_meta(account, 'need')`; cast with `str()` / `decimal()`; missing metadata is
  null, so wrap it in `coalesce()`.
- Saved queries: `bean-query main.beancount '.run "Baseline"'`.
- In the Fava filter, quote numbers: `"1234567890"`.

## The month close

The month is the last full calendar month. Done when the user has the summary below and no question is open.

1. Run `uv run kingsmint coverage`. When an account's last imported day is before the month's last day, list
   those accounts and stop: the user downloads their statements, drops them into the inbox, and closes the month
   again. An account with `statements_until` is not missing.
2. When `inbox/` holds statements, import them with the `import` skill, which also categorizes them. When
   `Uncategorized` transactions of the month remain, categorize them with the user first.
3. Summarize the month, against the average of the 12 months before it:
   - income, expenses, and the difference (what was saved);
   - per `root(account, 2)` expense account, the month and the average; name the 3 largest changes, up and down;
   - one-off transactions above 10% of the month's expenses, and payees that appear for the first time;
   - runway: `uv run kingsmint runway` (months of the baseline that the liquid money covers).
   Give the causes in plain words, as in "A change between periods". End with what to watch next month.
4. Commit: `Close <month>`, with the three main numbers of the summary in the body.

## A change between periods

Work through every check; most surprises in this ledger came from checks 3–5, not from spending.

1. Split net profit into income and expenses for both periods. Name the side that moved.
2. Per account (`root(account, 2)`, then full accounts), list the largest differences.
3. **One-offs**: single large transactions (inheritance, a car sale, dividend tax, a partner's
   contribution). Ask whether each is income, equity, or an asset.
4. **Timing**: corporate and income tax arrive a year after the income, until tax advances start;
   a cash deposit returns earlier withdrawn cash as a negative expense; client money that waits in an
   account without statements is booked when it moves to an imported account.
5. **Coverage**: missing statement months or accounts make a period look better or worse. Compare
   each account's first and last month with the period.
6. **Scale**: net profit is a small difference of two large numbers, so a moderate change in income
   is a large change in net profit. Give the percentage on both sides.

## A forecast for the current year

Actual months from the ledger plus an estimate for the rest. Base income on this year's monthly
average and the user's plans (holidays); base expenses on the same months of last year, which carry the
seasonal items (Christmas, year-end cash withdrawals). State the assumption about when clients pay
(the month after the work), and give the variant when it is wrong.

## Tax rate

Payments to the state over client income, per year and over several years, both in the same year and
shifted one year (tax follows the income). Show VAT separately: with clients abroad (reverse charge), it is mostly refunds.

## Baseline and runway

Run the saved queries `Baseline`, `Baseline by account`, and `Liquid money` (see `main.beancount`).
Runway = liquid money / baseline, with and without investments. Labels and `cut` factors are metadata in
`accounts.beancount`; the user owns them, so change them only on request.
