# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public v3. See license.txt
"""CADRO Turkish regional setup.

Called by erpnext.setup.doctype.company.company.install_country_fixtures when a
company with country "Türkiye" is created. The Turkish chart of accounts lives in
accounts/doctype/account/chart_of_accounts/verified/tr_chart_of_accounts.json and the
default KDV templates (%20, %10, %1) in setup/setup_wizard/data/country_wise_tax.json.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup(company=None, patch=True):
	"""Entry point called after company creation and on every patch run."""
	make_custom_fields()


def make_custom_fields(update=True):
	fields = get_custom_fields()
	if fields:
		create_custom_fields(fields, ignore_validate=frappe.flags.in_patch, update=update)


def get_custom_fields():
	"""Turkish custom fields on company-level DocTypes.

	Currently an intentional no-op: custom fields are added only when a concrete
	fiscal requirement (e-fatura UUID, GİB status, etc.) is defined with a
	qualified accountant.  The hook remains in place so that future adaptations do
	not require a setup.py restructure.
	"""
	return {}
