"""CADRO SaaS — payment webhooks.

The control plane receives payment events from a provider (Stripe, Iyzico, PayTR, ...). A
provider adapter verifies the signature and normalizes the body into a `WebhookPayload`;
`handle_webhook` then moves the tenant's subscription state.

`normalize_generic` is the adapter for CADRO's own signed JSON format (used by tests, by a
billing back office, and as the template for provider-specific adapters).

Rules `handle_webhook` guarantees:
  * a redelivered event (same `event_id`) changes nothing and answers "duplicate";
  * a payment for an invoice that was already applied under another event id is "ignored";
  * the payload's tenant must own the site it names;
  * a cancelled tenant is never revived by a late event;
  * when applying an event fails (e.g. bench is down) the event id is released, so the
    provider's retry is handled again instead of being swallowed as a duplicate.

This module does NOT reconcile amounts against a price list: that needs the billing system.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from cadro.saas import db
from cadro.saas.subscription import SubscriptionState
from cadro.saas.tenant import TenantRecord, TenantStatus, utcnow, validate_site_name

log = logging.getLogger("cadro.saas.webhook")

# A signed request older (or newer) than this is refused, which limits replay of a captured request.
SIGNATURE_TOLERANCE_SECONDS = 300


class WebhookEvent(str, Enum):
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_RENEWED = "subscription.renewed"
    TRIAL_ENDING = "trial.ending"


@dataclass
class WebhookPayload:
    """Normalized webhook payload independent of the payment provider."""

    event: WebhookEvent
    tenant_id: str
    site_name: str
    amount: float | None = None
    currency: str | None = None
    invoice_id: str | None = None
    subscription_id: str | None = None
    raw: dict[str, Any] | None = None  # provider-specific payload for audit
    event_id: str = ""  # the provider's unique id for this delivery; the idempotency key


class InvalidSignature(Exception):
    """The signature or timestamp of a webhook request could not be verified."""


class SiteActions(Protocol):
    """What the control plane can do to a tenant's site."""

    def suspend(self, site: str) -> None: ...

    def reactivate(self, site: str) -> None: ...


class BenchSiteActions:
    """Runs the real `bench` commands (the control plane must run next to the bench)."""

    def suspend(self, site: str) -> None:
        from cadro.saas import manage_tenant

        manage_tenant.suspend(site)

    def reactivate(self, site: str) -> None:
        from cadro.saas import manage_tenant

        manage_tenant.reactivate(site)


# ---------------------------------------------------------------------------
# Signature verification and the generic adapter
# ---------------------------------------------------------------------------


def sign(timestamp: str, raw: bytes, secret: bytes) -> str:
    """HMAC-SHA256 (hex) over "<timestamp>.<body>"."""
    return hmac.new(secret, timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()


def verify_signature(raw: bytes, signature: str, timestamp: str, secret: bytes, now: datetime | None = None) -> None:
    """Raise InvalidSignature unless the request is fresh and correctly signed."""
    if not secret:
        raise InvalidSignature("webhook secret is not configured")
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        raise InvalidSignature("invalid timestamp") from None
    if abs((now or utcnow()).timestamp() - sent_at) > SIGNATURE_TOLERANCE_SECONDS:
        raise InvalidSignature("timestamp outside the tolerance window")
    expected = sign(timestamp, raw, secret)
    if not hmac.compare_digest(expected.encode(), str(signature or "").encode()):
        raise InvalidSignature("signature mismatch")


def _text(data: dict[str, Any], key: str, required: bool = False) -> str | None:
    value = data.get(key)
    if value is None:
        if required:
            raise ValueError(f"'{key}' is required")
        return None
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError(f"'{key}' must be a non-empty string")
    return value


def normalize_generic(
    raw: bytes, signature: str, timestamp: str, secret: bytes, now: datetime | None = None
) -> WebhookPayload:
    """Verify and parse CADRO's own signed JSON webhook.

    Raises InvalidSignature for a bad signature or stale timestamp, ValueError for a malformed body.
    """
    verify_signature(raw, signature, timestamp, secret, now)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")

    amount = data.get("amount")
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float))):
        raise ValueError("'amount' must be a number")

    return WebhookPayload(
        event=WebhookEvent(data.get("event")),
        tenant_id=_text(data, "tenant_id", required=True),
        site_name=_text(data, "site_name", required=True),
        amount=float(amount) if amount is not None else None,
        currency=_text(data, "currency"),
        invoice_id=_text(data, "invoice_id"),
        subscription_id=_text(data, "subscription_id"),
        raw=data,
        event_id=_text(data, "event_id", required=True),
    )


# ---------------------------------------------------------------------------
# Applying events
# ---------------------------------------------------------------------------


def _subscription_state(record: TenantRecord, payment_failed_since: datetime | None) -> SubscriptionState:
    return SubscriptionState(
        status=record.status,
        plan=record.plan.value,
        trial_ends_at=record.trial_ends_at,
        payment_failed_since=payment_failed_since,
    )


def _validate(payload: WebhookPayload) -> None:
    if not payload.event_id:
        raise ValueError("event_id is required")
    if payload.amount is not None and not (0 < payload.amount < math.inf):
        raise ValueError("amount must be a positive number")
    if payload.event == WebhookEvent.PAYMENT_SUCCEEDED and (payload.amount is None or not payload.currency):
        raise ValueError("payment.succeeded needs an amount and a currency")


def handle_webhook(payload: WebhookPayload, actions: SiteActions | None = None) -> str:
    """Apply a verified, normalized event. Returns "applied", "grace", "suspended", "recorded",
    "ignored" or "duplicate". Raises ValueError for a bad payload and LookupError for an unknown site."""
    _validate(payload)
    site = validate_site_name(payload.site_name)
    record = db.get_tenant(site)
    if record is None:
        raise LookupError(f"Tenant with site_name '{site}' is not registered")
    if record.tenant_id != payload.tenant_id:
        raise ValueError("tenant_id does not belong to this site")

    claimed = db.claim_webhook_event(
        payload.event_id, payload.event.value, site, payload.invoice_id, payload.amount, payload.currency
    )
    if not claimed:
        return "duplicate"

    try:
        outcome = _apply(record, payload, actions or BenchSiteActions())
    except BaseException:
        db.release_webhook_event(payload.event_id)
        raise
    db.finish_webhook_event(payload.event_id, outcome)
    log.info("webhook %s %s for %s -> %s", payload.event_id, payload.event.value, site, outcome)
    return outcome


def _suspend(site: str, actions: SiteActions) -> None:
    actions.suspend(site)
    db.set_tenant_status(site, TenantStatus.SUSPENDED)


def _apply(record: TenantRecord, payload: WebhookPayload, actions: SiteActions) -> str:
    site = record.site_name
    event = payload.event

    if record.status == TenantStatus.CANCELLED:
        return "ignored"

    if event in (WebhookEvent.PAYMENT_SUCCEEDED, WebhookEvent.SUBSCRIPTION_RENEWED):
        if payload.invoice_id and db.invoice_was_paid(payload.invoice_id):
            return "ignored"
        db.set_payment_failed_since(site, None)
        if record.status == TenantStatus.SUSPENDED:
            actions.reactivate(site)
        db.set_tenant_status(site, TenantStatus.ACTIVE)
        return "applied"

    if event == WebhookEvent.PAYMENT_FAILED:
        since = record.payment_failed_since or utcnow()
        db.set_payment_failed_since(site, since)
        if _subscription_state(record, since).should_suspend:
            if record.status != TenantStatus.SUSPENDED:
                _suspend(site, actions)
            return "suspended"
        return "grace"

    if event == WebhookEvent.SUBSCRIPTION_CANCELLED:
        if record.status != TenantStatus.SUSPENDED:
            actions.suspend(site)
        db.set_tenant_status(site, TenantStatus.CANCELLED)
        return "applied"

    # subscription.created, trial.ending: kept in the event log; the next payment decides.
    return "recorded"


def sweep_overdue(actions: SiteActions | None = None) -> list[str]:
    """Suspend every trial/active tenant whose trial ended or whose payment grace period ran out.

    Meant to run on a schedule (hourly). Returns the sites it suspended; a site that fails
    is logged and retried on the next run.
    """
    actions = actions or BenchSiteActions()
    suspended = []
    for status in (TenantStatus.TRIAL, TenantStatus.ACTIVE):
        for record in db.list_tenants(status):
            if not _subscription_state(record, record.payment_failed_since).should_suspend:
                continue
            try:
                _suspend(record.site_name, actions)
            except Exception:
                log.exception("could not suspend %s", record.site_name)
                continue
            suspended.append(record.site_name)
    return suspended
