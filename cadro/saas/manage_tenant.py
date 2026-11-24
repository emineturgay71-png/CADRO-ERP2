#!/usr/bin/env python3
"""CADRO SaaS — tenant lifecycle management.

Suspend / reactivate / offboard a tenant site.  Called by the control plane,
never by the tenant directly.

Usage (from the repository root):
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action suspend
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action reactivate
    python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action offboard \
        --confirm cadro-tenant-001.localhost
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from cadro.saas import db
from cadro.saas.tenant import TenantStatus, validate_site_name


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


def offboard(site: str) -> None:
    """Permanently offboard a tenant — drop the site and its database.

    The caller MUST have already exported the tenant's data and obtained
    confirmation.  This is a destructive operation.
    """
    validate_site_name(site)
    print(f"WARNING: This will PERMANENTLY delete site '{site}' and all its data.")
    bench("drop-site", site, "--force", "--no-backup")
    _record_status(site, TenantStatus.CANCELLED)
    print(f"Site '{site}' offboarded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO SaaS — manage tenant lifecycle")
    parser.add_argument("--site", required=True, help="Site name")
    parser.add_argument("--action", required=True, choices=["suspend", "reactivate", "offboard"])
    parser.add_argument("--confirm", help="For offboard: the site name, repeated, as confirmation")
    args = parser.parse_args()

    if args.action == "offboard" and args.confirm != args.site:
        print("ERROR: offboard requires --confirm <site name>", file=sys.stderr)
        sys.exit(1)

    try:
        if args.action == "suspend":
            suspend(args.site)
        elif args.action == "reactivate":
            reactivate(args.site)
        elif args.action == "offboard":
            offboard(args.site)
    except (ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()