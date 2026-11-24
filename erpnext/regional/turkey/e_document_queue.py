"""E-document integration helpers for Turkish fiscal compliance.

Provides a lightweight queue / status model that works with the abstract
e_document_contract without depending on any concrete provider.

All state transitions are logged so an auditor can trace the full
life-cycle of every e-document independently of the ERP ledger. The log is the
"CADRO EDocument Log" DocType (erpnext/regional/doctype/cadro_edocument_log);
its controller enforces the state machine and refuses deletion.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext.regional.turkey.e_document_contract import DocumentStatus


EDOC_LOG_DOCTYPE = "CADRO EDocument Log"


def create_log_entry(
    document_type: str,
    direction: str,
    reference_doctype: str,
    reference_name: str,
) -> str:
    """Create a draft e-document log entry; returns its name."""
    log = frappe.new_doc(EDOC_LOG_DOCTYPE)
    log.e_document_type = document_type
    log.direction = direction
    log.reference_doctype = reference_doctype
    log.reference_name = reference_name
    log.status = DocumentStatus.DRAFT.value
    log.insert(ignore_permissions=True)
    return log.name


def transition_log(name: str, new_status: str, correlation_id: str = "", response: dict | None = None, error: str = "") -> None:
    """Advance the log entry to a new status.

    The DocType controller rejects transitions the contract does not allow
    ("Invalid Status Transition"); the change is saved with version tracking.
    """
    doc = frappe.get_doc(EDOC_LOG_DOCTYPE, name)
    current = doc.status

    doc.status = new_status
    if correlation_id:
        doc.correlation_id = correlation_id
    if response is not None:
        doc.provider_response = json.dumps(response, ensure_ascii=False, default=str)
    if error:
        doc.provider_error = error
    if new_status in {DocumentStatus.PROCESSING.value, DocumentStatus.ACCEPTED.value}:
        doc.last_polled = now_datetime()

    doc.save(ignore_permissions=True)
    doc.add_comment("Info", _("Status changed: {0} → {1}").format(current, new_status))


def idempotent_send_log(
    reference_doctype: str,
    reference_name: str,
    document_type: str,
) -> str | None:
    """If a log entry already exists for this ERP document that was successfully
    submitted (status != draft), return its correlation_id to prevent double sends."""
    existing = frappe.get_all(
        EDOC_LOG_DOCTYPE,
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "e_document_type": document_type,
        },
        fields=["name", "status", "correlation_id"],
        order_by="created_on desc",
        limit=1,
    )
    if existing and existing[0].status != DocumentStatus.DRAFT.value:
        return existing[0].correlation_id or existing[0].name
    return None
