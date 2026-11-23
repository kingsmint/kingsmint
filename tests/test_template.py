"""The saved queries of template/main.beancount, on a small synthetic ledger."""
from pathlib import Path

import beanquery
from beancount import loader
from beancount.core.data import Query

TEMPLATE = Path(__file__).parent.parent / "template" / "main.beancount"

LEDGER = """
2000-01-01 open Assets:Me:Bank EUR
2000-01-01 open Assets:Me:Investments EUR
2000-01-01 open Assets:Me:Property:Flat EUR
2000-01-01 open Assets:Me:Loans:Friend EUR
2000-01-01 open Assets:Co:Car EUR
  liquid: "false"
2000-01-01 open Equity:Opening-Balances EUR
2024-01-01 * "Opening"
  Assets:Me:Bank            100 EUR
  Assets:Me:Investments     200 EUR
  Assets:Me:Property:Flat  1000 EUR
  Assets:Me:Loans:Friend     50 EUR
  Assets:Co:Car             300 EUR
  Equity:Opening-Balances
"""


def test_liquid_money_leaves_out_property_and_loans(tmp_path):
    # property and loans given without liquid: "false" are not liquid by their name
    text = TEMPLATE.read_text().replace("CURRENCY", "EUR").replace('"TITLE"', '"T"').replace('"LOCALE"', '"sk_SK"')
    text = "\n".join(line for line in text.splitlines() if not line.startswith("include "))  # only the queries
    (tmp_path / "main.beancount").write_text(text + LEDGER)
    entries, errors, options = loader.load_file(str(tmp_path / "main.beancount"))
    query = next(e.query_string for e in entries if isinstance(e, Query) and e.name == "Liquid money")
    rows = beanquery.connect("beancount:", entries=entries, errors=errors, options=options).execute(query).fetchall()
    assert {a: inv.get_currency_units("EUR").number for a, inv in rows} == {"Assets:Me:Bank": 100, "Assets:Me:Investments": 200}
