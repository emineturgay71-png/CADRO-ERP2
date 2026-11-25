#!/usr/bin/env python3
"""CADRO SaaS — tenant lifecycle management.

Suspend / reactivate / offboard a tenant site.  Called by the control plane,
never by the tenant directly.

Usage (from the repository root):
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action suspend
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action reactivate
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action export --dest /backups/export
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action offboard \
        --confirm cadro-tenant-001.localhost
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from cadro.saas import db
from cadro.saas.tenant import TenantStatus, utcnow, validate_site_name

# Offboarding drops the site and its database, so the tenant's data must have been exported recently.
EXPORT_MAX_AGE_DAYS = 7


def bench(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["bench", *args], capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"bench {' '.join(args[:3])} failed: {result.stderr.strip()[-400:]}")
    return result


def _record_status(site: str, status: TenantStatus) -> None:
    """Mirror the site state in the control-plane registry (sites created by hand may not be listed)."""
    try:
        db.set_tenant_status(site, status)
    except LookupError:
        print(f"Note: '{site}' is not registered in the control plane; only the site was changed.")


def suspend(site: str) -> None:
    """Suspend a tenant: the site answers with the maintenance page until it is reactivated.

    Only the tenant's own site configuration is changed. Global settings (-g) would affect
    every other tenant on the bench.
    """
    validate_site_name(site)
    print(f"Suspending site '{site}' ...")
    bench("--site", site, "set-config", "maintenance_mode", "1")
    bench("--site", site, "set-config", "disable_website", "1")
    _record_status(site, TenantStatus.SUSPENDED)
    print(f"Site '{site}' suspended.")


def reactivate(site: str) -> None:
    """Reactivate a previously suspended tenant."""
    validate_site_name(site)
    print(f"Reactivating site '{site}' ...")
    bench("--site", site, "set-config", "maintenance_mode", "0")
    bench("--site", site, "set-config", "disable_website", "0")
    _record_status(site, TenantStatus.ACTIVE)
    print(f"Site '{site}' reactivated.")


def export_tenant(site: str, dest: str) -> str:
    """Export the tenant's data (database dump, public and private files, site config) into `dest`.

    The export is the customer's copy of their data and the safety net before offboarding; it is
    recorded in the registry so that `offboard` can require it. Returns the export directory.
    """
    validate_site_name(site)
    stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = Path(dest) / f"{site}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    print(f"Exporting '{site}' to {path} ...")
    bench("--site", site, "backup", "--with-files", "--backup-path", str(path))
    try:
        db.mark_exported(site)
    except LookupError:
        print(f"Note: '{site}' is not registered in the control plane; the export was not recorded.")
    print(f"Export of '{site}' complete: {path}")
    return str(path)


def require_recent_export(site: str, max_age_days: int = EXPORT_MAX_AGE_DAYS) -> None:
    """Raise unless a data export of the tenant is recorded within the last `max_age_days` days."""
    tenant = db.get_tenant(site)
    if tenant is None or tenant.exported_at is None or utcnow() - tenant.exported_at > timedelta(days=max_age_days):
        raise RuntimeError(
            f"no data export of '{site}' within the last {max_age_days} days is recorded; run "
            f"`--action export --dest <dir>` first (or pass --skip-export-check after taking a backup another way)"
        )


def _db_root_password_args() -> list[str]:
    """`--db-root-password` from DB_PASSWORD_FILE: `bench drop-site` otherwise prompts for it.

    The value is visible in the container's process list while the command runs; the control
    plane container has no other users.
    """
    path = os.environ.get("DB_PASSWORD_FILE")
    if not path or not Path(path).is_file():
        return []
    return ["--db-root-password", Path(path).read_text(encoding="utf-8").strip()]


def offboard(site: str, skip_export_check: bool = False) -> None:
    """Permanently offboard a tenant — drop the site and its database.

    Refused unless the tenant's data was exported recently (see `export_tenant`). This is a
    destructive operation.
    """
    validate_site_name(site)
    if not skip_export_check:
        require_recent_export(site)
    print(f"WARNING: This will PERMANENTLY delete site '{site}' and all its data.")
    bench("drop-site", site, "--force", "--no-backup", *_db_root_password_args())
    _record_status(site, TenantStatus.CANCELLED)
    print(f"Site '{site}' offboarded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO SaaS — manage tenant lifecycle")
    parser.add_argument("--site", required=True, help="Site name")
    parser.add_argument("--action", required=True, choices=["suspend", "reactivate", "export", "offboard"])
    parser.add_argument("--confirm", help="For offboard: the site name, repeated, as confirmation")
    parser.add_argument("--dest", help="For export: directory that receives the export")
    parser.add_argument(
        "--skip-export-check", action="store_true", help="For offboard: do not require a recorded data export"
    )
    args = parser.parse_args()

    if args.action == "offboard" and args.confirm != args.site:
        print("ERROR: offboard requires --confirm <site name>", file=sys.stderr)
        sys.exit(1)
    if args.action == "export" and not args.dest:
        print("ERROR: export requires --dest <directory>", file=sys.stderr)
        sys.exit(1)

    try:
        if args.action == "suspend":
            suspend(args.site)
        elif args.action == "reactivate":
            reactivate(args.site)
        elif args.action == "export":
            export_tenant(args.site, args.dest)
        elif args.action == "offboard":
            offboard(args.site, skip_export_check=args.skip_export_check)
    except (ValueError, RuntimeError, FileExistsError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()