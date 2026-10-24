"""Tatra banka: monthly PDF statements (the old layout, and the layout used since mid-2025), and the account history CSV."""

import datetime as dt
import re
from decimal import Decimal

from kingsmint.banks.common import Statement, Txn, date, iban, squash

TB_START = re.compile(r"^(\d\d\.\d\d\.\d{4})\s+(.*?)\s{2,}.*?([\d,]+\.\d\d)(-?)$")


def tb_num(n, minus=""):
    return Decimal(n.replace(",", "")) * (-1 if minus else 1)


def parse_pdf(text):
    m = re.search(r"Posledný výpis\s+(\S+)\s+([\d,]+\.\d\d)(-?)", text)
    start, opening = date(m[1]) + dt.timedelta(days=1), tb_num(m[2], m[3])
    end = date(re.search(r"Dátum (\d\d\.\d\d\.\d{4})", text)[1])
    m = re.search(r"Zostatok na účte ku dňu vystavenia výpisu:\s+([\d,]+\.\d\d)(-?)", text)
    st = Statement(iban(re.search(r"IBAN (SK[\d ]+\d)", text)[1]), opening, tb_num(*m.groups()), start, end)

    body = text[text.index("Posledný výpis"): text.index("SPOLU")]
    recs = []
    for line in body.splitlines():
        if m := TB_START.match(line):
            recs.append((m, []))
        elif recs and line.startswith(" ") and line.strip():  # page headers start at column 0
            recs[-1][1].append(line)
    for m, lines in recs:
        st.txns.append(tb_txn(Txn(date(m[1]), tb_num(m[3], m[4]), narration=squash(m[2])), lines))
    return st


def tb_txn(t, lines):
    """Fill payee, IBAN and narration from the detail lines; a value continues on lines indented deeper."""
    def indent(x):
        return len(x) - len(x.lstrip())
    for i, line in enumerate(lines):
        s = line.strip()
        deeper = [x for x in lines[i + 1:i + 3] if indent(x) > indent(line)][:1]
        if k := re.match(r"(Príjemca|Platiteľ):\s+(\S+)", s):
            t.iban = k[2]
            t.payee = squash(deeper[0]) if deeper and lines.index(deeper[0]) == i + 1 else ""
        elif k := re.match(r"Miesto [^:]+:\s+\S.*?\s{2,}(.*)", s):
            t.payee = squash(k[1])
        elif s.startswith("Detail:"):
            cont = []
            for x in lines[i + 1:]:
                if indent(x) <= indent(line):
                    break
                cont.append(squash(x))
            t.narration = squash(" ".join([s[7:], *cont]))
    return t


# Tatra banka layout used until mid-2025: "Od 1.1.2025 Do 31.1.2025", amounts "-2 500.00"
TB2_START = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{4})\s{2,}(\S.*?)\s{2,}(-?\d[\d ]*\.\d\d)$")
TB2_PAGE = re.compile(r"tatrabanka\.sk|^\s*(Tatra banka, a\. s\.|IČO:|Obchodný register|Oddiel:)")


def parse_pdf_2025(text):
    m = re.search(r"Od\s+(\S+)\s+Do\s+(\S+)", text)
    start, end = date(m[1]), date(m[2])
    opening = Decimal(re.search(r"Počiatočný zostatok\s+(-?[\d ]+\.\d\d)", text)[1].replace(" ", ""))
    closing = Decimal(re.search(r"Koncový zostatok\s+(-?[\d ]+\.\d\d)", text)[1].replace(" ", ""))
    st = Statement(re.search(r"IBAN\s+(SK\d+)", text)[1], opening, closing, start, end)

    body = text[text.index("Dátum zúčtovania"): text.index("Týmto potvrdzujeme")]
    recs = []
    for line in body.splitlines()[1:]:
        if not line.strip() or TB2_PAGE.search(line):
            continue
        if m := TB2_START.match(line):
            recs.append((m, []))
        elif recs:  # the 2nd line starts with the booking date: blank it to keep the indentation
            recs[-1][1].append(re.sub(r"^\d{1,2}\.\d{1,2}\.\d{4}", lambda d: " " * len(d[0]), line))
    for m, lines in recs:
        st.txns.append(tb_txn(Txn(date(m[1]), Decimal(m[3].replace(" ", "")), narration=squash(m[2])), lines))
    return st


def parse_csv(rows):
    """Tatra banka download: newest first, unsigned amounts with Debet/Kredit, no balance."""
    out = []
    for r in reversed(rows):
        amount = Decimal(r["Suma"].replace(" ", "").replace(",", "."))
        t = Txn(date(r["Dátum spracovania"].strip()), -amount if r["Typ"] == "Debet" else amount,
                narration=squash(r["Informácia pre príjemcu"]) or squash(r["Popis"]), iban=r["IBAN"].strip())
        out.append((t, None))
    return sorted(out, key=lambda x: x[0].date)
