"""Statement parsers, one module per bank, in a folder per country (ISO code, as in the IBAN), or `intl`
for providers whose statements are the same in every country.

A PDF parser takes the text from `kingsmint.pdf.pdf_text` and returns a `Statement`. A CSV parser takes the rows
of an account history export and returns (Txn, balance or None) pairs, oldest first.
"""

import importlib.util
import sys
from pathlib import Path

from kingsmint.banks.sk import fio, tatra, vub

# PDF parser chosen by a marker string found only in that bank's statements
PARSERS = [("VÚB, a.s.", vub.parse_pdf), ("Tatra banka, a.s.", tatra.parse_pdf), ("Tatra banka, a. s.", tatra.parse_pdf_2025),
           ("Fio banka, a.s.", fio.parse_pdf)]
# CSV parser chosen by a column only that bank's export has
CSV_PARSERS = [("Účtovný zostatok", vub.parse_csv), ("Dátum spracovania", tatra.parse_csv)]


def load_local(folder=Path("banks")):
    """Parsers the ledger adds in its own banks/*.py, for a bank kingsmint lacks (the Claude app cannot change the
    installed kingsmint). They come first, so one can also replace a built-in parser. A module defines MARKER and
    parse_pdf(text), and/or COLUMN and parse_csv(rows), like the built-in ones, and a docstring for `kingsmint banks`."""
    for f in sorted(folder.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"kingsmint_local.{f.stem}", f)  # scan names the bank by the last part
        sys.modules[spec.name] = m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        if hasattr(m, "parse_pdf"):
            PARSERS.insert(0, (m.MARKER, m.parse_pdf))
        if hasattr(m, "parse_csv"):
            CSV_PARSERS.insert(0, (m.COLUMN, m.parse_csv))


load_local()
