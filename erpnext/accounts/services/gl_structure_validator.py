# Copyright (c) 2026, CADRO and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _


def validate_account_structure(gl_entry):
	"""Validate one GL entry against the Company's active Account Structures."""
	from erpnext.accounts.doctype.account_structure.account_structure import AccountStructure

	company = gl_entry.get("company") or gl_entry.company
	account = gl_entry.get("account") or gl_entry.account

	structures = frappe.get_all(
		"Account Structure",
		filters={"company": company, "disabled": 0},
		fields=["name"],
	)

	account_root = None
	account_report = None

	for structure in structures:
		doc = frappe.get_doc("Account Structure", structure.name)
		for segment in doc.segments:
			if not segment.get("dimension_fieldname"):
				continue
			must_have = False
			if segment.get("mandatory"):
				must_have = True
			if account_report is None:
				account_report = frappe.get_cached_value(
					"Account", account, "report_type"
				)
			if account_report == "Balance Sheet" and segment.get("mandatory_for_bs"):
				must_have = True
			if account_report == "Profit and Loss" and segment.get("mandatory_for_pl"):
				must_have = True

			value = gl_entry.get(segment.dimension_fieldname)

			if must_have and not value:
				label = segment.get("dimension_label") or segment.dimension_fieldname
				frappe.throw(
					_("Account {0} requires dimension {1}").format(
						account, label
					)
				)

			if segment.allowed_values and value:
				allowed = {v.strip() for v in segment.allowed_values.split(",") if v.strip()}
				if value not in allowed:
					frappe.throw(
						_("Dimension value {0} is not allowed for account {1}").format(
							value, account
						)
					)

		for segment in doc.segments:
			if not segment.blocked_dimensions:
				continue
			blocked = {b.strip() for b in segment.blocked_dimensions.split(",") if b.strip()}
			my_value = gl_entry.get(segment.dimension_fieldname)
			if not my_value:
				continue
			for other_segment in doc.segments:
				if other_segment is segment:
					continue
				if other_segment.dimension_fieldname in blocked:
					other_value = gl_entry.get(other_segment.dimension_fieldname)
					if other_value:
						frappe.throw(
							_("Dimension {0}={1} cannot be combined with {2}={3}").format(
								segment.dimension_label or segment.dimension_fieldname,
								my_value,
								other_segment.dimension_label or other_segment.dimension_fieldname,
								other_value,
							)
						)
