"""CADRO SaaS tenant model.

Defines the tenant (customer) lifecycle independent of ERPNext's Company model.
A tenant owns one Frappe site and may contain multiple ERPNext companies.

IMPORTANT: This module defines data structures and helpers only.  It does NOT
automatically provision sites, bill customers or enforce quotas — those belong
in the CADRO control plane (outside this ERPNext app repo).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class TenantStatus(str, enum.Enum):
    """Life-cycle of a SaaS tenant."""

    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class PlanTier(str, enum.Enum):
    """Subscription tiers a tenant can be on."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantQuota:
    """Resource limits enforced at the tenant level."""

    max_users: int = 5
    max_companies: int = 1
    max_storage_gb: int = 5
    max_api_calls_per_minute: int = 300


# Default quotas per plan tier — adjust after measuring real costs.
PLAN_QUOTAS: dict[PlanTier, TenantQuota] = {
    PlanTier.STARTER: TenantQuota(max_users=5, max_companies=1, max_storage_gb=2, max_api_calls_per_minute=100),
    PlanTier.PROFESSIONAL: TenantQuota(max_users=20, max_companies=3, max_storage_gb=20, max_api_calls_per_minute=600),
    PlanTier.ENTERPRISE: TenantQuota(max_users=100, max_companies=10, max_storage_gb=100, max_api_calls_per_minute=2000),
}


@dataclass
class TenantRecord:
    """Minimal tenant state persisted in the CADRO control plane.

    This is deliberately NOT an ERPNext DocType — the control plane lives
    outside the ERP application so that suspended tenants cannot change
    their own status.
    """

    tenant_id: str
    site_name: str
    plan: PlanTier
    status: TenantStatus = TenantStatus.TRIAL
    trial_ends_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    quota: TenantQuota = field(default_factory=TenantQuota)

    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE

    def can_access(self) -> bool:
        """A tenant can access only when active, or during its trial window."""
        if self.status == TenantStatus.ACTIVE:
            return True
        if self.status == TenantStatus.TRIAL and self.trial_ends_at:
            return datetime.utcnow() < self.trial_ends_at
        return False


def tenant_from_site(site_name: str) -> TenantRecord | None:
    """Resolve a tenant from its site name (stub — real lookup goes to control plane DB)."""
    raise NotImplementedError("Tenant resolution requires the control-plane database")


def enforce_tenant_active(site_name: str) -> None:
    """Raise if the tenant is suspended or its trial expired."""
    tenant = tenant_from_site(site_name)
    if tenant is None:
        return  # unknown site — let the framework 404
    if not tenant.can_access():
        from frappe import _

        raise PermissionError(_("This account is suspended. Please contact support."))