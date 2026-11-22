"""CADRO SaaS — payment webhook contract.

Defines the expected shape of payment webhook payloads for the CADRO control
plane.  This is a contract, not an implementation — the actual webhook handler
lives in the control-plane service.

Supported providers (planned): Stripe, Iyzico, PayTR
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class WebhookEvent(str, Enum):
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_RENEWED = "subscription.renewed"
    TRIAL_ENDING = "trial.ending"


@dataclass
class WebhookPayload:
    """Normalized webhook payload independent of the payment provider.

    The control-plane webhook handler receives this payload after the
    provider-specific adapter normalizes it.
    """

    event: WebhookEvent
    tenant_id: str
    site_name: str
    amount: float | None = None
    currency: str | None = None
    invoice_id: str | None = None
    subscription_id: str | None = None
    raw: dict[str, Any] | None = None  # provider-specific payload for audit


# Provider adapters implement this signature:
#
#   def normalize(raw_payload: bytes, signature: str) -> WebhookPayload:
#       ...
#
# The adapter MUST:
#   1. Verify the webhook signature using the provider's shared secret
#   2. Parse the provider-specific payload
#   3. Return a normalized WebhookPayload
#
# The control plane MUST:
#   1. Look up the tenant from the payload's tenant_id/site_name
#   2. Reconcile the amount/invoice against the billing system
#   3. Transition the tenant's subscription state
#   4. Return 200 OK (idempotent — same payload = same result)