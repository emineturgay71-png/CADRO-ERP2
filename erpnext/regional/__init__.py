# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc

from erpnext import get_region

# Country names whose regional package does not follow frappe.scrub(country).
# Frappe names the country "Türkiye", the package is erpnext.regional.turkey.
COUNTRY_PACKAGE_ALIASES = {"Türkiye": "turkey"}


def get_country_package(country: str) -> str:
	"""Return the erpnext.regional sub-package name for a country."""
	return COUNTRY_PACKAGE_ALIASES.get(country) or frappe.scrub(country)


def check_deletion_permission(doc, method):
	region = get_region(doc.company)
	if region in ["Nepal"] and doc.docstatus != 0:
		frappe.throw(_("Deletion is not permitted for country {0}").format(region))


def rename_vat_settings(doc, method, old_name: str, new_name: str, merge: bool = False) -> None:
	"""Keep the VAT settings named after their company, as the VAT reports look them up by name."""
	for doctype in ("UAE VAT Settings", "South Africa VAT Settings"):
		if frappe.db.exists(doctype, old_name) and not frappe.db.exists(doctype, new_name):
			rename_doc(doctype, old_name, new_name, force=True, ignore_permissions=True, show_alert=False)
