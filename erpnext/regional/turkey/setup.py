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
	if company:
		set_payment_method_accounts(company)


# Ödeme yöntemi -> hesap planındaki yaprak hesap. Çek, vadesi gelene kadar 101.01 Alınan Çekler'de
# bekler; havale/EFT doğrudan banka hesabına girer, nakit TL kasaya.
PAYMENT_METHOD_ACCOUNTS = {
	"Cash": "100.01",
	"Cheque": "101.01",
	"Wire Transfer": "102.01",
	"Bank Draft": "102.01",
}

# Aynı türde birden çok yaprak hesap olduğunda ERPNext'in seçtiği hesap rastgeledir (TL, EUR ve USD
# kasalar; 153 ve 157 stok hesapları). Yeni Türkiye şirketinde varsayılanlar bilinçli seçilir.
COMPANY_DEFAULT_ACCOUNTS = {
	"default_cash_account": "100.01",
	"default_inventory_account": "153.01",
}


def set_company_defaults(doc, method=None):
	"""Company `on_update` kancası: yeni Türkiye şirketinin varsayılan kasa ve stok hesaplarını ayarla.

	ERPNext varsayılanları hesap türüne göre kendisi seçer ve seçim belirsiz kaldığında yanlış hesabı
	(örn. USD KASA) alır; bu kanca ERPNext'in kendi atamasından sonra çalışır.
	"""
	from erpnext.regional import get_country_package

	if not doc.flags.in_insert or get_country_package(doc.country or "") != "turkey":
		return
	for fieldname, number in COMPANY_DEFAULT_ACCOUNTS.items():
		account = frappe.db.get_value(
			"Account", {"company": doc.name, "account_number": number, "is_group": 0}, "name"
		)
		if account and doc.get(fieldname) != account:
			doc.db_set(fieldname, account)


def set_payment_method_accounts(company):
	"""Bağlı hesabı olmayan çek/havale ödeme yöntemlerini şirketin hesaplarına bağla.

	Bağlanmadığında bu yöntemlerle yapılan tahsilat ve ödemeler hesap bulamaz. Mevcut bir bağlantıya
	dokunulmaz.
	"""
	for mode, number in PAYMENT_METHOD_ACCOUNTS.items():
		if not frappe.db.exists("Mode of Payment", mode):
			continue
		account = frappe.db.get_value(
			"Account", {"company": company, "account_number": number, "is_group": 0}, "name"
		)
		if not account:
			continue
		if frappe.db.exists("Mode of Payment Account", {"parent": mode, "company": company}):
			continue
		mode_of_payment = frappe.get_doc("Mode of Payment", mode)
		mode_of_payment.append("accounts", {"company": company, "default_account": account})
		mode_of_payment.save(ignore_permissions=True)


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
