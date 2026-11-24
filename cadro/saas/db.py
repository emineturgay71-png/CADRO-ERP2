"""CADRO control-plane — minimal tenant database.

Uses SQLite for the MVP.  Production should use PostgreSQL.
The control-plane database is deliberately separate from the ERPNext
MariaDB instance so that a suspended tenant cannot modify its own status.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cadro.saas.tenant import PLAN_QUOTAS, PlanTier, TenantQuota, TenantRecord, TenantStatus

# CADRO_CONTROL_PLANE_DB overrides the default location (tests, other deployments).
DB_PATH = Path(os.environ.get("CADRO_CONTROL_PLANE_DB") or Path(__file__).resolve().parents[2] / "cadro" / "control_plane.db")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open the control-plane database; commits on success and always closes."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            yield conn
    finally:
        conn.close()


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
                max_api_calls_per_minute INTEGER NOT NULL DEFAULT 300,
                payment_failed_since TEXT
            )
        """
        )
        # Registries created before the payment columns existed.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tenants)")}
        if "payment_failed_since" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN payment_failed_since TEXT")
        # One row per payment-provider event; the primary key is what makes webhooks idempotent.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id    TEXT PRIMARY KEY,
                event       TEXT NOT NULL,
                site_name   TEXT NOT NULL,
                invoice_id  TEXT,
                amount      REAL,
                currency    TEXT,
                received_at TEXT NOT NULL,
                outcome     TEXT NOT NULL DEFAULT 'processing'
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
    """Update a tenant's lifecycle status. Raises LookupError for an unknown site."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute("UPDATE tenants SET status = ? WHERE site_name = ?", (status.value, site_name))
    if cursor.rowcount == 0:
        raise LookupError(f"Tenant with site_name '{site_name}' is not registered")


def set_payment_failed_since(site_name: str, since: datetime | None) -> None:
    """Record (or clear, with None) when the tenant's payments started failing."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE tenants SET payment_failed_since = ? WHERE site_name = ?",
            (since.isoformat() if since else None, site_name),
        )
    if cursor.rowcount == 0:
        raise LookupError(f"Tenant with site_name '{site_name}' is not registered")


def claim_webhook_event(
    event_id: str,
    event: str,
    site_name: str,
    invoice_id: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
) -> bool:
    """Reserve a provider event id. False means it was already seen (duplicate delivery)."""
    init_db()
    received = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO webhook_events (event_id, event, site_name, invoice_id, amount, currency, received_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, event, site_name, invoice_id, amount, currency, received),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def finish_webhook_event(event_id: str, outcome: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE webhook_events SET outcome = ? WHERE event_id = ?", (outcome, event_id))


def release_webhook_event(event_id: str) -> None:
    """Forget a claimed event whose processing failed, so the provider's retry is handled again."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM webhook_events WHERE event_id = ?", (event_id,))


def invoice_was_paid(invoice_id: str) -> bool:
    """True if a payment for this invoice was already applied under another event id."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM webhook_events WHERE invoice_id = ? AND event IN ('payment.succeeded', 'subscription.renewed') "
            "AND outcome = 'applied'",
            (invoice_id,),
        ).fetchone()
    return row is not None


def list_tenants(status: TenantStatus | None = None) -> list[TenantRecord]:
    """List all tenants, optionally filtered by status."""
    init_db()
    with _connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM tenants WHERE status = ? ORDER BY created_at", (status.value,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tenants ORDER BY created_at").fetchall()
    return [_row_to_record(r) for r in rows]


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
        payment_failed_since=(
            datetime.fromisoformat(row["payment_failed_since"]) if row["payment_failed_since"] else None
        ),
    )