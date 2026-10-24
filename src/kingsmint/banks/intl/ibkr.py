"""Interactive Brokers, also through introducing brokers such as Lynx: the yearly activity statement CSV."""

import csv
import datetime as dt
from decimal import Decimal


def num(s):  # "1,803", "-0.00005183"
    return Decimal(s.replace(",", ""))


def parse_csv(path, ibkr):
    """Return (cash account, start, end, opening entries, year entries); `ibkr` maps account numbers to cash accounts."""
    headers, sec = {}, {}
    for row in csv.reader(path.open(encoding="utf-8-sig")):
        if len(row) < 3:
            continue
        if row[1] == "Header":
            headers[row[0]] = row[2:]
        elif row[1] == "Data":
            sec.setdefault(row[0], []).append(dict(zip(headers.get(row[0], []), row[2:])))  # 2021 has data rows without a header
    info = {r["Field Name"]: r["Field Value"] for r in sec["Statement"]}
    acct = {r["Field Name"]: r["Field Value"] for r in sec.get("Account Information", [])}
    number = acct.get("Account", "").split(" ")[0]  # "U1234567 (Custom Consolidated)"
    if number not in ibkr:
        raise ValueError(f"no account with ibkr: {number!r} in accounts.beancount")
    cash_acc = ibkr[number]
    sec_acc = cash_acc.rsplit(":", 1)[0] + ":Securities"
    broker = acct.get("Master Name", "IBKR").split(" ")[0]  # introducing broker, e.g. "Lynx B.V."
    start, end = (dt.datetime.strptime(x.strip(), "%B %d, %Y").date() for x in info["Period"].split(" - "))

    # positions at the start = closing positions minus this period's changes
    pos = {}  # (symbol, currency) -> [quantity, cost]
    for r in sec.get("Open Positions", []):
        if r["DataDiscriminator"] == "Summary":
            pos[r["Symbol"], r["Currency"]] = [num(r["Quantity"]), num(r["Cost Basis"])]
    year = []
    for r in sec.get("Trades", []):
        if r["DataDiscriminator"] != "Order":
            continue
        day, cur, qty = r["Date/Time"][:10], r["Currency"], num(r["Quantity"])
        if r["Asset Category"] == "Forex":  # "EUR.USD": qty in EUR, proceeds in USD, commission in EUR
            base, comm = r["Symbol"].split(".")[0], num(r["Comm in EUR"])
            year += [f"{day} * \"{broker}\" \"{'Buy' if qty > 0 else 'Sell'} {abs(qty)} {base} for {cur}\"",
                     f"  {cash_acc}  {qty} {base} @@ {abs(num(r['Proceeds']))} {cur}",
                     f"  {cash_acc}  {num(r['Proceeds'])} {cur}",
                     f"  {cash_acc}  {comm} EUR", f"  Expenses:Investments:Fees  {-comm} EUR", ""]
            continue
        if r["Asset Category"] != "Stocks":
            raise ValueError(f"unsupported trade: {r['Asset Category']} {r['Symbol']}")
        sym = r["Symbol"]
        p = pos.setdefault((sym, cur), [Decimal(0), Decimal(0)])
        p[0] -= qty
        p[1] -= num(r["Basis"])  # buys: +cost, sells: -cost
        cash = num(r["Proceeds"]) + num(r["Comm/Fee"])
        lot = f"{{{{{-num(r['Proceeds'])} {cur}}}}}" if qty > 0 else f"{{}} @ {r['T. Price']} {cur}"  # total cost: price x qty is rounded
        year += [f"{day} * \"{broker}\" \"{'Buy' if qty > 0 else 'Sell'} {abs(qty)} {sym}\"",
                 f"  {sec_acc}  {qty} {sym} {lot}", f"  {cash_acc}  {cash} {cur}",
                 f"  Expenses:Investments:Fees  {-num(r['Comm/Fee'])} {cur}"]
        if qty < 0:
            year.append("  Income:Investments:Gains")
        year.append("")
    for r in sec.get("Corporate Actions", []):
        if r["Asset Category"] != "Stocks":
            continue
        sym, cur, qty, proceeds = r["Description"].split("(")[0], r["Currency"], num(r["Quantity"]), num(r["Proceeds"])
        if not (qty < 0 and proceeds > 0):
            raise ValueError(f"unsupported corporate action: {r['Description']}")
        p = pos.setdefault((sym, cur), [Decimal(0), Decimal(0)])
        p[0] -= qty
        p[1] += proceeds - num(r["Realized P/L"])
        year += [f"{r['Report Date']} * \"{broker}\" \"{r['Description']}\"",
                 f"  {sec_acc}  {qty} {sym} {{}} @ {proceeds / -qty} {cur}", f"  {cash_acc}  {proceeds} {cur}",
                 "  Income:Investments:Gains", ""]
    for r in sec.get("Deposits & Withdrawals", []):
        # "Internal" = between my own IBKR accounts in a consolidated statement; they cancel out
        if r["Currency"].startswith("Total") or r["Description"].startswith("Internal"):
            continue
        year += [f"{r['Settle Date']} * \"{broker}\" \"{r['Description']}\"",
                 f"  {cash_acc}  {num(r['Amount'])} {r['Currency']}", "  Assets:Transit", ""]
    for section, account in [("Interest", "Income:Investments:Interest"), ("Withholding Tax", "Expenses:Taxes:Withholding")]:
        for r in sec.get(section, []):
            if not r["Currency"].startswith("Total"):
                year += [f"{r['Date']} * \"{broker}\" \"{r['Description']}\"",
                         f"  {cash_acc}  {num(r['Amount'])} {r['Currency']}", f"  {account}", ""]

    cash = {}
    for r in sec["Cash Report"]:
        if r["Currency"] != "Base Currency Summary" and r["Currency Summary"] in ("Starting Cash", "Ending Cash"):
            cash.setdefault(r["Currency Summary"], {})[r["Currency"]] = r["Total"]

    opening = [f"{start} * \"{broker}\" \"Opening positions\""]
    opening += [f"  {cash_acc}  {n} {c}" for c, n in cash["Starting Cash"].items() if num(n)]
    opening += [f"  {sec_acc}  {q} {sym} {{{{{cost:.2f} {cur}}}}}" for (sym, cur), (q, cost) in pos.items() if q]
    opening += ["  Equity:Opening-Balances", ""]

    after = end + dt.timedelta(days=1)
    year += [f"{after} balance {cash_acc}  {n} {c}" for c, n in cash["Ending Cash"].items()]
    held = {}
    for r in sec.get("Open Positions", []):
        if r["DataDiscriminator"] == "Summary":
            held[r["Symbol"]] = held.get(r["Symbol"], 0) + num(r["Quantity"])
            year.append(f"{end} price {r['Symbol']}  {r['Close Price']} {r['Currency']}")
    year += [f"{after} balance {sec_acc}  {q} {sym}" for sym, q in held.items()]
    year += [f"{end} price {r['Symbol']}  {r['Current Price']} EUR"
             for r in sec.get("Mark-to-Market Performance Summary", [])
             if r["Asset Category"] == "Forex" and r["Symbol"] != "EUR"]
    return cash_acc, start, end, "\n".join(opening) + "\n", "\n".join(year) + "\n"
