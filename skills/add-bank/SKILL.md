---
name: add-bank
description: Add or fix a statement parser in the kingsmint importer. Use when import says "unknown bank", a bank changed its statement layout, or a statement fails to reconcile.
---

# Add a bank parser

A parser turns one statement into a `Statement` (`src/kingsmint/banks/common.py` in the kingsmint repository): IBAN, opening and closing balance,
period, and `Txn` rows. The reconciliation check in `import_pdf` (opening + transactions = closing)
is the proof that a parser is right, so a parser is done only when every statement of that bank
reconciles.

The ledger's `pyproject.toml` (`tool.uv.sources`) says where kingsmint comes from. With a git source,
clone kingsmint, point the source to the local path (`{ path = "...", editable = true }`), and run
`uv sync`. The parser is public code: it must not contain the user's IBANs, names, or amounts, and
their statements never go into the kingsmint repository.

1. Get the text: `uv run python -I -c "import sys; from kingsmint.pdf import pdf_text; print(pdf_text(sys.argv[1]))" <file>`
   for PDFs, or read the CSV with `uv run python -I`. Find the
   IBAN, the balances, the period, and how one transaction spans lines.
2. Write the parser in `src/kingsmint/banks/<country>/<bank>.py`: the country is the ISO code from the
   IBAN (`sk`, `cz`, `de`), or `intl` for providers whose statements are the same everywhere. Name the
   functions `parse_pdf(text)` and `parse_csv(rows)`, and reuse the helpers in `banks/common.py`
   (`sk_num`, `date`, `iban`, `squash`, `merchant`). A new layout of a known bank gets its own function
   in the same file (see `tatra.parse_pdf_2025`).
   Parsers work on text. When the text alone cannot be parsed (empty table cells, wrapped columns),
   that parser may read the PDF with pdfplumber (`extract_tables`) as an extra dependency; `pdf_text`
   stays on pypdfium2 for speed.
3. Register it in `banks/__init__.py`: `PARSERS` with a marker string found only in that bank's PDFs,
   `CSV_PARSERS` with a column only that bank's export has.
4. Fill `payee`, `narration`, and the counterparty `iban`: the rules match on them. Fill the statement's
   `holder` and `type` from the header (`header()` in `banks/common.py`): `kingsmint scan` shows them, and
   setup derives the accounts from them. Check that `uv run kingsmint scan` prints them for every layout.
5. Import every statement of the bank, old and new layouts. Fix the parser until each one is `ok`.
   Typical misreads: a record split over two lines, a page break inside the table, a fee row, a
   reversal dated outside the period, a thousands separator.
6. For a new account, add the `open` with `iban` in `accounts.beancount`. Then run `uv run kingsmint check`,
   the `categorize` skill, and commit the ledger.
7. Commit the parser in the kingsmint repository and offer the user to send it upstream as a pull request.
