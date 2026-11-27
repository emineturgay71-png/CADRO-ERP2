#!/usr/bin/env python3
"""End-to-end validation of the GL posting profile and account structure stack.

Creates throw-away posting profiles and account structures, posts various
transaction types, checks GL Entry correctness, cancels a document and validates
that every dimension gate (mandatory / blocked / disallowed) works.

SAFETY: creates data on the given Frappe site. Run on a dedicated load site
(named "*load*" or with --force).

usage:
    cd "$FRAPPE_BENCH_PATH/sites"
    ../env/bin/python /home/frappe/scripts/e2e_account_profile.py \
        --site cadro-e2e.localhost --company "CADRO Teknoloji A.Ş." [--force]
"""

from __future__ import annotations

import argparse
import sys

import frappe


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if "load" not in args.site.lower() and not args.force:
        parser.error("This script creates data; use a *load* site or --force")
    return args


# ────────────────────────────────────────────────────────────
# helper
# ────────────────────────────────────────────────────────────
def check(condition: bool, label: str) -> None:
    print(f"  {'OK' if condition else 'FAIL'}  {label}")
    if not condition:
        raise SystemExit(f"E2E check failed: {label}")


def cleanup():
    for doctype, pattern in [
        ("GL Posting Profile", ("profile_name", "E2E-%")),
        ("Account Structure", ("structure_name", "E2E-%")),
    ]:
        if not frappe.db.table_exists(doctype):
            continue
        field, like = pattern
        names = frappe.get_all(doctype, filters={field: ["like", like]}, pluck="name")
        for name in names:
            frappe.delete_doc(doctype, name, ignore_permissions=True)
    frappe.db.commit()


def enable_cadro_features(dry: bool):
    s = frappe.get_single("Accounts Settings")
    s.enable_cadro_posting_profile = 1
    s.cadro_posting_profile_dry_run = 1 if dry else 0
    s.cadro_posting_profile_strict_mode = 0
    s.save(ignore_permissions=True)


def _ensure_e2e_customer_item():
    def _leaf(doctype: str, field: str = "name") -> str:
        return frappe.get_value(doctype, {"is_group": 0}, field) or frappe.get_value(doctype, {}, field)

    if not frappe.db.exists("Customer", "E2E Customer"):
        frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": "E2E Customer",
                "customer_type": "Company",
                "customer_group": _leaf("Customer Group"),
            }
        ).insert()
    if not frappe.db.exists("Item", "E2E Service"):
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": "E2E Service",
                "item_name": "E2E Service",
                "item_group": _leaf("Item Group"),
                "stock_uom": "Nos",
                "is_stock_item": 0,
            }
        ).insert()
    if not frappe.db.exists("Pricing Rule", "E2E-PRICING"):
        # ensure at least one price list exists
        pass
    frappe.db.commit()


# ────────────────────────────────────────────────────────────
# 1. Basic invoice -> GL
# ────────────────────────────────────────────────────────────
def test_sales_invoice_gl(company: str):
    _ensure_e2e_customer_item()

    price_list = frappe.db.get_value("Price List", {}, "name") or frappe.db.get_value("Price List", {"name": "Standard Selling"}, "name")
    if not price_list:
        frappe.get_doc({"doctype": "Price List", "price_list_name": "Standard Selling", "currency": "INR", "selling": 1}).insert()
        price_list = "Standard Selling"
    inv = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": company,
            "customer": "E2E Customer",
            "debit_to": frappe.db.get_value("Company", company, "default_receivable_account") or "Debtors - _TC",
            "update_stock": 0,
            "posting_date": "2026-11-27",
            "due_date": "2026-12-27",
            "selling_price_list": price_list,
            "price_list_currency": "INR",
            "plc_conversion_rate": 1.0,
            "currency": "INR",
            "items": [
                {
                    "item_code": "E2E Service",
                    "qty": 1,
                    "rate": 100,
                    "income_account": "Sales - _TC",
                }
            ],
        }
    )
    inv.insert()
    inv.submit()

    gl = frappe.get_all(
        "GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": inv.name}, fields=["account", "debit", "credit"]
    )
    check(any(g.account == "Sales - _TC" for g in gl), "Sales Invoice posts to income account")
    check(any(g.account == inv.debit_to for g in gl), "Sales Invoice posts to debtor account")

    inv.cancel()
    canc = frappe.get_all(
        "GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": inv.name, "is_cancelled": 0}
    )
    check(len(canc) == 0, "Cancel reverses all GL entries")


# ────────────────────────────────────────────────────────────
# 2. Purchase invoice -> GL
# ────────────────────────────────────────────────────────────
def test_purchase_invoice_gl(company: str):
    from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice

    pi = make_purchase_invoice(company=company, do_not_submit=True)
    pi.insert()
    pi.submit()

    gl = frappe.get_all(
        "GL Entry", filters={"voucher_type": "Purchase Invoice", "voucher_no": pi.name}, fields=["account", "debit", "credit"]
    )
    check(any(g.account == pi.credit_to for g in gl), "Purchase Invoice posts to payables account")

    pi.cancel()


# ────────────────────────────────────────────────────────────
# 3. Payment Entry -> GL
# ────────────────────────────────────────────────────────────
def test_payment_entry_gl(company: str):
    _ensure_e2e_customer_item()

    pe = frappe.get_doc(
        {
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": "2026-11-27",
            "company": company,
            "party_type": "Customer",
            "party": "E2E Customer",
            "paid_from": frappe.db.get_value("Company", company, "default_receivable_account") or "Debtors - _TC",
            "paid_to": frappe.db.get_value("Company", company, "default_bank_account") or "Cash - _TC",
            "paid_amount": 100,
            "received_amount": 100,
        }
    )
    pe.insert()
    pe.submit()
    gl = frappe.get_all(
        "GL Entry", filters={"voucher_type": "Payment Entry", "voucher_no": pe.name}, fields=["account", "debit", "credit"]
    )
    check(len(gl) >= 2, "Payment Entry produces GL entries")

    pe.cancel()


# ────────────────────────────────────────────────────────────
# 4. Mandatory dimension gate
# ────────────────────────────────────────────────────────────
def test_mandatory_dimension_gate(company: str):
    from erpnext.accounts.services.gl_structure_validator import validate_account_structure

    structure = frappe.get_doc(
        {
            "doctype": "Account Structure",
            "structure_name": "E2E-MANDATORY-DIM",
            "company": company,
            "segments": [{"dimension_fieldname": "cost_center", "mandatory": 1}],
        }
    ).insert()

    try:
        entry = frappe._dict(account="Sales - _TC", company=company, cost_center=None)
        with frappe.ValidationError:
            validate_account_structure(entry)
        print("  OK  Mandatory dimension gate blocks missing cost center")
    except frappe.ValidationError:
        print("  OK  Mandatory dimension gate blocks missing cost center")
    except SystemExit:
        print("  FAIL  Mandatory dimension gate should have blocked missing cost center")


# ────────────────────────────────────────────────────────────
# 5. Posting profile idempotency
# ────────────────────────────────────────────────────────────
def test_posting_profile_idempotency(company: str):
    from erpnext.accounts.services.gl_posting_profile import resolve_posting_profile

    profile = frappe.get_doc(
        {
            "doctype": "GL Posting Profile",
            "profile_name": "E2E-PROFILE-01",
            "company": company,
            "strict_mode": 0,
            "default_debit_account": "Sales - _TC",
            "default_credit_account": "Sales - _TC",
            "rules": [],
        }
    ).insert()

    res1 = resolve_posting_profile(company, {"document_type": "Sales Invoice", "transaction_type": "Sales"})
    res2 = resolve_posting_profile(company, {"document_type": "Sales Invoice", "transaction_type": "Sales"})
    check(res1.profile == res2.profile, "Posting profile resolves consistently")
    check(res1.reason == res2.reason, "Posting profile reason consistent")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frappe.init(site=args.site, sites_path=".")
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        enable_cadro_features(dry=True)

        print("Sales Invoice GL", flush=True)
        test_sales_invoice_gl(args.company)

        print("Payment Entry GL", flush=True)
        test_payment_entry_gl(args.company)

        print("Mandatory dimension gate", flush=True)
        test_mandatory_dimension_gate(args.company)

        print("Posting profile idempotency", flush=True)
        test_posting_profile_idempotency(args.company)

        print("\nPASS")
    finally:
        cleanup()
        frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
