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


# Country-specific standard reports and the country they are meant for.
COUNTRY_REPORTS = {
	"IRS 1099": "United States",
	"VAT Audit Report": "South Africa",
	"UAE VAT 201": "United Arab Emirates",
	"Electronic Invoice Register": "Italy",
}


def apply_country_report_visibility(doc=None, method=None):
	"""Disable the country-specific reports unless a company (or the system) is in that country.

	Runs after migrate and whenever a Company is saved, so a company in another country
	switches its reports on again.
	"""
	countries = set(frappe.get_all("Company", pluck="country"))
	countries.add(frappe.db.get_single_value("System Settings", "country"))

	for report, country in COUNTRY_REPORTS.items():
		current = frappe.db.get_value("Report", report, "disabled")
		if current is None:
			continue
		disabled = 0 if country in countries else 1
		if current != disabled:
			frappe.db.set_value("Report", report, "disabled", disabled, update_modified=False)


def sync_system_defaults():
	"""Copy System Settings (language, date/number format, ...) into the global defaults.

	System Settings.on_update does this on save. Values written straight to the database,
	as the CADRO provisioning does, skip it and the desk keeps showing the old defaults.
	"""
	frappe.get_doc("System Settings").set_defaults()
	frappe.db.commit()
	frappe.clear_cache()


def check_deletion_permission(doc, method):
	region = get_region(doc.company)
	if region in ["Nepal"] and doc.docstatus != 0:
		frappe.throw(_("Deletion is not permitted for country {0}").format(region))


def rename_vat_settings(doc, method, old_name: str, new_name: str, merge: bool = False) -> None:
	"""Keep the VAT settings named after their company, as the VAT reports look them up by name."""
	for doctype in ("UAE VAT Settings", "South Africa VAT Settings"):
		if frappe.db.exists(doctype, old_name) and not frappe.db.exists(doctype, new_name):
			rename_doc(doctype, old_name, new_name, force=True, ignore_permissions=True, show_alert=False)
