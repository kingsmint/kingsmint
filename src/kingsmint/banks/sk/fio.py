"""Fio banka, Slovak branch: monthly PDF statements in EUR or USD."""

import re

from kingsmint.banks.common import Statement, Txn, date, sk_num, squash

FIO_AMT = r"(-?\d{1,3}(?:[  ]\d{3})*,\d\d)"
FIO_START = re.compile(r"^ ?(\d{1,2}\.\d{1,2}\.\d{4})\s{2,}(\S.*?)(?:\s{2,}(\S+))?\s{2,}" + FIO_AMT + "$")


def parse_pdf(text):
    m = re.search(r"Výpis za obdobie\s+(\S+)-(\S+)", text)
    start, end = date(m[1]), date(m[2])
    opening = sk_num(re.search(r"Starý zostatok\s+" + FIO_AMT, text)[1])
    closing = sk_num(re.search(r"Nový zostatok\s+" + FIO_AMT, text)[1])
    st = Statement(re.search(r"IBAN\s+(SK\d+)", text)[1], opening, closing, start, end)
    if cur := re.search(r"Mena účtu\s+([A-Z]{3})", text):
        st.currency = cur[1]

    recs, skip = [], True
    for line in text.splitlines():
        if "Užívateľský symbol" in line:
            skip = False
            continue
        if re.search(r"\s\d+ z \d+$", line) or "koniec zostavy" in line:  # page footer
            skip = True
        if skip:
            continue
        if m := FIO_START.match(line):
            recs.append((m, []))
        elif recs and line.strip():
            recs[-1][1].append(line)
    for m, lines in recs:
        t = Txn(date(m[1]), sk_num(m[4]), narration=squash(m[2]))
        if m[3] and "/" in m[3]:
            t.iban = m[3].split("/")[0]
        # before the operation ID line: continuation of the type, or "date  detail  counterparty name";
        # after it: card details or messages for the recipient.
        # Statements before ~2021 put VS/SS/KS in a right column and a message on the ID line.
        op, name, msgs, seen_id = [m[2]], "", [], False
        for x in lines:
            x = re.sub(r"\s{2,}\d+$", "", x.strip())  # old layout: VS/SS/KS column
            if not x or re.fullmatch(r"\d+", x) and seen_id:
                continue
            if i := re.match(r"\d{8,}(?:\s{2,}(.*))?$", x):
                seen_id = True
                if i[1] and not re.match(r"(VS|REF):", i[1]):
                    msgs.append(squash(i[1]))
            elif not seen_id:
                if d := re.match(r"\d{1,2}\.\d{1,2}\.\d{4}\s{2,}(.*)", x):
                    name = (re.split(r"\s{2,}", d[1]) + [""])[1]
                elif not re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", x):
                    op.append(x)
            elif not re.match(r"(VS|REF):|\d{15,}$", x):
                msgs.append(squash(x))
        msgs = list(dict.fromkeys(msgs))
        if buy := next((x for x in msgs if x.startswith("Nákup: ")), None):
            t.payee = buy[7:].split(",")[0]
        elif atm := next((x for x in msgs if x.startswith("Výběr z bankomatu: ")), None):
            t.payee, t.narration = "Výběr z bankomatu", atm[19:]
        else:
            t.payee = name or (msgs.pop(0) if msgs else "")
            t.narration = " ".join(msgs) or squash(" ".join(op))
        st.txns.append(t)
    return st
