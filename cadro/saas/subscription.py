"""CADRO SaaS subscription and entitlement model.

Thread-safe context manager that gates API calls behind the tenant's current
subscription state.  Designed to be called from Frappe whitelisted methods
without changing every endpoint individually.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from erpnext.cadro.saas.tenant import TenantStatus, enforce_tenant_active


class QuotaExceededError(Exception):
    """Raised when a tenant exceeds its plan quota."""


class SubscriptionExpiredError(Exception):
    """Raised when a tenant's trial or subscription has ended."""


@dataclass
class SubscriptionState:
    """Snapshot of a tenant's subscription at a point in time."""

    status: TenantStatus
    plan: str
    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    payment_failed_since: datetime | None = None

    @property
    def is_grace_period(self) -> bool:
        """True when payment is overdue but within the 7-day grace window."""
        if not self.payment_failed_since:
            return False
        return (datetime.now(timezone.utc) - self.payment_failed_since).days < 7

    @property
    def should_suspend(self) -> bool:
        """True when the tenant MUST be suspended now."""
        if self.status == TenantStatus.CANCELLED:
            return True
        if self.payment_failed_since and not self.is_grace_period:
            return True
        if self.trial_ends_at and datetime.now(timezone.utc) > self.trial_ends_at and self.status == TenantStatus.TRIAL:
            return True
        return False


def require_active_subscription(fn):
    """Decorator for Frappe whitelisted methods that gates on subscription state.

    Usage:
        @frappe.whitelist()
        @require_active_subscription
        def my_endpoint():
            ...
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        import frappe

        site_name = frappe.local.site
        try:
            enforce_tenant_active(site_name)
        except PermissionError:
            frappe.throw(
                frappe._("Your account is suspended or your trial has ended. Please contact support."),
                title=frappe._("Account Suspended"),
            )
        return fn(*args, **kwargs)

    return wrapper


def webhook_payment_succeeded(site_name: str, amount: float, currency: str, invoice_id: str) -> None:
    """Handle a successful payment webhook.

    THIS IS A STUB — the real implementation goes into the CADRO control-plane
    service that owns the tenant database.  The stub exists so that Phase 5
    documents the contract without wiring a specific payment provider.
    """
    raise NotImplementedError("Control-plane payment handling is not implemented yet")


def webhook_payment_failed(site_name: str, reason: str) -> None:
    """Handle a failed payment — triggers dunning after grace period."""
    raise NotImplementedError("Control-plane payment handling is not implemented yet")