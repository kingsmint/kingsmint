"""A sample ledger: three years and this year of made-up statements for two accounts, imported like real ones.

Run in a new ledger (the template, title and currency filled in). It adds the accounts and rules, writes the
statements as VUB CSV exports to inbox/, and imports them. All names, IBANs and amounts are invented. The
history has what the reports should show: a pay rise, an energy price jump, a one-off car repair, holidays,
Christmas, subscriptions that get dearer, and a few payments without a rule for the categorize skill.
"""

import calendar
import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

from kingsmint import importer

CURRENT, SAVINGS = "SK3100000000001234567890", "SK5400000000009876543210"
EMPLOYER = "SK8800000000005555666677"

ACCOUNTS = """
; sample ledger: made-up accounts
2000-01-01 open Assets:Me:Bank:VUB:Current EUR
  iban: "{CURRENT}"
2000-01-01 open Assets:Me:Bank:VUB:Savings EUR
  iban: "{SAVINGS}"
; the money before the first statement
{before} pad Assets:Me:Bank:VUB:Current Equity:Opening-Balances
{before} pad Assets:Me:Bank:VUB:Savings Equity:Opening-Balances
2000-01-01 open Income:Salary
  need: "income-linked"
2000-01-01 open Income:Interest
2000-01-01 open Expenses:Housing:Rent
  need: "essential"
2000-01-01 open Expenses:Housing:Energy
  need: "essential"
2000-01-01 open Expenses:Housing:Telecom
  need: "essential"
2000-01-01 open Expenses:Insurance:Property
  need: "essential"
2000-01-01 open Expenses:Food:Groceries
  need: "flexible"
  cut: 0.8
2000-01-01 open Expenses:Food:Restaurants
  need: "optional"
2000-01-01 open Expenses:Transport:Fuel
  need: "flexible"
  cut: 0.6
2000-01-01 open Expenses:Transport:Car
  need: "flexible"
  cut: 0.5
2000-01-01 open Expenses:Health:Pharmacy
  need: "flexible"
  cut: 0.8
2000-01-01 open Expenses:Leisure:Subscriptions
  need: "optional"
2000-01-01 open Expenses:Leisure:Travel
  need: "optional"
2000-01-01 open Expenses:Sport
  need: "optional"
2000-01-01 open Expenses:Gifts
  need: "optional"
"""

RULES = [  # (regex, account); the payees below the rules have none, so they stay uncategorized
    ("Acme Software", "Income:Salary"), ("^Úrok", "Income:Interest"), ("Byty Nova", "Expenses:Housing:Rent"),
    ("Energie Západ", "Expenses:Housing:Energy"), ("Mobil Plus", "Expenses:Housing:Telecom"),
    ("Poisťovňa Istota", "Expenses:Insurance:Property"), ("Lidl|Tesco|Billa", "Expenses:Food:Groceries"),
    ("Bistro|Pizzeria", "Expenses:Food:Restaurants"), ("Slovnaft|OMV", "Expenses:Transport:Fuel"),
    ("Autoservis", "Expenses:Transport:Car"), ("Lekáreň", "Expenses:Health:Pharmacy"),
    ("Netflix|Spotify", "Expenses:Leisure:Subscriptions"), ("Cestovná kancelária", "Expenses:Leisure:Travel"),
    ("Fitness", "Expenses:Sport"), ("Hračky|Kníhkupectvo", "Expenses:Gifts"), ("Výber z bankomatu", "Expenses:Cash"),
    ("Poplatok za vedenie", "Expenses:Bank:Fees"),
]


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def movements(start, end, rnd):
    """{iban: [(date, amount, partner iban, partner name, info)]} for the days start..end."""
    cur, sav = [], []
    first = start.year

    def pay(d, amount, name, info="", iban=""):
        cur.append((d, -Decimal(amount).quantize(Decimal("0.01")), iban, name, info))

    for d in days(start, end):
        y, last = d.year - first, calendar.monthrange(d.year, d.month)[1]
        if d.day == 1:
            pay(d, 650 if y < 2 else 720, "Byty Nova s.r.o.", "Nájom", "SK2000000000001111222233")
            pay(d, 22.90, "Mobil Plus a.s.", "Faktúra")
        if d.day == 3:
            pay(d, 68 if y < 2 else 124, "Energie Západ a.s.", "Záloha elektrina a plyn")  # the energy price jump
        if d.day == 5:
            pay(d, 13.99 if y < 1 else 17.99, "Netflix", "Platba kartou")
            pay(d, 10.99 if y < 2 else 12.99, "Spotify", "Platba kartou")
            if y != 1:  # a year without the gym
                pay(d, 39, "Fitness Aréna", "Členské")
        if d.day == 25:
            amount = 2150 + 120 * y + (800 if d.month == 12 else 0)
            cur.append((d, Decimal(amount), EMPLOYER, "Acme Software s.r.o.", "Mzda"))
        if d.day == 26:
            cur.append((d, Decimal(-400), SAVINGS, "Ja", "Sporenie"))
            sav.append((d, Decimal(400), CURRENT, "Ja", "Sporenie"))
        if d.day == last:
            pay(d, 3.90, "", "Poplatok za vedenie účtu")
            balance = 3000 + sum(x[1] for x in sav)
            sav.append((d, (balance * Decimal("0.02") / 12).quantize(Decimal("0.01")), "", "Úrok", ""))
        if d.weekday() == 5:
            pay(d, rnd.uniform(45, 95) * (1 + 0.04 * y), rnd.choice(["Lidl", "Tesco", "Billa"]), "Platba kartou")
        if d.weekday() in (4, 6) and rnd.random() < 0.45:
            pay(d, rnd.uniform(14, 48), rnd.choice(["Bistro Centrum", "Pizzeria Roma"]), "Platba kartou")
        if d.day in (8, 22):
            pay(d, rnd.uniform(48, 66), rnd.choice(["Slovnaft", "OMV"]), "Platba kartou")
        if d.day == 15:
            pay(d, 100, "", "Výber z bankomatu")
        if d.day == 12 and rnd.random() < 0.3:
            pay(d, rnd.uniform(8, 35), "Lekáreň Zdravie", "Platba kartou")
        if d.month == 3 and d.day == 10:
            pay(d, 310 + 15 * y, "Poisťovňa Istota a.s.", "Poistenie domácnosti")
        if d.month == 7 and d.day == 14:
            pay(d, rnd.uniform(1400, 2100), "Cestovná kancelária Slnko", "Zájazd")
        if d.month == 12 and d.day in (6, 13, 18):
            pay(d, rnd.uniform(80, 160), rnd.choice(["Hračky Svet", "Kníhkupectvo Pod Hradom"]), "Platba kartou")
        if (y, d.month, d.day) == (1, 10, 9):
            pay(d, 980, "Autoservis Rýchly", "Oprava bŕzd a rozvodov")  # a one-off
        if d.day == 19 and rnd.random() < 0.25:  # no rule: the categorize skill asks about these
            pay(d, rnd.uniform(20, 120), rnd.choice(["Eshop Mix s.r.o.", "SumUp *Stánok", "Paypal *Market"]), "Platba kartou")
    return {CURRENT: (Decimal(1500), cur), SAVINGS: (Decimal(3000), sav)}


def csv(opening, rows):  # -> (text, closing balance)
    """A VUB account history export: oldest first, with the running balance."""
    out = ["Dátum zaúčtovania;Suma;Účet partnera;Názov partnera;Doplňujúce informácie;Referencia partnera;Účtovný zostatok"]
    balance = opening
    for d, amount, iban, name, info in rows:
        balance += amount
        num = lambda x: f"{x:.2f}".replace(".", ",")
        out.append(f"{d:%Y%m%d};{num(amount)};{iban};{name};{info};NOTPROVIDED;{num(balance)}")
    return "\n".join(out) + "\n", balance


def write(root, today):
    """The accounts, rules and statements of the sample, from 1 January three years ago to the end of last month."""
    start = dt.date(today.year - 3, 1, 1)
    end = today.replace(day=1) - dt.timedelta(days=1)
    with open(root / "accounts.beancount", "a", encoding="utf-8") as f:
        f.write(ACCOUNTS.format(CURRENT=CURRENT, SAVINGS=SAVINGS, before=start - dt.timedelta(days=1)))
    with open(root / "rules.beancount", "a", encoding="utf-8") as f:
        f.write("\n; sample ledger rules\n" + "".join(f'2000-01-01 custom "rule" "{rx}" {a}\n' for rx, a in RULES))
    (root / "inbox").mkdir(exist_ok=True)
    for iban, (balance, rows) in movements(start, end, random.Random(7)).items():
        (root / "inbox" / f"{iban}.csv").write_text(csv(balance, rows)[0], encoding="utf-8")


def main():
    root = Path.cwd()
    if any((root / "ledger").glob("Assets-*")):
        return print("FAIL this ledger has imported statements; make the sample in a new ledger")
    write(root, dt.date.today())
    importer.main([])
