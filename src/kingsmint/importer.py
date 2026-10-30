"""Import bank statements into the ledger in the current directory.

usage: kingsmint import [--force] [PATH ...]     (default PATH: inbox)

For each bank PDF: detect the bank, parse transactions, check that they sum to the
statement's closing - opening balance, categorize them with rules.beancount,
write ledger/<account>/<YYYY-MM>.beancount and move the PDF to documents/<account>/<start>_<end>.<IBAN>.pdf
(the IBKR account number instead of an IBAN for its CSVs).
IBKR year-to-date activity statement CSVs always replace ledger/<broker account>/<year>.beancount; the cash
account is the one whose `ibkr` metadata is the IBKR account number, securities are its sibling `:Securities`.
Account history CSVs (VUB "export pohybov na účte", Tatra download; the file name must start with the
account IBAN) are split by year into ledger/<account>/csv-<year>.beancount, including years without
movements; years that already have PDF statements are skipped.
Files already in documents/ get the same name (used by `kingsmint import --force documents`).
"""

import csv
import datetime as dt
import filecmp
import re
import shutil
import sys
from decimal import Decimal
from pathlib import Path

from beancount import loader
from beancount.core import data, interpolate

from kingsmint.banks import CSV_PARSERS, PARSERS
from kingsmint.banks.common import Statement, Txn
from kingsmint.banks.intl.ibkr import parse_csv as parse_ibkr, sections as ibkr_sections
from kingsmint.pdf import pdf_text

ROOT = Path.cwd()
LEDGER = ROOT / "main.beancount"

def read_csv(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1250")
    lines = text.splitlines()
    return list(csv.DictReader(lines, delimiter=";" if lines[0].count(";") > lines[0].count(",") else ","))


def import_account_csv(path, rows, accounts, own, rules, force):
    iban = re.match(r"(?:\d{4}-\d\d-\d\d[._])*([A-Z]{2}\d{2}[A-Z0-9]{11,30})", path.name)
    account = accounts.get(iban[1]) if iban else None
    if not account:
        return print(f"FAIL {path.name}: the name must start with an IBAN that is in accounts.beancount")
    parse = next((p for column, p in CSV_PARSERS if column in rows[0]), None)
    if not parse:
        return print(f"skip {path.name}: unknown bank")
    parsed = parse(rows)
    first = parsed[0]
    balance = first[1] - first[0].amount if first[1] is not None else Decimal(0)  # no balance column: opened at 0
    folder = ROOT / "ledger" / account.replace(":", "-")
    # every year of the export, also those without movements: the export shows the balance did not change
    years = list(range(min(t.date.year for t, _ in parsed), max(t.date.year for t, _ in parsed) + 1))
    doc = None
    for year in years:
        items = [x for x in parsed if x[0].date.year == year]
        opening, closing = balance, balance + sum(t.amount for t, _ in items)
        balance = closing
        if items and items[-1][1] is not None and items[-1][1] != closing:
            return print(f"FAIL {path.name}: {year} sums to {closing}, the bank's balance is {items[-1][1]}")
        if any(folder.glob(f"{year}-[0-9][0-9].beancount")):
            continue  # this year comes from PDF statements
        out = folder / f"csv-{year}.beancount"
        if out.exists() and not force:
            print(f"skip {path.name} {year}: {out.relative_to(ROOT)} exists (use --force)")
            continue
        start = items[0][0].date if year == years[0] else dt.date(year, 1, 1)
        end = items[-1][0].date if year == years[-1] else dt.date(year, 12, 31)
        st = Statement(iban[1], opening, closing, start, end, [t for t, _ in items])
        folder.mkdir(parents=True, exist_ok=True)
        doc = doc or archive(path, account, iban[1], parsed[0][0].date, parsed[-1][0].date)
        if not doc:
            return
        out.write_text(render(st, account, own, rules, doc.name), encoding="utf-8")
        print(f"ok   {path.name} {year} -> {out.relative_to(ROOT)} ({len(items)} txns)")


# ---------------------------------------------------------------- import


def load():
    entries, errors, _ = loader.load_file(str(LEDGER))
    for e in errors:
        print("ledger error:", e.message, file=sys.stderr)
    opens = [e for e in entries if isinstance(e, data.Open) and "iban" in e.meta]
    accounts = {e.meta["iban"]: e.account for e in opens}
    # transfers to an own account are matched through Assets:Transit only while both sides are imported
    own = {e.meta["iban"]: (e.meta.get("statements_until", dt.date.max), (e.currencies or [None])[0]) for e in opens}
    rules = [(e.date, re.compile(e.values[0].value, re.I), e.values[1].value,
              [(e.values[i].value, e.values[i + 1].value) for i in range(2, len(e.values), 2)],
              f"{Path(e.meta['filename']).name}:{e.meta['lineno']}")
             # file order, not date order (the loader sorts entries by date): the first matching rule wins
             for e in sorted((e for e in entries if isinstance(e, data.Custom) and e.type == "rule"),
                             key=lambda e: (e.meta["filename"], e.meta["lineno"]))]
    ibkr = {e.meta["ibkr"]: e.account for e in entries if isinstance(e, data.Open) and "ibkr" in e.meta}
    return accounts, own, rules, ibkr


def categorize(t, own, rules, currency="EUR"):
    return match(t, own, rules, currency)[:2]


def match(t, own, rules, currency="EUR"):
    """(account, splits, why): why is the rule's "file:line", "own account", or "no rule"."""
    until, other_currency = own.get(t.iban, (dt.date.min, None))
    if t.date <= until:  # between own accounts: a transfer, or an exchange when the currencies differ
        return ("Equity:Conversions" if other_currency not in (None, currency) else "Assets:Transit"), [], "own account"
    text = f"{t.payee} | {t.narration} | {t.iban} | {t.amount}"
    for since, rx, account, splits, *where in rules:
        if since <= t.date and (rx.search(text) or t.vs and rx.search(f"VS{t.vs}")):
            return account, splits, where[0] if where else "rule"
    return "Income:Uncategorized" if t.amount > 0 else "Expenses:Uncategorized", [], "no rule"


def preview():
    """What `reimport` would change: imported bank transactions that the current rules categorize differently."""
    accounts, own, rules, _ = load()
    iban_of = {a: i for i, a in accounts.items()}
    changes = {}
    for e in loader.load_file(str(LEDGER))[0]:
        bank = e.postings[0] if isinstance(e, data.Transaction) and e.postings else None
        # render() writes: bank account, fee, splits, then the category without an amount (the loader fills it in)
        auto = [p for p in e.postings[1:] if (p.meta or {}).get(interpolate.AUTOMATIC_META)] if bank else []
        if not auto or bank.account not in iban_of:
            continue  # IBKR, hand-written, and zero-amount entries are not categorized by rules
        fee = e.postings[1].units.number if e.postings[1] is not auto[0] and e.postings[1].account == "Expenses:Bank:Fees" else 0
        t = Txn(e.date, bank.units.number + fee, e.payee or "", e.narration or "", e.meta.get("iban", ""),
                vs=e.meta.get("vs", ""))
        others = {k: v for k, v in own.items() if k != iban_of[bank.account]}
        new, _, why = match(t, others, rules, bank.units.currency)
        old = auto[0].account
        if new != old:
            changes.setdefault((why, old, new), []).append(f"{t.date}  {t.payee} | {t.narration} | {t.iban} | {t.amount}")
    for (why, old, new), txns in sorted(changes.items(), key=lambda kv: -len(kv[1])):
        print(f"{why}  {old} -> {new}  {len(txns)}")
        for line in txns[:3]:
            print(f"    {line}")
    n = sum(map(len, changes.values()))
    print(f"{n} transactions would change; `uv run kingsmint reimport` applies the rules" if n else "no changes")


def clear_generated():
    """Delete the files `import` wrote to ledger/, so a reimport leaves none of an account that was renamed."""
    for f in (ROOT / "ledger").rglob("*.beancount"):
        if f.read_text(encoding="utf-8").startswith("; generated by kingsmint"):
            f.unlink()
    for d in (ROOT / "ledger").iterdir():
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def q(s):
    return '"' + s.replace("\\", "").replace('"', "'") + '"'


def render(st, account, own, rules, source):
    out = [f"; generated by kingsmint from {source} -- edits are lost on `kingsmint reimport`", "",
           f"{st.start} balance {account} {st.opening:.2f} {st.currency}", ""]
    for t in sorted(st.txns, key=lambda t: t.date):
        other, splits = categorize(t, {k: v for k, v in own.items() if k != st.iban}, rules, st.currency)
        flag = "!" if other.endswith("Uncategorized") else "*"
        out.append(f"{t.date} {flag} {q(t.payee)} {q(t.narration)}")
        out.append(f"  document: {q(source)}")  # Fava opens the statement from the transaction
        if t.iban:
            out.append(f"  iban: {q(t.iban)}")  # counterparty; rules and transfer detection match on it
        if t.vs:
            out.append(f"  vs: {q(t.vs)}")
        out.append(f"  {account}  {t.amount + t.fee:.2f} {st.currency}")
        if t.fee:
            out.append(f"  Expenses:Bank:Fees  {-t.fee:.2f} {st.currency}")
        for split_account, share in splits:
            out.append(f"  {split_account}  {-t.amount * share:.2f} {st.currency}")
        if t.amount:
            out.append(f"  {other}")
        out.append("")
    out.append(f"{st.end + dt.timedelta(days=1)} balance {account} {st.closing:.2f} {st.currency}")
    return "\n".join(out) + "\n"


def archive(src, account, key, start, end):
    """Move a statement to documents/<account>/<start>_<end>.<IBAN or broker account>.<ext>: a name that is
    unique whatever the bank called the file; Beancount finds a document by the date at the start of its name.
    None, after a FAIL line, when another file already has that name."""
    doc = ROOT / "documents" / account.replace(":", "/") / f"{start}_{end}.{key}{src.suffix.lower()}"
    if src.resolve() == doc.resolve():
        return doc
    if doc.exists():
        if not filecmp.cmp(src, doc, shallow=False):
            return print(f"FAIL {src.name}: {doc.relative_to(ROOT)} is another statement for the same account and "
                         "period; compare the two, keep one, and delete the other")
        src.unlink()  # the same statement downloaded twice
        return doc
    doc.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, doc)
    return doc


def with_document(text, account, name):
    """Add `document: name` to each transaction that posts to `account`, where Fava finds the statement."""
    return "\n\n".join(re.sub(r"^\d{4}-\d\d-\d\d \* .*$", lambda m: f"{m[0]}\n  document: {q(name)}", b, count=1, flags=re.M)
                       if f"\n  {account}  " in b else b for b in text.split("\n\n"))


def import_ibkr(path, ibkr):
    cash_acc, start, end, opening, year = parse_ibkr(path, ibkr)
    doc = archive(path, cash_acc, next(n for n, a in ibkr.items() if a == cash_acc), start, end)
    if not doc:
        return
    opening, year = (with_document(x, cash_acc, doc.name) for x in (opening, year))
    folder = ROOT / "ledger" / cash_acc.rsplit(":", 1)[0].replace(":", "-")
    folder.mkdir(parents=True, exist_ok=True)
    # opening positions come from the earliest statement only, later years continue from it
    first = folder / "opening.beancount"
    since = re.search(r"^(\d{4}-\d\d-\d\d) \*", first.read_text(encoding="utf-8"), re.M) if first.exists() else None
    if not since or start <= dt.date.fromisoformat(since[1]):
        first.write_text(f"; generated by kingsmint from {doc.name}\n\n" + opening, encoding="utf-8")
    out = folder / f"{start.year}.beancount"
    out.write_text(f"; generated by kingsmint from {doc.name} -- edits are lost on `kingsmint reimport`\n\n" + year, encoding="utf-8")
    print(f"ok   {path.name} -> {out.relative_to(ROOT)}")


def import_pdf(pdf, accounts, own, rules, force):
    text = pdf_text(pdf)
    parse = next((p for marker, p in PARSERS if marker in text), None)
    if not parse:
        return print(f"skip {pdf.name}: unknown bank")
    st = parse(text)
    for t in st.txns:  # e.g. a reversal listed in April but dated 31 March: keep it inside the period
        t.date = min(max(t.date, st.start), st.end)
    total = sum(t.amount + t.fee for t in st.txns)
    if total != st.closing - st.opening:
        return print(f"FAIL {pdf.name}: transactions sum to {total}, statement says {st.closing - st.opening}")
    account = accounts.get(st.iban)
    if not account:
        return print(f"FAIL {pdf.name}: no account with iban {st.iban!r} in accounts.beancount")

    out = ROOT / "ledger" / account.replace(":", "-") / f"{st.end:%Y-%m}.beancount"
    if out.exists() and not force:
        return print(f"skip {pdf.name}: {out.relative_to(ROOT)} exists (use --force)")
    doc = archive(pdf, account, st.iban, st.start, st.end)
    if not doc:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(st, account, own, rules, doc.name), encoding="utf-8")
    print(f"ok   {pdf.name} -> {out.relative_to(ROOT)} ({len(st.txns)} txns)")


# ---------------------------------------------------------------- scan


def scan_file(f, accounts, ibkr):
    """One line about a statement without importing it: bank, account id, currency, period, holder, type."""
    if f.suffix.lower() == ".pdf":
        text = pdf_text(f)
        parse = next((p for marker, p in PARSERS if marker in text), None)
        if not parse:
            return "unknown bank"
        st = parse(text)
        bank, key, known, currency, start, end = parse.__module__.split(".")[-1], st.iban, accounts.get(st.iban), st.currency, st.start, st.end
        holder, kind = st.holder, st.type
    elif f.read_bytes()[:20].lstrip(b"\xef\xbb\xbf").startswith(b"Statement,"):
        _, acct, key, start, end = ibkr_sections(f)
        bank, known, currency = "ibkr", ibkr.get(key), acct.get("Base Currency", "")
        holder, kind = acct.get("Name", ""), acct.get("Customer Type", "")
    else:
        rows = read_csv(f)
        parse = next((p for column, p in CSV_PARSERS if column in rows[0]), None)
        iban = re.match(r"(?:\d{4}-\d\d-\d\d[._])*([A-Z]{2}\d{2}[A-Z0-9]{11,30})", f.name)
        if not parse or not iban:
            return "unknown bank" if not parse else "the name must start with the account IBAN"
        dates = [t.date for t, _ in parse(rows)]
        bank, key, known, currency, start, end = parse.__module__.split(".")[-1] + " csv", iban[1], accounts.get(iban[1]), "", min(dates), max(dates)
        holder = kind = ""  # an account history export has no header
    fields = [bank, key, currency, f"{start}..{end}", f"holder: {holder}" if holder else "", f"type: {kind}" if kind else ""]
    return "  ".join(x for x in fields if x) + f"  -> {known or 'NEW'}"


def scan(paths):
    files = sorted(f for p in paths for f in ([p] if p.is_file() else p.rglob("*")) if f.suffix.lower() in (".pdf", ".csv"))
    if not files:
        return print(f"nothing to scan in {', '.join(map(str, paths))}")
    accounts, _, _, ibkr = load()
    for f in files:
        try:
            print(f"{f.name}  {scan_file(f, accounts, ibkr)}")
        except Exception as e:  # one unreadable file must not hide the others
            print(f"{f.name}  FAIL {type(e).__name__}: {e}")


def main(args):
    force = "--force" in args
    paths = [Path(a) for a in args if a != "--force"] or [ROOT / "inbox"]
    # PDFs first: an account history CSV skips the years that PDF statements already cover
    files = sorted((f for p in paths for f in ([p] if p.is_file() else p.rglob("*")) if f.suffix.lower() in (".pdf", ".csv")),
                   key=lambda f: (f.suffix.lower() == ".csv", f.name))
    if not files:
        return print(f"nothing to import in {', '.join(map(str, paths))}")
    accounts, own, rules, ibkr = load()
    for f in files:
        if f.suffix.lower() == ".pdf":
            import_pdf(f, accounts, own, rules, force)
        elif f.read_bytes()[:20].lstrip(b"\xef\xbb\xbf").startswith(b"Statement,"):
            import_ibkr(f, ibkr)
        else:
            import_account_csv(f, read_csv(f), accounts, own, rules, force)


