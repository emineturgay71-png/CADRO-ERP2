#!/usr/bin/env python3
"""Load test for the bank statement import, on a throw-away CADRO site.

Builds a Turkish-format CSV statement with N rows (separate BORÇ/ALACAK columns, "1.234,56"
amounts, dd.mm.yyyy dates, unique references), attaches it, and runs the real import path:
`Bank Statement Import Log` insert (file parsing and detection) and `insert_transactions()`.
It then imports the same file again (every row must be skipped as a duplicate) and a file that
overlaps the first by half (only the new half may be created), and checks the resulting Bank
Transactions against the totals of the file.

SAFETY: creates data that cannot be removed again (submitted Bank Transactions). The site name
must contain "load"; use --force to override. Run inside the bench container, from the sites dir:

    cd "$FRAPPE_BENCH_PATH/sites"
    ../env/bin/python /home/frappe/scripts/bank_import_load.py --site cadro-load.localhost [--rows 2000]
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
import time
from datetime import date, timedelta

REF_PREFIX = "LOAD-BNK-"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", required=True)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--force", action="store_true", help='allow a site whose name does not contain "load"')
    args = parser.parse_args(argv)
    if "load" not in args.site.lower() and not args.force:
        parser.error('refusing to run on a site whose name does not contain "load" (use --force)')
    if args.rows < 2:
        parser.error("--rows must be at least 2")
    return args


def tr_amount(value: float) -> str:
    """1234.5 -> '1.234,50' (Turkish number format)."""
    text = f"{value:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def build_rows(start: int, count: int, first_day: date, today: date, seed: int):
    """Statement rows for transactions start..start+count-1 plus their expected totals."""
    span = max((today - first_day).days, 1)
    rows, credits, debits = [], 0.0, 0.0
    for number in range(start, start + count):
        rng = random.Random(seed * 1_000_003 + number)  # the same number always yields the same row
        day = first_day + timedelta(days=(number * 7) % (span + 1))
        amount = round(rng.uniform(10, 25000), 2)
        text = tr_amount(amount)
        label = "Müşteri tahsilatı" if number % 2 == 0 else "Tedarikçi ödemesi İşlem"
        credit = number % 2 == 0
        credits += amount if credit else 0
        debits += 0 if credit else amount
        rows.append(
            [day.strftime("%d.%m.%Y"), day.strftime("%d.%m.%Y"), f"{label} {number}", f"{REF_PREFIX}{number:07d}",
             "" if credit else text, text if credit else ""]
        )
    return rows, round(credits, 2), round(debits, 2)


def csv_bytes(rows: list[list[str]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=",")
    writer.writerow(["HESAP HAREKETLERİ", "", "", "", "", ""])
    writer.writerow(["VALÖR TARİHİ", "İŞLEM TARİHİ", "AÇIKLAMA", "REFERANS", "BORÇ", "ALACAK"])
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def ensure_bank_account(frappe, company: str) -> str:
    name = frappe.db.get_value("Bank Account", {"account_name": "LOAD Banka TL", "company": company}, "name")
    if name:
        return name
    if not frappe.db.exists("Bank", "LOAD Banka"):
        frappe.get_doc({"doctype": "Bank", "bank_name": "LOAD Banka"}).insert()
    account = frappe.db.get_value("Account", {"company": company, "account_name": "LOAD Banka TL"}, "name")
    if not account:
        parent = frappe.db.get_value(
            "Account", {"company": company, "is_group": 1, "account_name": ["like", "%BANKALAR%"]}, "name"
        ) or frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_type": "Bank"}, "name")
        if not parent:
            raise SystemExit("No bank group account found in the chart of accounts")
        account = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": "LOAD Banka TL",
                "parent_account": parent,
                "company": company,
                "account_type": "Bank",
                "is_group": 0,
            }
        ).insert().name
    doc = frappe.get_doc(
        {
            "doctype": "Bank Account",
            "account_name": "LOAD Banka TL",
            "bank": "LOAD Banka",
            "is_company_account": 1,
            "account": account,
            "company": company,
        }
    ).insert()
    frappe.db.commit()
    return doc.name


def import_file(frappe, bank_account: str, rows: list[list[str]], label: str):
    """Attach the CSV, create the import log (parses and detects) and import. Returns timings."""
    started = time.monotonic()
    file_doc = frappe.get_doc(
        {"doctype": "File", "file_name": f"load-{label}.csv", "content": csv_bytes(rows), "is_private": 1}
    ).insert()
    log = frappe.get_doc(
        {"doctype": "Bank Statement Import Log", "bank_account": bank_account, "file": file_doc.file_url}
    ).insert()
    parsed = time.monotonic()
    log.insert_transactions()
    frappe.db.commit()
    background = log.status == "In Progress"
    if background:  # a large statement is imported by a worker; wait for it
        deadline = time.monotonic() + 3600
        while time.monotonic() < deadline:
            frappe.db.commit()  # a fresh snapshot for every poll
            if frappe.db.get_value(log.doctype, log.name, "status") != "In Progress":
                break
            time.sleep(1)
        log.reload()
    done = time.monotonic()
    comment = frappe.get_all(
        "Comment", filters={"reference_doctype": log.doctype, "reference_name": log.name, "comment_type": "Info"},
        fields=["content"], order_by="creation desc", limit=1,
    )
    return {
        "label": label,
        "mode": "background" if background else "inline",
        "status": log.status,
        "detected": log.number_of_transactions,
        "debits": round(log.total_debits or 0, 2),
        "credits": round(log.total_credits or 0, 2),
        "parse_s": parsed - started,
        "import_s": done - parsed,
        "comment": comment[0]["content"] if comment else "",
    }


def totals(frappe, bank_account: str) -> tuple[int, float, float]:
    row = frappe.db.sql(
        """select count(*), coalesce(sum(deposit), 0), coalesce(sum(withdrawal), 0) from `tabBank Transaction`
           where bank_account=%s and reference_number like %s and docstatus=1""",
        (bank_account, REF_PREFIX + "%"),
    )[0]
    return int(row[0]), round(float(row[1]), 2), round(float(row[2]), 2)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    import frappe

    frappe.init(site=args.site, sites_path=".")
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
        if not company:
            raise SystemExit("The site has no Company")
        from erpnext.accounts.utils import get_fiscal_year

        today = date.today()
        first_day = max(get_fiscal_year(today, company=company)[1], today - timedelta(days=360))
        bank_account = ensure_bank_account(frappe, company)
        before = totals(frappe, bank_account)
        n = args.rows
        print(f"Bank import load on {args.site}: {n} rows, bank account {bank_account}", flush=True)

        rows_a, cred_a, deb_a = build_rows(0, n, first_day, today, args.seed)
        first = import_file(frappe, bank_account, rows_a, "a")
        after_a = totals(frappe, bank_account)

        again = import_file(frappe, bank_account, rows_a, "a-again")
        after_again = totals(frappe, bank_account)

        rows_b, cred_b, deb_b = build_rows(n // 2, n, first_day, today, args.seed)
        overlap = import_file(frappe, bank_account, rows_b, "b-overlap")
        after_b = totals(frappe, bank_account)

        for result in (first, again, overlap):
            rate = result["detected"] / result["import_s"] if result["import_s"] else 0
            print(
                f"  {result['label']:9} {result['mode']:10} parse {result['parse_s']:6.1f}s  import {result['import_s']:6.1f}s "
                f"({rate:5.0f} rows/s)  detected {result['detected']}  {result['comment']}",
                flush=True,
            )

        ok = True

        def check(name: str, condition: bool) -> None:
            nonlocal ok
            ok = ok and condition
            print(f"  [{'OK' if condition else 'FAIL'}] {name}")

        check("file totals detected correctly", (first["credits"], first["debits"]) == (cred_a, deb_a))
        check("every import ends Completed", all(r["status"] == "Completed" for r in (first, again, overlap)))
        check("first import creates every row", after_a[0] - before[0] == n)
        check("amounts match the file", (round(after_a[1] - before[1], 2), round(after_a[2] - before[2], 2)) == (cred_a, deb_a))
        check("re-importing the same file creates nothing", after_again == after_a)
        check("overlapping file creates only its new half", after_b[0] - after_a[0] == n - (n - n // 2))
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        frappe.destroy()


if __name__ == "__main__":
    sys.exit(main())
