"""VÚB banka: monthly or yearly PDF statements, and the account history CSV ("export pohybov na účte")."""

import datetime as dt
import re
from decimal import Decimal

from kingsmint.banks.common import Statement, Txn, date, iban, merchant, sk_num, squash

VUB_AMT = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d\d)\s*$")
VUB_DATE = re.compile(r"^(\d\d)/(\d\d)\s")
VUB_REF = re.compile(r"\s{2,}\w{13}(?:\s.*)?$")  # bank reference + fee columns
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?)\b")


def parse_pdf(text):
    m = re.search(r"^\s*k (\d\d\.\d\d\.\d{4})\s+(-?[\d.]+,\d\d)", text, re.M)  # under "Vlastné použiteľné prostriedky"
    start, opening = date(m[1]) + dt.timedelta(days=1), sk_num(m[2])
    m = re.search(r"Vlast\. použit\. prostr\. k (\S+).*?\n\s*(-?[\d.]+,\d\d)", text)
    end, closing = date(m[1]), sk_num(m[2])
    st = Statement(iban(re.search(r"Číslo:\s+(SK[\d ]+\d)", text)[1]), opening, closing, start, end)

    # Each record: line 1 = booking date, type or IBAN, amount;
    # line 2 = realization date (cards only), description, reference, fee;
    # then optional "Názov:", "Účel platby:", ... lines.
    in_table, rec, want_line2 = False, None, False
    for line in text.splitlines():
        if "ROZPIS POPLATKOV" in line:
            break
        # the page header ends with "Pobočka:" (left column, not the indented one at the top right);
        # on the last page the table header is not repeated
        if ("Popis transakcie" in line and "Poplatok" in line) or (rec and line.startswith("Pobočka:")):
            in_table = True
            continue
        if "Por. číslo:" in line:
            in_table = False
        if not in_table or not line.strip():
            continue
        if want_line2:
            want_line2 = False
            if a := VUB_AMT.search(line):
                rec["fee"] = sk_num(a[1])
                line = line[: a.start()]
            rec["line2"] = squash(VUB_REF.sub("", re.sub(r"^\s*\d\d/\d\d\s", "", line)))
            continue
        if d := VUB_DATE.match(line):
            a = VUB_AMT.search(line)
            rec = {"day": int(d[1]), "month": int(d[2]), "amount": sk_num(a[1]) if a else Decimal(0),
                   "line1": line[d.end(): a.start() if a else None], "fee": Decimal(0), "details": {}}
            st.txns.append(rec)
            want_line2 = True
        elif rec and (kv := re.match(r"\s*([^:]+):\s*(.*)", line)):
            rec["details"][kv[1]] = squash(kv[2])

    for i, r in enumerate(st.txns):
        year = end.year - (r["month"] > end.month)
        line1 = squash(r["line1"])
        ib = IBAN_RE.search(r["line1"])  # raw: VS after the IBAN is separated by 2+ spaces
        desc = squash(re.sub(r"\b\d+\b", "", line1)) if not ib else ""  # drop VS/KS numbers
        name = r["details"].get("Názov", "").replace("Neuvedené", "")  # "not given"
        payee = name or merchant(r["line2"])
        narration = r["details"].get("Účel platby") or (r["line2"] if name else desc)
        st.txns[i] = Txn(dt.date(year, r["month"], r["day"]), r["amount"], payee, narration,
                         iban(ib[1]) if ib else "", r["fee"])
    return st


def parse_csv(rows):
    """VUB "export pohybov na účte": oldest first, with the running balance."""
    out = []
    for r in rows:
        name, info = squash(r["Názov partnera"]), squash(r["Doplňujúce informácie"])
        t = Txn(dt.datetime.strptime(r["Dátum zaúčtovania"].strip(), "%Y%m%d").date(), sk_num(r["Suma"]),
                iban=r["Účet partnera"].strip())
        if info.startswith("DD") and name.startswith("VUB,"):  # card payment before 2022: "DDTesco~Bratislav...10:39P1"
            t.payee, t.narration = merchant(re.sub(r"(\d{10}|\d\d:\d\dP\d)$", "", info[2:].replace("~", " "))), "Platba kartou"
        elif name in ("", "Platba kartou", "NOTPROVIDED"):  # card payment, fee, or no name: the text is in "Doplňujúce informácie"
            t.payee, t.narration = merchant(info), name.replace("NOTPROVIDED", "")
        else:
            ref = r["Referencia partnera"].strip()
            t.payee, t.narration = name, info or ("" if ref == "NOTPROVIDED" else ref)
        out.append((t, sk_num(r["Účtovný zostatok"])))
    return out
