"""CADRO control-plane — minimal tenant database.

Uses SQLite for the MVP.  Production should use PostgreSQL.
The control-plane database is deliberately separate from the ERPNext
MariaDB instance so that a suspended tenant cannot modify its own status.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cadro.saas.tenant import PlanTier, TenantQuota, TenantRecord, TenantStatus

DB_PATH = Path(__file__).resolve().parents[2] / "cadro" / "control_plane.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create the tenant table if it does not exist — safe to call repeatedly."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id   TEXT PRIMARY KEY,
                site_name   TEXT UNIQUE NOT NULL,
                plan        TEXT NOT NULL DEFAULT 'starter',
                status      TEXT NOT NULL DEFAULT 'trial',
                trial_ends_at TEXT,
                created_at  TEXT NOT NULL,
                max_users   INTEGER NOT NULL DEFAULT 5,
                max_companies INTEGER NOT NULL DEFAULT 1,
                max_storage_gb INTEGER NOT NULL DEFAULT 5,
                max_api_calls_per_minute INTEGER NOT NULL DEFAULT 300
            )
        """
        )


def create_tenant(site_name: str, plan: PlanTier = PlanTier.STARTER) -> TenantRecord:
    """Register a new tenant and return its record."""
    init_db()
    tenant_id = site_name.replace(".", "-")
    quota = PLAN_QUOTAS.get(plan, TenantQuota())
    trial_ends = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO tenants (tenant_id, site_name, plan, status, trial_ends_at, created_at,
                   max_users, max_companies, max_storage_gb, max_api_calls_per_minute)
                   VALUES (?, ?, ?, 'trial', ?, ?, ?, ?, ?, ?)""",
                (tenant_id, site_name, plan.value, trial_ends, created,
                 quota.max_users, quota.max_companies, quota.max_storage_gb, quota.max_api_calls_per_minute),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"Tenant with site_name '{site_name}' already exists") from None

    return TenantRecord(
        tenant_id=tenant_id,
        site_name=site_name,
        plan=plan,
        status=TenantStatus.TRIAL,
        trial_ends_at=datetime.fromisoformat(trial_ends),
        created_at=datetime.fromisoformat(created),
        quota=quota,
    )


def get_tenant(site_name: str) -> TenantRecord | None:
    """Look up a tenant by site name."""
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE site_name = ?", (site_name,)).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def set_tenant_status(site_name: str, status: TenantStatus) -> None:
    """Update a tenant's lifecycle status."""
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE tenants SET status = ? WHERE site_name = ?", (status.value, site_name))


def list_tenants(status: TenantStatus | None = None) -> list[TenantRecord]:
    """List all tenants, optionally filtered by status."""
    init_db()
    with _connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM tenants WHERE status = ? ORDER BY created_at", (status.value,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tenants ORDER BY created_at").fetchall()
    return [_row_to_record(r) for r in rows]


def tenant_from_site(site_name: str) -> TenantRecord | None:
    """Resolve a tenant from its site name."""
    return get_tenant(site_name)


def enforce_tenant_active(site_name: str) -> None:
    """Raise if the tenant is suspended or its trial expired."""
    tenant = get_tenant(site_name)
    if tenant is None:
        return  # unknown site — let the framework 404
    if not tenant.can_access():
        from frappe import _

        raise PermissionError(_("This account is suspended. Please contact support."))


def _row_to_record(row: sqlite3.Row) -> TenantRecord:
    return TenantRecord(
        tenant_id=row["tenant_id"],
        site_name=row["site_name"],
        plan=PlanTier(row["plan"]),
        status=TenantStatus(row["status"]),
        trial_ends_at=datetime.fromisoformat(row["trial_ends_at"]) if row["trial_ends_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
        quota=TenantQuota(
            max_users=row["max_users"],
            max_companies=row["max_companies"],
            max_storage_gb=row["max_storage_gb"],
            max_api_calls_per_minute=row["max_api_calls_per_minute"],
        ),
    )


from cadro.saas.tenant import PLAN_QUOTAS  # noqa: E402