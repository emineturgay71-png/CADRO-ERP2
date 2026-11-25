#!/usr/bin/env python3
"""Seed a throw-away CADRO site with volume data for load testing.

Creates customers, suppliers, service items and submitted Sales Invoices (names prefixed
"LOAD ") on the site's default company, so that list views, reports and the ledger have a
realistic number of rows when scripts/load_smoke.py runs. It is idempotent: it only adds what
is missing to reach the requested counts. It never touches records it did not create.

SAFETY: the data cannot be removed again (submitted invoices). The site name must contain
"load" (e.g. cadro-load.localhost, restored from a backup of the pilot); use --force to override.

Run it inside the bench container with the bench's Python, from the sites directory:

    cd "$FRAPPE_BENCH_PATH/sites"
    ../env/bin/python /home/frappe/scripts/seed_load_data.py --site cadro-load.localhost \
        [--customers 300] [--suppliers 50] [--items 300] [--invoices 1500] [--seed 1]
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta

PREFIX = "LOAD "
COMMIT_EVERY = 50


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", required=True)
    parser.add_argument("--customers", type=int, default=300)
    parser.add_argument("--suppliers", type=int, default=50)
    parser.add_argument("--items", type=int, default=300)
    parser.add_argument("--invoices", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=1, help="random seed, for repeatable data")
    parser.add_argument("--force", action="store_true", help='allow a site whose name does not contain "load"')
    args = parser.parse_args(argv)
    if "load" not in args.site.lower() and not args.force:
        parser.error('refusing to seed a site whose name does not contain "load" (use --force)')
    for name in ("customers", "suppliers", "items", "invoices"):
        if getattr(args, name) < 0:
            parser.error(f"--{name} must not be negative")
    return args


def _existing(frappe, doctype: str, field: str) -> int:
    return frappe.db.count(doctype, {field: ["like", f"{PREFIX}%"]})


def _first_leaf(frappe, doctype: str) -> str:
    name = frappe.db.get_value(doctype, {"is_group": 0}, "name")
    if not name:
        raise SystemExit(f"No leaf {doctype} exists on the site; complete the setup wizard first")
    return name


def _seed_parties(frappe, args: argparse.Namespace) -> None:
    group = _first_leaf(frappe, "Customer Group")
    territory = _first_leaf(frappe, "Territory")
    have = _existing(frappe, "Customer", "customer_name")
    for i in range(have + 1, args.customers + 1):
        frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"{PREFIX}Musteri {i:05d}",
                "customer_type": "Company",
                "customer_group": group,
                "territory": territory,
            }
        ).insert()
        if i % COMMIT_EVERY == 0:
            frappe.db.commit()

    supplier_group = _first_leaf(frappe, "Supplier Group")
    have = _existing(frappe, "Supplier", "supplier_name")
    for i in range(have + 1, args.suppliers + 1):
        frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": f"{PREFIX}Tedarikci {i:05d}",
                "supplier_group": supplier_group,
            }
        ).insert()
        if i % COMMIT_EVERY == 0:
            frappe.db.commit()
    frappe.db.commit()


def _seed_items(frappe, args: argparse.Namespace) -> None:
    group = _first_leaf(frappe, "Item Group")
    uom = frappe.db.get_value("UOM", "Nos") or frappe.db.get_value("UOM", {}, "name")
    have = _existing(frappe, "Item", "item_code")
    for i in range(have + 1, args.items + 1):
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"{PREFIX}Hizmet {i:05d}",
                "item_name": f"{PREFIX}Hizmet {i:05d}",
                "item_group": group,
                "stock_uom": uom,
                "is_stock_item": 0,
            }
        ).insert()
        if i % COMMIT_EVERY == 0:
            frappe.db.commit()
    frappe.db.commit()


def _seed_invoices(frappe, args: argparse.Namespace, company: str, today: date) -> None:
    rng = random.Random(args.seed)
    customers = frappe.get_all("Customer", filters={"customer_name": ["like", f"{PREFIX}%"]}, pluck="name")
    items = frappe.get_all("Item", filters={"item_code": ["like", f"{PREFIX}%"]}, pluck="name")
    if not customers or not items:
        if args.invoices:
            raise SystemExit("Invoices need at least one seeded customer and item")
        return

    have = frappe.db.count("Sales Invoice", {"company": company, "remarks": ["like", f"{PREFIX}%"]})
    # Posting dates stay inside the current fiscal year (earlier years may have no Fiscal Year).
    from erpnext.accounts.utils import get_fiscal_year

    year_start = max(get_fiscal_year(today, company=company)[1], today - timedelta(days=360))
    span = (today - year_start).days
    for i in range(have + 1, args.invoices + 1):
        posting = today - timedelta(days=rng.randint(0, span))
        invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "company": company,
                "customer": rng.choice(customers),
                "posting_date": posting.isoformat(),
                "set_posting_time": 1,
                "due_date": (posting + timedelta(days=30)).isoformat(),
                "remarks": f"{PREFIX}{i:06d}",
                "update_stock": 0,
                "items": [
                    {"item_code": rng.choice(items), "qty": rng.randint(1, 10), "rate": rng.randint(10, 5000)}
                    for _ in range(rng.randint(1, 5))
                ],
            }
        )
        invoice.insert()
        invoice.submit()
        if i % COMMIT_EVERY == 0:
            frappe.db.commit()
            print(f"  invoices: {i}/{args.invoices}", flush=True)
    frappe.db.commit()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    import frappe

    frappe.init(site=args.site, sites_path=".")
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
        if not company:
            raise SystemExit("The site has no Company; complete the setup wizard first")
        print(f"Seeding {args.site} (company: {company}) ...", flush=True)
        _seed_parties(frappe, args)
        _seed_items(frappe, args)
        _seed_invoices(frappe, args, company, date.today())
        print(
            "Done: "
            f"{_existing(frappe, 'Customer', 'customer_name')} customers, "
            f"{_existing(frappe, 'Supplier', 'supplier_name')} suppliers, "
            f"{_existing(frappe, 'Item', 'item_code')} items, "
            f"{frappe.db.count('Sales Invoice', {'remarks': ['like', PREFIX + '%']})} invoices"
        )
    finally:
        frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
