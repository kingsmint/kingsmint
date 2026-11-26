"""Changes of transactions from the app, written where `kingsmint reimport` keeps them.

One transaction: its postings after the statement row, payee and note, changed in place in its file. In ledger/, the
reimport's three-way merge (kingsmint.merge) keeps what the user changed, by the transaction's `id`.
All transactions of a counterparty: a rule at the top of rules.beancount, then `kingsmint reimport`. It moves the
transactions that only the rules categorize; one whose postings were edited by hand keeps them, and `reset` gives it
the rules' postings back.
"""

import base64
import binascii
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from beancount.core.data import Close, Open
from beancount.parser import parser
from fava.beans.funcs import hash_entry

from dashboard import CASH
from kingsmint import importer, merge
from kingsmint.banks.common import Txn
from ledger_settings import write

FEES = "Expenses:Bank:Fees"  # the importer's fee posting stays as it is: it belongs to the statement row
RULE = re.compile(r'^\d{4}-\d{2}-\d{2} custom "rule" ')


class EditError(ValueError):
    pass


def plain(text: str, what: str) -> str:
    text = text.strip()
    if any(c in text for c in '"\\\n'):
        raise EditError(f"{what}: no quotes, backslashes or line breaks")
    return text


def fees(accounts) -> bool:
    """Whether the accounts after the statement row hold a fee beside a category, as the importer writes it; a
    transaction that is only a fee has the fee as its category."""
    return FEES in accounts and any(a != FEES for a in accounts)


def imported_fee(root: Path, e) -> bool:
    """Whether the import wrote a bank fee beside the category: then that posting belongs to the statement row. One
    that a split by hand added is a category, so the import's postings (.kingsmint/base/) tell, not their shape."""
    try:
        base = base_of(root, e)
    except ValueError:
        base = None
    return fees([a for a, _ in merge.parts(base)[2][1:]] if base else [p.account for p in e.postings[1:]])


def fixed(e, fee: bool):
    """The postings that an edit keeps: the statement row, and the import's fee when `fee`."""
    return [e.postings[0], *([next(p for p in e.postings[1:] if p.account == FEES)] if fee else [])]


def rest_of(e, fee: bool) -> Decimal:
    """What the categories share: the statement row's amount without the fee, with the sign the categories get."""
    keep = fixed(e, fee)
    if any(p.units.currency != keep[0].units.currency or p.cost or p.price for p in keep):
        raise EditError("The statement row has another currency or a price: edit this transaction in Fava")
    return -sum((p.units.number for p in keep), Decimal(0))


def editable(e, entries) -> str | None:
    """Why the app does not change `e`, or None. It changes transactions of the statements: an `id`, and the statement
    row first, on an account with an IBAN. Others (cash.beancount, property.beancount, IBKR) are written by hand in
    their own order, where the first posting is not the statement row: Fava changes them."""
    banks = {o.account for o in entries if isinstance(o, Open) and "iban" in o.meta}
    if "id" not in e.meta or not e.postings or e.postings[0].account not in banks:
        return "Not a transaction of a bank statement: change it in Fava"
    return None


def find(text: str, e, name: str):
    """The chunk (merge.chunks) of `e`: the one with its id. Its line number alone could point to another entry when
    the file changed since Fava loaded it."""
    found = [chunk for chunk in merge.chunks(text, name) if chunk[0] == e.meta["id"]]
    near = [c for c in found if c[3] <= e.meta["lineno"] - 1 < c[4]]  # the same id twice: the one on its line
    if not found:
        raise EditError(f"{name}: the transaction {e.meta['id']} is not there; the file changed")
    return (near or found)[0]


def base_of(root: Path, e) -> str | None:
    """The transaction as kingsmint wrote it at the import (.kingsmint/base/), or None."""
    path = Path(e.meta.get("filename", "")).resolve()
    if "id" not in e.meta or not path.is_relative_to(root.resolve()):
        return None
    name = path.relative_to(root.resolve()).as_posix()
    base = root / merge.BASE / name
    if not base.exists():
        return None
    return next((body for tid, _, body, *_ in merge.chunks(base.read_text(encoding="utf-8"), name)
                 if tid == e.meta["id"]), None)


def bank_text(root: Path, e) -> str:
    """The payee as the bank wrote it, which the rules match: from the import, also when the payee was renamed by hand
    (in Fava, without `bank_payee`)."""
    try:
        base = base_of(root, e)
    except ValueError:
        base = None
    return (merge.bank_text(*merge.parts(base)[:2]) or '""')[1:-1] if base else importer.bank_payee(e)


def save_entry(root: Path, e, entries, postings: list[dict] | None, payee: str | None = None,
               note: str | None = None) -> str:
    """Writes the transaction `e` with the categories `postings` ([{account, amount}]: the amount money in positive,
    none on the last, which gets the rest; None keeps them), and the payee and note when given ("" removes the note).
    Returns what changed, for the version: the transaction as it was named before, and the parts changed."""
    path = Path(e.meta["filename"]).resolve()
    if not path.is_relative_to(root.resolve()) or path.is_relative_to((root / ".kingsmint").resolve()):
        raise EditError(f"{path} is not a file of the ledger")
    if why := editable(e, entries):
        raise EditError(why)
    fee = imported_fee(root, e)
    lines = None if postings is None else categories(e, entries, postings, fee)
    text = path.read_text(encoding="utf-8")
    name = path.relative_to(root.resolve()).as_posix()
    try:
        _, lead, body, start, end = find(text, e, name)
    except ValueError as err:
        raise EditError(str(err)) from None
    head, meta, old, _ = merge.parts(body)
    if lines is not None:
        head = dict(head, flag="!" if any(a.endswith("Uncategorized") for a, _ in lines) else "*")  # as the import flags
    # the app shows the narration when there is no payee: that text unchanged keeps it so; "" removes the payee
    if payee is not None and (payee := plain(payee, "Payee")) not in ({e.payee or ""} | ({e.narration} if not e.payee else set())):
        head = dict(head, payee=f'"{payee}"') if payee else {k: v for k, v in head.items() if k != "payee"}
        if "bank_payee" not in meta and (bank := bank_text(root, e)) and bank != payee:
            meta["bank_payee"] = f'  bank_payee: "{bank}"\n'  # rules match the bank's text, not the name
    if note is not None:
        if note := plain(note, "Note"):
            meta["note"] = f'  note: "{note}"\n'
        else:
            meta.pop("note", None)
    kept = [next(p for p in old[1:] if p[0] == FEES)] if fee else []
    new = merge.assemble(body, head["date"], head, list(meta.items()), old if lines is None else (old[0], *kept, *lines))
    ls = merge.lines(text)
    out = "".join(ls[:start]) + lead + new + "".join(ls[end:])
    if len(parser.parse_string(out)[1]) > len(parser.parse_string(text)[1]):
        raise EditError(f"The change would break {name}; nothing was written")
    write(path, out)
    parts = [*(["category"] if lines is not None else []), *(["payee"] if payee is not None else []),
             *(["note"] if note is not None else [])]
    return f"{e.date} {e.payee or e.narration}", parts


def categories(e, entries, postings: list[dict], fee: bool) -> list[tuple[str, str]]:
    """The checked categories of `e` as (account, posting line). The categories they replace must be in the statement
    row's currency, without a cost or price, and of one sign: else the change would lose them, so Fava changes it."""
    opened = {o.account: o.date for o in entries if isinstance(o, Open)}
    closed = {c.account: c.date for c in entries if isinstance(c, Close)}
    if not postings:
        raise EditError("At least one category")
    rest, total = rest_of(e, fee), Decimal(0)
    if not rest:
        raise EditError("The transaction has no amount to categorize")
    currency, lines = e.postings[0].units.currency, []
    old = [p for p in e.postings[1:] if p not in fixed(e, fee)]
    if any(p.units.currency != currency or p.cost or p.price for p in old):
        raise EditError("A category has another currency, a cost or a price: change this transaction in Fava")
    if len({p.units.number > 0 for p in old}) > 1:
        raise EditError("Its categories have different signs: change this transaction in Fava")
    for i, p in enumerate(postings):
        account = p.get("account", "")
        if account not in opened or opened[account] > e.date or closed.get(account, dt.date.max) <= e.date:
            raise EditError(f"{account!r} is not open on {e.date}")
        last = i == len(postings) - 1
        if last:
            if p.get("amount") is not None:
                raise EditError("The last category gets the rest: no amount")
            lines.append((account, f"  {account}\n"))
            continue
        try:
            amount = Decimal(str(p.get("amount"))).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise EditError(f"Not an amount: {p.get('amount')!r}") from None
        if amount <= 0:
            raise EditError(f"{account}: the amount is more than 0")
        total += amount
        lines.append((account, f"  {account}  {amount.copy_sign(rest)} {currency}\n"))
    if total >= abs(rest):
        raise EditError(f"The amounts are {total}, the transaction {abs(rest)}: the last category gets nothing")
    return lines


def hand_edited(root: Path, e) -> bool:
    """Whether the categories of `e` differ from what kingsmint wrote at the import (.kingsmint/base/): then reimport
    keeps them, whatever the rules say."""
    try:
        old = base_of(root, e)
        if old is None:
            return False
        path = Path(e.meta["filename"]).resolve()
        mine = find(path.read_text(encoding="utf-8"), e, path.relative_to(root.resolve()).as_posix())[2]
    except ValueError:
        return False
    return merge.parts(mine)[2][1:] != merge.parts(old)[2][1:]


def hash_at(entries, filename: str, lineno: int) -> str | None:
    """The hash of the entry on a line: an edit changes the hash, not the line the entry starts on."""
    return next((hash_entry(x) for x in entries
                 if x.meta.get("filename") == filename and x.meta.get("lineno") == lineno), None)


def hash_of(entries, tid) -> str | None:
    """The hash of the transaction with this id: a reimport moves it to another line."""
    return next((hash_entry(x) for x in entries if tid and x.meta.get("id") == tid), None)


def counterparty(root: Path, e) -> tuple[str, str]:
    """(regex, label) of a rule for the transaction's counterparty: its IBAN, else the bank's payee text."""
    if iban := e.meta.get("iban"):
        return re.escape(str(iban)), str(iban)
    if payee := bank_text(root, e):
        return "^" + re.escape(payee) + r" \|", payee
    raise EditError("The transaction names no counterparty (no IBAN, no payee): change it alone")


def statement_txns(entries, named: dict):
    """(entry, Txn as the importer matched it, the other own accounts) of each imported bank transaction; `named`: the
    bank's payee text of transactions renamed by hand, by id."""
    opens = [o for o in entries if isinstance(o, Open) and "iban" in o.meta]
    iban_of = {o.account: o.meta["iban"] for o in opens}
    own = {o.meta["iban"]: (o.meta.get("statements_until", dt.date.max), (o.currencies or [None])[0]) for o in opens}
    for x in entries:
        if not hasattr(x, "postings") or not x.postings or "id" not in x.meta or x.postings[0].account not in iban_of:
            continue
        bank = x.postings[0]
        # shortcut: the fee by the postings' shape, not the import's: a split by hand with Expenses:Bank:Fees in it
        # gets the wrong amount here; read .kingsmint/base/ for each when that matters for the preview
        fee = sum((p.units.number for p in fixed(x, fees([q.account for q in x.postings[1:]]))[1:]), Decimal(0))
        t = Txn(x.date, bank.units.number + fee, named.get(x.meta["id"], importer.bank_payee(x)), x.narration or "",
                str(x.meta.get("iban", "")),
                vs=str(x.meta.get("vs", "")), ref=str(x.meta.get("ref", "")))
        yield x, t, {k: v for k, v in own.items() if k != iban_of[bank.account]}


def hand_edits(root: Path) -> tuple[set, dict]:
    """The ids of transactions whose postings were edited by hand (reimport keeps them, whatever the rules say), and
    the bank's payee text of those renamed by hand, by id (as `kingsmint rules` reads them)."""
    kept, _ = merge.collect(root)
    edited = {tid for tid, (_, base, _, mine) in kept.items()
              if base and mine != base and merge.parts(mine)[2][1:] != merge.parts(base)[2][1:]}
    named = {tid: (merge.bank_text(*merge.parts(base)[:2]) or '""')[1:-1] for tid, (_, base, _, mine) in kept.items()
             if base and mine != base and merge.parts(mine)[0].get("payee") != merge.parts(base)[0].get("payee")}
    return edited, named


def rule_preview(root: Path, e, entries, account: str) -> dict:
    """What a rule for the counterparty of `e` to `account` would do: the transactions it matches, newest first, each
    with its category now and whether it was edited by hand (then it stays)."""
    if account not in {o.account for o in entries if isinstance(o, Open)}:
        raise EditError(f"No open entry for {account!r}")
    if why := editable(e, entries):
        raise EditError(why)
    regex, label = counterparty(root, e)
    rule = (dt.date(2000, 1, 1), re.compile(regex, re.I), account, [], "new rule")
    try:
        edited, named = hand_edits(root)
    except ValueError as err:
        raise EditError(str(err)) from None
    rows = []
    for x, t, others in statement_txns(entries, named):
        if importer.match(t, others, [rule], x.postings[0].units.currency)[0] != account:
            continue
        shape = fees([q.account for q in x.postings[1:]])
        now = [p.account for p in x.postings[1:] if p not in fixed(x, shape)]
        rows.append({"date": x.date.isoformat(), "payee": x.payee or x.narration, "amount": float(t.amount),
                     "currency": x.postings[0].units.currency, "accounts": now, "hash": hash_entry(x),
                     "id": x.meta["id"], "edited": x.meta["id"] in edited})
    rows.sort(key=lambda r: r["date"], reverse=True)
    return {"counterparty": label, "regex": regex, "rows": rows,
            # not the transaction itself: the change that offers the rule moves it, also while still being saved
            "moves": sum(1 for r in rows if not r["edited"] and r["accounts"] != [account] and r["id"] != e.meta["id"])}


def add_rule(root: Path, e, account: str) -> str:
    """Puts the rule for the counterparty of `e` at the top of rules.beancount, so it wins over the rules there."""
    regex, label = counterparty(root, e)
    path = root / "rules.beancount"
    if not path.exists():
        raise EditError("The ledger has no rules.beancount")
    text = path.read_text(encoding="utf-8")
    ls = merge.lines(text)
    at = next((i for i, line in enumerate(ls) if RULE.match(line)), len(ls))
    if at == len(ls) and ls and not ls[-1].endswith("\n"):
        ls[-1] += "\n"
    quoted = regex.replace("\\", "\\\\").replace('"', '\\"')
    ls[at:at] = [f"; {label}: from the app, {dt.date.today()}\n",
                 f'2000-01-01 custom "rule" "{quoted}" {account}\n', "\n"]
    out = "".join(ls)
    if len(parser.parse_string(out)[1]) > len(parser.parse_string(text)[1]):
        raise EditError("The rule would break rules.beancount; nothing was written")
    write(path, out)
    return f"{label} -> {account}"


RECEIPTS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".webp"}
RECEIPT_MAX = 10 * 1024 * 1024  # the page makes a photo smaller; a scan from the phone is far below this


def slug(text: str) -> str:
    """A file name's part from a text: "Stavebniny Ďurčo" -> "stavebniny-durco"."""
    ascii_ = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "receipt"


def add_cash(root: Path, entries, currency: str, date: str, amount, account: str, payee: str,
             receipt: dict | None = None) -> str:
    """Appends a cash payment to cash.beancount, as its example: `account` gets the amount, Expenses:Cash the
    negative amount. A `receipt` ({name, data}: the file's name and its bytes in base64; the page has them from a
    file, a paste or the iPhone's camera) goes to documents/Expenses/Cash/<date>.<payee>.<ext>, linked with
    `document:`. Returns the version's message."""
    path = root / "cash.beancount"
    if not path.exists():
        raise EditError("The ledger has no cash.beancount")
    try:
        day = dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise EditError(f"Not a date: {date!r}") from None
    try:
        number = Decimal(str(amount).replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise EditError(f"Not an amount: {amount!r}") from None
    if not number.is_finite() or number <= 0:
        raise EditError("The amount is more than 0")
    if not (payee := plain(payee or "", "Payee")):
        raise EditError("Name the payee or what was paid")
    opened = {o.account: o.date for o in entries if isinstance(o, Open)}
    closed = {c.account: c.date for c in entries if isinstance(c, Close)}
    for a in (account, CASH):
        if a not in opened or opened[a] > day or closed.get(a, dt.date.max) <= day:
            raise EditError(f"{a!r} is not open on {day}")
    if not account.startswith("Expenses:") or account == CASH:
        raise EditError("The category is an expense other than Expenses:Cash")
    data = target = None
    if receipt:
        suffix = Path(str(receipt.get("name", ""))).suffix.lower()
        if suffix not in RECEIPTS:
            raise EditError(f"A receipt is one of {', '.join(sorted(RECEIPTS))}")
        try:
            data = base64.b64decode(str(receipt.get("data", "")), validate=True)
        except binascii.Error:
            raise EditError("The receipt's data are not base64") from None
        if not data or len(data) > RECEIPT_MAX:
            raise EditError(f"A receipt has 1 byte to {RECEIPT_MAX // 1024 // 1024} MB")
        folder, n = root / "documents" / "Expenses" / "Cash", 1
        target = folder / f"{day}.{slug(payee)}{suffix}"
        while target.exists():
            n += 1
            target = folder / f"{day}.{slug(payee)}-{n}{suffix}"
    text = path.read_text(encoding="utf-8")
    entry = (f'\n{day} * "{payee}"\n' + (f'  document: "{target.name}"\n' if target else "")
             + f"  {account}  {number} {currency}\n  {CASH}  {-number} {currency}\n")
    out = text + ("" if not text or text.endswith("\n") else "\n") + entry
    if len(parser.parse_string(out)[1]) > len(parser.parse_string(text)[1]):
        raise EditError("The payment would break cash.beancount; nothing was written")
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    write(path, out)
    return f"Cash: {day} {payee} {number} {currency}"
