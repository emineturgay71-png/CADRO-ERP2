"""Example e-invoice adapter — demonstrates the provider contract.

This is a CONCRETE EXAMPLE, not the abstract contract.  It simulates an
e-document provider (e.g. Logo, Paraşüt, vb.) by returning deterministic
responses.  Replace with a real provider implementation before production.

Usage:
    adapter = ExampleEInvoiceAdapter(api_key="test-key", base_url="https://sandbox.example.com")
    correlation_id = adapter.send(invoice_dict)
    status = adapter.status(correlation_id)
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from erpnext.regional.turkey.e_document_contract import (
    DocumentStatus,
    EInvoice,
)


class ExampleEInvoiceAdapter(EInvoice):
    """Sandbox e-invoice adapter that simulates provider responses.

    Real adapters MUST:
      - Verify webhook signatures with the provider's shared secret
      - Handle rate limits and retries with exponential backoff
      - Log every request/response for audit
      - Never store API keys in source code
    """

    def __init__(self, api_key: str, base_url: str = "https://sandbox.example.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        # In-memory store for demo purposes only — real adapter polls the provider.
        self._store: dict[str, dict[str, Any]] = {}

    def send(self, invoice_doc: dict[str, Any]) -> str:
        """Simulate sending an e-invoice to the provider."""
        correlation_id = f"EXAMPLE-{uuid.uuid4().hex[:12].upper()}"
        digest = hashlib.sha256(str(invoice_doc).encode()).hexdigest()[:16]

        self._store[correlation_id] = {
            "document": invoice_doc,
            "status": DocumentStatus.QUEUED,
            "digest": digest,
            "sent_at": time.time(),
        }
        # Simulate async processing: auto-advance after 2 seconds
        self._store[correlation_id]["status"] = DocumentStatus.PROCESSING

        return correlation_id

    def cancel(self, correlation_id: str) -> str:
        """Simulate cancellation of an accepted invoice."""
        if correlation_id not in self._store:
            raise ValueError(f"Unknown correlation ID: {correlation_id}")

        record = self._store[correlation_id]
        if record["status"] != DocumentStatus.ACCEPTED:
            raise ValueError(f"Cannot cancel invoice in status: {record['status'].value}")

        cancel_id = f"CANCEL-{uuid.uuid4().hex[:8].upper()}"
        record["status"] = DocumentStatus.CANCELLED
        record["cancel_id"] = cancel_id
        return cancel_id

    def status(self, correlation_id: str) -> DocumentStatus:
        """Simulate polling for invoice status.

        Auto-advances PROCESSING → ACCEPTED after 3 seconds for demo purposes.
        A real adapter makes an HTTP call to the provider's status endpoint.
        """
        if correlation_id not in self._store:
            raise ValueError(f"Unknown correlation ID: {correlation_id}")

        record = self._store[correlation_id]
        if record["status"] == DocumentStatus.PROCESSING:
            elapsed = time.time() - record["sent_at"]
            if elapsed > 3:
                record["status"] = DocumentStatus.ACCEPTED

        return record["status"]

    def download_pdf(self, correlation_id: str) -> bytes | None:
        """Simulate downloading the signed PDF (returns empty bytes in sandbox)."""
        if correlation_id not in self._store:
            return None
        record = self._store[correlation_id]
        if record["status"] != DocumentStatus.ACCEPTED:
            return None
        return b"%PDF-1.4 sandbox e-invoice placeholder"

    def download_ubl(self, correlation_id: str) -> bytes | None:
        """Simulate downloading UBL-TR XML."""
        if correlation_id not in self._store:
            return None
        return f"<Invoice><ID>{correlation_id}</ID></Invoice>".encode()