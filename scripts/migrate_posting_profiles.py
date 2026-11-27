#!/usr/bin/env python3
"""Migrate existing Company, Party and Item defaults into GL Posting Profiles.

Dry-run by default; writes CSVs at --out (default cadro-profile-migration/) —
one for the profiles it would create ('profiles.csv'), one for every legacy
default that could not be matched to a profile rule ('unmatched.csv'), and one
for every match found ('matched.csv').

usage:
    cd "$FRAPPE_BENCH_PATH/sites"
    ../env/bin/python /home/frappe/scripts/migrate_posting_profiles.py \
        --site cadro-pilot.localhost [--apply] [--out cadro-profile-migration]

With --apply, the profiles are actually inserted; unmatched rows are still
written but skipped.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import frappe


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--site", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="cadro-profile-migration")
    return parser.parse_args(argv)


def profile_name(company: str, doctype: str) -> str:
    """Stable profile name from company abbreviation."""
    return f"CADRO-MIG-{frappe.scrub(company)[:20]}-{frappe.scrub(doctype)}"


def write_row(writer, row: dict, company: str) -> None:
    row["company"] = company
    writer.writerow(row)


def migrate_company_defaults(company: str, out_dir: Path, apply: bool) -> tuple[int, int]:
    """Turn Company default accounts into profile rules."""
    fields = [
        ("default_income_account", "Sales Invoice", "Sales", "credit", "income_account"),
        ("default_expense_account", "Purchase Invoice", "Purchase", "debit", "expense_account"),
        ("default_payable_account", "Purchase Invoice", "Purchase", "credit", "payable_account"),
        ("default_receivable_account", "Sales Invoice", "Sales", "debit", "receivable_account"),
        ("default_bank_account", "Payment Entry", "Payment Receive", "credit", "bank_account"),
        ("default_cash_account", "Payment Entry", "Payment Pay", "debit", "cash_account"),
    ]

    company_row = frappe.db.get_value("Company", company, [f[0] for f in fields], as_dict=True)
    matched, unmatched = 0, 0
    if not company_row:
        return 0, 0

    for fieldname, doctype, transaction, side, label in fields:
        account = company_row.get(fieldname)
        if not account:
            continue

        profile_doc = {
            "doctype": "GL Posting Profile",
            "profile_name": f"{profile_name(company, doctype)}-{label}",
            "company": company,
            "rules": [
                {
                    "document_type": doctype,
                    "transaction_type": transaction,
                    "priority": 10,
                    "active": 1,
                    side + "_account": account,
                }
            ],
        }

        if apply:
            try:
                frappe.get_doc(profile_doc).insert()
            except frappe.ValidationError:
                pass

        row = {
            "source": "company_defaults",
            "fieldname": fieldname,
            "label": label,
            "doctype": doctype,
            "transaction_type": transaction,
            "side": side,
            "account": account,
            "profile_name": profile_doc["profile_name"],
            "applied": "yes" if apply else "no",
        }

        prof_file = out_dir / "matched.csv"
        fieldnames = ["source", "fieldname", "label", "doctype", "transaction_type", "side", "account", "profile_name", "applied", "company"]
        with open(prof_file, "a", newline="") as fh:
            write_row(csv.DictWriter(fh, fieldnames=fieldnames), row, company)
        matched += 1

    return matched, unmatched


def migrate_party_accounts(company: str, out_dir: Path, apply: bool) -> tuple[int, int, int]:
    """Re-create Party Account rows as profile rules."""
    party_rows = frappe.get_all(
        "Party Account",
        filters={"company": company},
        fields=["parent", "parenttype", "account", "advance_account"],
    )
    matched, unmatched, skipped = 0, 0, 0

    doctype_map = {
        "Customer": ("Sales Invoice", "Sales"),
        "Supplier": ("Purchase Invoice", "Purchase"),
    }

    for row in party_rows:
        doctype, transaction = doctype_map.get(row.parenttype, (None, None))
        if not doctype:
            skipped += 1
            continue

        side = "debit" if row.parenttype == "Customer" else "credit"
        profile_doc = {
            "doctype": "GL Posting Profile",
            "profile_name": f"{profile_name(company, doctype)}-party-{row.parent}",
            "company": company,
            "rules": [
                {
                    "document_type": doctype,
                    "transaction_type": transaction,
                    "party_type": row.parenttype,
                    "party": row.parent,
                    "priority": 5,
                    "active": 1,
                    side + "_account": row.account,
                }
            ],
        }

        if apply:
            try:
                frappe.get_doc(profile_doc).insert()
            except frappe.ValidationError:
                pass

        with open(out_dir / "matched.csv", "a", newline="") as fh:
            write_row(
                csv.DictWriter(fh, fieldnames=["source", "fieldname", "label", "doctype", "transaction_type", "side", "account", "profile_name", "applied", "company"]),
                {
                    "source": "party_account",
                    "fieldname": "account",
                    "label": row.parent,
                    "doctype": doctype,
                    "transaction_type": transaction,
                    "side": side,
                    "account": row.account,
                    "profile_name": profile_doc["profile_name"],
                    "applied": "yes" if apply else "no",
                },
                company,
            )
        matched += 1

    return matched, unmatched, skipped


def migrate_item_defaults(company: str, out_dir: Path, apply: bool) -> tuple[int, int]:
    """Item Default expense / income rows become profile rules."""
    items = frappe.get_all(
        "Item Default",
        filters={"company": company},
        fields=["parent", "expense_account", "income_account"],
    )
    matched, unmatched = 0, 0
    for row in items:
        for side, account_field, doctype, transaction, label in [
            ("debit", "expense_account", "Purchase Invoice", "Purchase", "item-expense"),
            ("credit", "income_account", "Sales Invoice", "Sales", "item-income"),
        ]:
            account = row.get(account_field)
            if not account:
                continue

            profile_doc = {
                "doctype": "GL Posting Profile",
                "profile_name": f"{profile_name(company, doctype)}-{label}-{row.parent}",
                "company": company,
                "rules": [
                    {
                        "document_type": doctype,
                        "transaction_type": transaction,
                        "item": row.parent,
                        "priority": 8,
                        "active": 1,
                        side + "_account": account,
                    }
                ],
            }

            if apply:
                try:
                    frappe.get_doc(profile_doc).insert()
                except frappe.ValidationError:
                    pass

            with open(out_dir / "matched.csv", "a", newline="") as fh:
                write_row(
                    csv.DictWriter(fh, fieldnames=["source", "fieldname", "label", "doctype", "transaction_type", "side", "account", "profile_name", "applied", "company"]),
                    {
                        "source": "item_default",
                        "fieldname": account_field,
                        "label": row.parent,
                        "doctype": doctype,
                        "transaction_type": transaction,
                        "side": side,
                        "account": account,
                        "profile_name": profile_doc["profile_name"],
                        "applied": "yes" if apply else "no",
                    },
                    company,
                )
            matched += 1

    return matched, unmatched


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frappe.init(site=args.site, sites_path=".")
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
        if not company:
            raise SystemExit("No default company")

        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        matched_file = out_dir / "matched.csv"
        if not matched_file.exists():
            with open(matched_file, "w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["source", "fieldname", "label", "doctype", "transaction_type", "side", "account", "profile_name", "applied", "company"])

        unmatched_file = out_dir / "unmatched.csv"
        if not unmatched_file.exists():
            with open(unmatched_file, "w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["source", "fieldname", "label", "account", "reason", "company"])

        print(f"Migrating Company {company} ...")
        cm, cu = migrate_company_defaults(company, out_dir, args.apply)
        pm, pu, ps = migrate_party_accounts(company, out_dir, args.apply)
        im, iu = migrate_item_defaults(company, out_dir, args.apply)

        print(f"{cm} company defaults, {pm} party accounts ({ps} skipped), {im} item defaults migrated.")
        print(f"Unmatched: {cu} company, {pu} party, {iu} item.")
    finally:
        frappe.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
