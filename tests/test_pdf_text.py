from kingsmint.pdf import pdf_text
from pdf import make_pdf


def test_columns_and_phrases(tmp_path):
    pdf = tmp_path / "s.pdf"
    make_pdf(pdf, "Helvetica", [(50, 700, "1.2.2025"), (150, 700, "Card payment Lidl"), (450, 700, "-12,50"),
                                (150, 686, "detail line")])
    lines = pdf_text(pdf).splitlines()
    assert lines[0].split("  ")[0] == "1.2.2025" and "Card payment Lidl" in lines[0]  # one space inside a phrase
    assert lines[0].rstrip().endswith("-12,50") and "Lidl  " in lines[0]  # columns: 2+ spaces
    assert lines[1].startswith(" ") and lines[1].index("detail") == lines[0].index("Card")  # indentation kept


def test_monospaced_exact_columns(tmp_path):
    pdf = tmp_path / "m.pdf"
    make_pdf(pdf, "Courier", [(50, 700, "Mena"), (86, 700, "EUR")])  # Courier 10pt: 6pt per character
    assert pdf_text(pdf) == "Mena  EUR"
