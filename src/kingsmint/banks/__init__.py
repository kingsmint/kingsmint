"""Statement parsers, one module per bank, in a folder per country (ISO code, as in the IBAN), or `intl`
for providers whose statements are the same in every country.

A PDF parser takes the text from `kingsmint.pdf.pdf_text` and returns a `Statement`. A CSV parser takes the rows
of an account history export and returns (Txn, balance or None) pairs, oldest first.
"""

from kingsmint.banks.sk import fio, tatra, vub

# PDF parser chosen by a marker string found only in that bank's statements
PARSERS = [("VÚB, a.s.", vub.parse_pdf), ("Tatra banka, a.s.", tatra.parse_pdf), ("Tatra banka, a. s.", tatra.parse_pdf_2025),
           ("Fio banka, a.s.", fio.parse_pdf)]
# CSV parser chosen by a column only that bank's export has
CSV_PARSERS = [("Účtovný zostatok", vub.parse_csv), ("Dátum spracovania", tatra.parse_csv)]
