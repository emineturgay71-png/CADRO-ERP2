# Copyright (c) 2026, CADRO and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GLPostingProfile(Document):
	def validate(self):
		if not self.company:
			frappe.throw(_("Company is required"))

		seen = set()
		for rule in self.rules:
			if not rule.document_type:
				frappe.throw(_("Every posting rule needs a Document Type"))

			if rule.party_group and rule.party_group == "":
				rule.party_group = None

			for fieldname in ("debit_account", "credit_account"):
				account = rule.get(fieldname)
				if account:
					company = frappe.db.get_value("Account", account, "company")
					if company and company != self.company:
						frappe.throw(_("Row {0}: Account {1} does not belong to Company {2}").format(rule.idx, account, self.company))

			key = (
				rule.document_type, rule.party_type, rule.party, rule.party_group,
				rule.item, rule.item_group, rule.transaction_type, rule.tax_category,
				rule.currency, rule.cost_center,
			)
			if key in seen:
				frappe.throw(_("Row {0}: Duplicate posting rule for the same mapping").format(rule.idx))
			seen.add(key)
