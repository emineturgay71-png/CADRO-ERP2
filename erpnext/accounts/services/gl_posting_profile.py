# Copyright (c) 2026, CADRO and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe
from frappe.utils import getdate
from collections.abc import Mapping
from typing import Any


class PostingResolution:
	def __init__(
		self,
		debit_account: str | None = None,
		credit_account: str | None = None,
		profile: str | None = None,
		rule: str | None = None,
		reason: str = "legacy",
	):
		self.debit_account = debit_account
		self.credit_account = credit_account
		self.profile = profile
		self.rule = rule
		self.reason = reason


def resolve_posting_profile(company: str, context: Mapping[str, Any]) -> PostingResolution:
	"""Resolve a posting profile without changing the legacy posting behavior.

	This resolver is read-only and currently used for dry-run and migration reports. It does not
	override Sales Invoice, Purchase Invoice or Payment Entry account selection.
	"""
	profiles = frappe.get_all(
		"GL Posting Profile",
		filters={"company": company, "disabled": 0},
		fields=["name", "strict_mode", "default_debit_account", "default_credit_account"],
	)
	if not profiles:
		return PostingResolution(reason="no-profile")

	matching_profile = profiles[0]
	for profile in profiles:
		if profile.name == context.get("profile"):
			matching_profile = profile
			break

	rules = frappe.get_all(
		"GL Posting Profile Rule",
		filters={"parent": matching_profile.name, "active": 1, "document_type": context.get("document_type")},
		fields=[
			"name", "idx", "document_type", "party_type", "party", "party_group", "item", "item_group",
			"transaction_type", "tax_category", "currency", "cost_center",
			"debit_account", "credit_account", "priority", "effective_from", "effective_to",
		],
		order_by="priority asc, idx asc",
	)

	for rule in rules:
		if not _rule_is_effective(rule):
			continue
		if not _rule_matches(rule, context):
			continue
		return PostingResolution(
			rule.get("debit_account") or matching_profile.default_debit_account,
			rule.get("credit_account") or matching_profile.default_credit_account,
			matching_profile.name,
			rule.name,
			"profile-rule",
		)

	return PostingResolution(
		matching_profile.default_debit_account,
		matching_profile.default_credit_account,
		matching_profile.name,
		None,
		"profile-default",
	)


def _rule_is_effective(rule) -> bool:
	if rule.get("effective_from") and getdate(rule.effective_from) > getdate():
		return False
	if rule.get("effective_to") and getdate(rule.effective_to) < getdate():
		return False
	return True


def _rule_matches(rule: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
	checks = {
		"party_type": context.get("party_type"),
		"party": context.get("party"),
		"party_group": context.get("party_group"),
		"item": context.get("item"),
		"item_group": context.get("item_group"),
		"transaction_type": context.get("transaction_type"),
		"tax_category": context.get("tax_category"),
		"currency": context.get("currency"),
		"cost_center": context.get("cost_center"),
	}
	for fieldname, actual in checks.items():
		configured = rule.get(fieldname)
		if configured and configured != actual:
			return False
	return True


@frappe.whitelist()
def dry_run_posting_profiles(company: str) -> dict:
	"""Return a read-only migration report for existing Company/Party/Item defaults."""
	if not company:
		frappe.throw("Company is required")

	company_row = frappe.db.get_value(
		"Company", company,
		["default_receivable_account", "default_payable_account", "default_income_account",
		 "default_expense_account", "default_bank_account", "default_cash_account",
		 "round_off_account", "exchange_gain_loss_account"],
		as_dict=True,
	)
	if not company_row:
		frappe.throw("Company not found")

	party_accounts = frappe.get_all(
		"Party Account",
		filters={"company": company},
		fields=["parent", "parenttype", "account", "advance_account"],
	)

	item_defaults = frappe.get_all(
		"Item Default",
		filters={"company": company},
		fields=["parent", "expense_account", "income_account", "buying_cost_center", "selling_cost_center"],
	)

	profiles = frappe.get_all("GL Posting Profile", filters={"company": company}, fields=["name", "disabled", "strict_mode"])

	return {
		"company": company,
		"company_defaults": dict(company_row),
		"party_account_count": len(party_accounts),
		"item_default_count": len(item_defaults),
		"profile_count": len(profiles),
		"party_accounts": party_accounts,
		"item_defaults": item_defaults,
		"profiles": profiles,
		"status": "dry-run",
		"changes_applied": False,
	}


def apply_profile_account(
	company: str,
	legacy_account: str | None,
	context: Mapping[str, Any],
	side: str,
) -> tuple[str | None, str]:
	"""Return (account, reason) for one posting side.

	By default it is fully non-destructive: legacy_account is returned and no profile is
	applied. Only when Accounts Settings enables the posting profile does the resolver run.
	When dry-run is enabled or strict mode is disabled, mismatches are also report-only.
	"""
	settings = frappe.get_single("Accounts Settings")
	if not getattr(settings, "enable_cadro_posting_profile", 0):
		return legacy_account, "feature-disabled"

	resolution = resolve_posting_profile(company, context)
	profile_account = (
		resolution.credit_account if side == "credit" else resolution.debit_account
	)

	if getattr(settings, "cadro_posting_profile_dry_run", 1):
		return legacy_account, resolution.reason

	if profile_account:
		return profile_account, resolution.reason

	strict_profile = False
	if resolution.profile:
		strict_profile = bool(
			frappe.db.get_value("GL Posting Profile", resolution.profile, "strict_mode")
		)
	if strict_profile or getattr(settings, "cadro_posting_profile_strict_mode", 0):
		frappe.throw(
			f"GL Posting Profile could not resolve a {side} account for {context.get('document_type') or 'document'}"
		)

	return legacy_account, resolution.reason
