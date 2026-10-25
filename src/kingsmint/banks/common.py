"""What every parser returns, and helpers for the number and date formats in statements."""

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Txn:
    date: dt.date
    amount: Decimal  # change of the account balance, fee excluded
    payee: str = ""
    narration: str = ""
    iban: str = ""  # counterparty
    fee: Decimal = Decimal(0)


@dataclass
class Statement:
    iban: str
    opening: Decimal  # balance at start of `start`
    closing: Decimal  # balance at end of `end`
    start: dt.date
    end: dt.date
    txns: list[Txn] = field(default_factory=list)
    currency: str = "EUR"
    holder: str = ""  # account owner as printed, e.g. "Example, s.r.o." or "Ing. Novák, Ján"
    type: str = ""  # account type as printed, e.g. "Osobný účet"


def header(rx, text):
    """First group of `rx` in the statement header, or ""."""
    m = re.search(rx, text, re.M)
    return squash(m[1]) if m else ""


def squash(s):
    return re.sub(r"\s+", " ", s).strip()


def merchant(s):  # VUB card text: "Tesco-Bratislav Bratislava08:53", "01/08# Decathlon,BA Ph BRATISLAVA"
    if "--" in s:
        s = s.replace("-", " ")
    return squash(re.sub(r"\d\d:\d\d$", "", re.sub(r"^\d\d/\d\d#", "", s.strip())))


def iban(s):
    return s.replace(" ", "")


def date(s):
    return dt.datetime.strptime(s, "%d.%m.%Y").date()


def sk_num(s):  # "-5.989,27", "-2 500,00"
    return Decimal(re.sub(r"[.\s ]", "", s).replace(",", "."))
