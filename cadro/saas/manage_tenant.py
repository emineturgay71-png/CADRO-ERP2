#!/usr/bin/env python3
"""CADRO SaaS — tenant lifecycle management.

Suspend / reactivate / offboard a tenant site.  Called by the control plane,
never by the tenant directly.

Usage:
    python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action suspend
    python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action reactivate
    python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action offboard --confirm YES
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def bench(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["bench", *args], capture_output=True, text=True, check=check)


def suspend(site: str) -> None:
    """Suspend a tenant — disable maintenance mode OFF, but revoke access."""
    print(f"Suspending site '{site}' ...")
    bench("set-config", "-g", "disable_website", "1")
    bench("--site", site, "set-config", "disable_website", "1")
    bench("--site", site, "set-config", "maintenance_mode", "1")
    print(f"Site '{site}' suspended.")


def reactivate(site: str) -> None:
    """Reactivate a previously suspended tenant."""
    print(f"Reactivating site '{site}' ...")
    bench("--site", site, "set-config", "maintenance_mode", "0")
    bench("--site", site, "set-config", "disable_website", "0")
    print(f"Site '{site}' reactivated.")


def offboard(site: str) -> None:
    """Permanently offboard a tenant — drop the site and its database.

    The caller MUST have already exported the tenant's data and obtained
    confirmation.  This is a destructive operation.
    """
    print(f"WARNING: This will PERMANENTLY delete site '{site}' and all its data.")
    print(f"Site: {site}")
    bench("drop-site", site, "--force", "--no-backup")
    print(f"Site '{site}' offboarded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO SaaS — manage tenant lifecycle")
    parser.add_argument("--site", required=True, help="Site name")
    parser.add_argument("--action", required=True, choices=["suspend", "reactivate", "offboard"])
    parser.add_argument("--confirm", help="Confirmation token for destructive actions")
    args = parser.parse_args()

    if args.action == "offboard" and args.confirm != "YES":
        print("ERROR: offboard requires --confirm YES", file=sys.stderr)
        sys.exit(1)

    if args.action == "suspend":
        suspend(args.site)
    elif args.action == "reactivate":
        reactivate(args.site)
    elif args.action == "offboard":
        offboard(args.site)


if __name__ == "__main__":
    main()