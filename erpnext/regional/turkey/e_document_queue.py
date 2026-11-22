"""E-document integration helpers for Turkish fiscal compliance.

Provides a lightweight queue / status model that works with the abstract
e_document_contract without depending on any concrete provider.

All state transitions are logged so an auditor can trace the full
life-cycle of every e-document independently of the ERP ledger.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext.regional.turkey.e_document_contract import DocumentStatus


EDOC_LOG_DOCTYPE = "CADRO EDocument Log"


def ensure_log_doctype() -> None:
    """Create the CADRO EDocument Log DocType if it does not exist.

    This is intentionally a lightweight custom DocType rather than a
    full-fledged JSON definition — it keeps the Phase 4 surface small
    and avoids migration churn while the provider is still undecided.
    """
    if frappe.db.exists("DocType", EDOC_LOG_DOCTYPE):
        return

    doc = frappe.get_doc(
        {
            "doctype": "DocType",
            "name": EDOC_LOG_DOCTYPE,
            "module": "Regional",
            "custom": 1,
            "istable": 0,
            "track_changes": 1,
            "fields": [
                {
                    "label": "Document Type",
                    "fieldname": "e_document_type",
                    "fieldtype": "Select",
                    "options": "\n".join(
                        ["e-fatura", "e-arsiv", "e-irsaliye", "e-defter"]
                    ),
                    "in_list_view": 1,
                    "reqd": 1,
                },
                {
                    "label": "Direction",
                    "fieldname": "direction",
                    "fieldtype": "Select",
                    "options": "outbound\ninbound",
                    "in_list_view": 1,
                    "reqd": 1,
                },
                {
                    "label": "Status",
                    "fieldname": "status",
                    "fieldtype": "Select",
                    "options": "\n".join(
                        [
                            "draft",
                            "queued",
                            "processing",
                            "accepted",
                            "rejected",
                            "cancelled",
                            "failed",
                        ]
                    ),
                    "default": "draft",
                    "in_list_view": 1,
                    "reqd": 1,
                },
                {
                    "label": "Correlation ID",
                    "fieldname": "correlation_id",
                    "fieldtype": "Data",
                    "read_only": 1,
                    "in_list_view": 1,
                    "description": "Provider-assigned identifier",
                },
                {
                    "label": "ERP Reference Doctype",
                    "fieldname": "reference_doctype",
                    "fieldtype": "Link",
                    "options": "DocType",
                    "reqd": 1,
                },
                {
                    "label": "ERP Reference Name",
                    "fieldname": "reference_name",
                    "fieldtype": "Dynamic Link",
                    "options": "reference_doctype",
                    "reqd": 1,
                },
                {
                    "label": "Provider Response",
                    "fieldname": "provider_response",
                    "fieldtype": "JSON",
                    "read_only": 1,
                },
                {
                    "label": "Provider Error",
                    "fieldname": "provider_error",
                    "fieldtype": "Text",
                    "read_only": 1,
                },
                {"label": "Column Break", "fieldname": "cb_1", "fieldtype": "Column Break"},
                {"label": "Created On", "fieldname": "created_on", "fieldtype": "Datetime", "read_only": 1},
                {"label": "Last Polled", "fieldname": "last_polled", "fieldtype": "Datetime", "read_only": 1},
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
        }
    )
    doc.insert(ignore_permissions=True)


def create_log_entry(
    document_type: str,
    direction: str,
    reference_doctype: str,
    reference_name: str,
) -> str:
    """Create a draft e-document log entry; returns its name."""
    ensure_log_doctype()
    log = frappe.new_doc(EDOC_LOG_DOCTYPE)
    log.e_document_type = document_type
    log.direction = direction
    log.reference_doctype = reference_doctype
    log.reference_name = reference_name
    log.status = "draft"
    log.created_on = now_datetime()
    log.insert(ignore_permissions=True)
    return log.name


def transition_log(name: str, new_status: str, correlation_id: str = "", response: dict | None = None, error: str = "") -> None:
    """Atomically advance the log entry to a new status."""
    valid_transitions: dict[str, set[str]] = {
        "draft": {"queued"},
        "queued": {"processing", "failed"},
        "processing": {"accepted", "rejected", "failed"},
        "accepted": {"cancelled"},
        "rejected": {"queued"},
        "cancelled": set(),
        "failed": {"queued"},
    }
    doc = frappe.get_doc(EDOC_LOG_DOCTYPE, name)
    current = doc.status
    allowed = valid_transitions.get(current, set())
    if new_status not in allowed:
        frappe.throw(
            _("Cannot transition from '{0}' to '{1}'").format(current, new_status),
            title=_("Invalid Status Transition"),
        )

    updates: dict[str, Any] = {"status": new_status}
    if correlation_id:
        updates["correlation_id"] = correlation_id
    if response is not None:
        updates["provider_response"] = json.dumps(response, ensure_ascii=False, default=str)
    if error:
        updates["provider_error"] = error
    if new_status in {"processing", "accepted"}:
        updates["last_polled"] = now_datetime()

    doc.db_set(updates, update_modified=True)
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
    if existing and existing[0].status != "draft":
        return existing[0].correlation_id or existing[0].name
    return None
