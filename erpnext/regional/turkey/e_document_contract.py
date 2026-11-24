"""Provider-independent e-document adapter contract for Turkish fiscal compliance.

This module defines the interface that every e-belge / e-fatura provider
integration must implement.  No provider-specific logic, API keys or URLs
belong here — those live in their own adapter package.

IMPORTANT: This contract does NOT claim official GİB compliance.  Every
implementation must be validated by a certified fiscal consultant before
use with real e-documents.
"""

from __future__ import annotations

import abc
import enum
from typing import Any


class DocumentDirection(str, enum.Enum):
    """Whether the e-document is sent or received."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class DocumentType(str, enum.Enum):
    """Turkish e-document types supported by the contract."""

    E_FATURA = "e-fatura"
    E_ARSIV = "e-arsiv"
    E_IRSALIYE = "e-irsaliye"
    E_DEFTER = "e-defter"


class DocumentStatus(str, enum.Enum):
    """Life-cycle states an e-document can be in."""

    DRAFT = "draft"             # preparing, not yet submitted to provider
    QUEUED = "queued"           # submitted, waiting for provider processing
    PROCESSING = "processing"   # provider is enriching / signing
    ACCEPTED = "accepted"       # successfully delivered / registered
    REJECTED = "rejected"       # provider or GİB rejected
    CANCELLED = "cancelled"     # successfully cancelled after acceptance
    FAILED = "failed"           # unrecoverable technical error


# Allowed status changes. Everything else is rejected, so an auditor can rely on the log.
VALID_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.DRAFT: {DocumentStatus.QUEUED},
    DocumentStatus.QUEUED: {DocumentStatus.PROCESSING, DocumentStatus.FAILED},
    DocumentStatus.PROCESSING: {DocumentStatus.ACCEPTED, DocumentStatus.REJECTED, DocumentStatus.FAILED},
    DocumentStatus.ACCEPTED: {DocumentStatus.CANCELLED},
    DocumentStatus.REJECTED: {DocumentStatus.QUEUED},
    DocumentStatus.CANCELLED: set(),
    DocumentStatus.FAILED: {DocumentStatus.QUEUED},
}


def can_transition(current: str, new: str) -> bool:
    """True if a log may move from status ``current`` to ``new`` (plain strings or enum values)."""
    try:
        return DocumentStatus(new) in VALID_TRANSITIONS[DocumentStatus(current)]
    except (ValueError, KeyError):
        return False


class EInvoice(abc.ABC):
    """Abstract e-fatura / e-arsiv invoice adapter."""

    @abc.abstractmethod
    def send(self, invoice_doc: dict[str, Any]) -> str:
        """Submit an invoice to the e-document provider.

        Returns the provider's correlation ID.  The caller is responsible
        for recording this ID and polling for the final status.
        """

    @abc.abstractmethod
    def cancel(self, correlation_id: str) -> str:
        """Request cancellation of a previously accepted e-invoice.

        Returns a new correlation ID for the cancellation request.
        """

    @abc.abstractmethod
    def status(self, correlation_id: str) -> DocumentStatus:
        """Poll the current status of an e-invoice from its correlation ID."""

    @abc.abstractmethod
    def download_pdf(self, correlation_id: str) -> bytes | None:
        """Download the signed / stamped PDF (when available)."""

    @abc.abstractmethod
    def download_ubl(self, correlation_id: str) -> bytes | None:
        """Download the UBL-TR XML representation."""


class EDespatch(abc.ABC):
    """Abstract e-irsaliye adapter."""

    @abc.abstractmethod
    def send(self, despatch_doc: dict[str, Any]) -> str:
        """Submit an e-irsaliye."""

    @abc.abstractmethod
    def status(self, correlation_id: str) -> DocumentStatus:
        """Poll the status."""


class ELedger(abc.ABC):
    """Abstract e-defter adapter."""

    @abc.abstractmethod
    def submit(self, period: str, data: bytes) -> str:
        """Submit e-defter data for a fiscal period (YYYYMM)."""

    @abc.abstractmethod
    def status(self, correlation_id: str) -> DocumentStatus:
        """Poll the status."""


# Registry of provider adapters.  At Phase 4 only the interface is defined;
# a concrete provider is selected before Phase 4 acceptance.
ADAPTERS: dict[str, EInvoice | EDespatch | ELedger] = {}
