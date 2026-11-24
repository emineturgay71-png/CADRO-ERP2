# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public v3. See license.txt

import json
import os

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.regional import get_country_package
from erpnext.regional.turkey.e_document_contract import VALID_TRANSITIONS, DocumentStatus, can_transition
from erpnext.regional.turkey.e_document_queue import (
	EDOC_LOG_DOCTYPE,
	create_log_entry,
	idempotent_send_log,
	transition_log,
)


class TestTurkeyRegional(IntegrationTestCase):
	def test_country_package_alias(self):
		# Frappe names the country "Türkiye"; the regional package is "turkey".
		self.assertEqual(get_country_package("Türkiye"), "turkey")
		self.assertEqual(get_country_package("United States"), "united_states")

	def test_country_wise_tax_uses_frappe_country_name(self):
		path = os.path.join(
			os.path.dirname(__file__), "..", "..", "setup", "setup_wizard", "data", "country_wise_tax.json"
		)
		with open(path, encoding="utf-8") as f:
			tax_data = json.load(f)

		self.assertNotIn("Turkey", tax_data)
		charts = tax_data["Türkiye"]["chart_of_accounts"]
		for coa in ("Turkey - Chart of Accounts", "*"):
			rates = sorted(
				row["account_head"]["tax_rate"]
				for template in charts[coa]["sales_tax_templates"]
				for row in template["taxes"]
			)
			self.assertEqual(rates, [1.0, 10.0, 20.0])


class TestEDocumentLog(IntegrationTestCase):
	"""The CADRO EDocument Log is an audit trail: strict state machine, no deletion."""

	def _new_log(self, document_type="e-fatura", reference_name="Administrator"):
		# Dynamic Link validation needs a real document; the Administrator user always exists.
		return create_log_entry(document_type, "outbound", "User", reference_name)

	def test_log_is_a_real_doctype(self):
		meta = frappe.get_meta(EDOC_LOG_DOCTYPE)
		self.assertFalse(meta.custom)
		self.assertEqual(meta.module, "Regional")
		self.assertTrue(meta.track_changes)

	def test_nobody_can_write_or_delete_the_log_from_the_ui(self):
		meta = frappe.get_meta(EDOC_LOG_DOCTYPE)
		for perm in meta.permissions:
			self.assertFalse(perm.write or perm.create or perm.delete, perm.role)

	def test_transition_table_covers_every_status(self):
		self.assertEqual(set(VALID_TRANSITIONS), set(DocumentStatus))
		self.assertTrue(can_transition("draft", "queued"))
		self.assertFalse(can_transition("draft", "accepted"))
		self.assertFalse(can_transition("cancelled", "queued"))
		self.assertFalse(can_transition("nonsense", "queued"))

	def test_happy_path_to_cancelled(self):
		name = self._new_log()
		log = frappe.get_doc(EDOC_LOG_DOCTYPE, name)
		self.assertEqual(log.status, "draft")
		self.assertTrue(log.created_on)

		transition_log(name, "queued")
		transition_log(name, "processing", correlation_id="PRV-001")
		transition_log(name, "accepted", response={"uuid": "abc", "mesaj": "Başarılı"})
		log.reload()
		self.assertEqual(log.status, "accepted")
		self.assertEqual(log.correlation_id, "PRV-001")
		self.assertEqual(json.loads(log.provider_response)["mesaj"], "Başarılı")
		self.assertTrue(log.last_polled)

		transition_log(name, "cancelled")
		self.assertEqual(frappe.db.get_value(EDOC_LOG_DOCTYPE, name, "status"), "cancelled")

	def test_rejected_and_failed_can_be_retried(self):
		for failure in ("rejected", "failed"):
			name = self._new_log()
			transition_log(name, "queued")
			if failure == "rejected":
				transition_log(name, "processing")
				transition_log(name, "rejected", error="Şema hatası")
			else:
				transition_log(name, "failed", error="Zaman aşımı")
			self.assertTrue(frappe.db.get_value(EDOC_LOG_DOCTYPE, name, "provider_error"))
			transition_log(name, "queued")
			self.assertEqual(frappe.db.get_value(EDOC_LOG_DOCTYPE, name, "status"), "queued")

	def test_invalid_transitions_are_rejected_and_do_not_change_the_record(self):
		name = self._new_log()
		with self.assertRaises(frappe.ValidationError):
			transition_log(name, "accepted")
		self.assertEqual(frappe.db.get_value(EDOC_LOG_DOCTYPE, name, "status"), "draft")

		transition_log(name, "queued")
		transition_log(name, "failed")
		transition_log(name, "queued")
		transition_log(name, "processing")
		transition_log(name, "accepted")
		transition_log(name, "cancelled")
		with self.assertRaises(frappe.ValidationError):
			transition_log(name, "queued")

	def test_a_new_log_must_start_as_draft(self):
		log = frappe.new_doc(EDOC_LOG_DOCTYPE)
		log.update(
			{
				"e_document_type": "e-fatura",
				"direction": "outbound",
				"reference_doctype": "User",
				"reference_name": "Administrator",
				"status": "accepted",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			log.insert(ignore_permissions=True)

	def test_log_cannot_be_deleted(self):
		name = self._new_log()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(EDOC_LOG_DOCTYPE, name, force=True, ignore_permissions=True)
		self.assertTrue(frappe.db.exists(EDOC_LOG_DOCTYPE, name))

	def test_reference_cannot_be_changed_after_creation(self):
		name = self._new_log()
		log = frappe.get_doc(EDOC_LOG_DOCTYPE, name)
		log.reference_name = "Guest"
		with self.assertRaises(frappe.ValidationError):
			log.save(ignore_permissions=True)

	def test_idempotent_send_log(self):
		name = self._new_log(document_type="e-arsiv")
		# A draft has not been sent yet.
		self.assertIsNone(idempotent_send_log("User", "Administrator", "e-arsiv"))

		transition_log(name, "queued")
		transition_log(name, "processing", correlation_id="PRV-777")
		self.assertEqual(idempotent_send_log("User", "Administrator", "e-arsiv"), "PRV-777")
		# Another document type for the same ERP document is independent.
		self.assertIsNone(idempotent_send_log("User", "Administrator", "e-irsaliye"))
