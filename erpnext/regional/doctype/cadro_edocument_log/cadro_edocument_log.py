# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext.regional.turkey.e_document_contract import DocumentStatus, can_transition


class CADROEDocumentLog(Document):
	"""Audit record of one e-document (e-fatura, e-arsiv, e-irsaliye, e-defter) life-cycle.

	Records are written by `erpnext.regional.turkey.e_document_queue`. Nobody gets write or
	delete permission on the form: the log has to stay a trustworthy trail, so the status
	only moves along the contract's state machine and a record can never be deleted.
	"""

	def before_insert(self):
		self.created_on = now_datetime()

	def validate(self):
		if self.is_new():
			if self.status != DocumentStatus.DRAFT.value:
				frappe.throw(_("A new e-document log must start in status 'draft'"))
			return

		before = self.get_doc_before_save()
		if before and before.status != self.status and not can_transition(before.status, self.status):
			frappe.throw(
				_("Cannot transition from '{0}' to '{1}'").format(before.status, self.status),
				title=_("Invalid Status Transition"),
			)

	def on_trash(self):
		frappe.throw(_("E-document logs cannot be deleted"), title=_("Not Allowed"))
