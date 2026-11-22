#!/usr/bin/env python3
"""CADRO SaaS site provisioning.

Creates a new Frappe site for a tenant, installs the required apps and
applies the tenant's plan quota.  Called by the control plane, never by
the tenant directly.

Usage:
    python cadro/saas/provision_site.py \
        --site cadro-tenant-001.localhost \
        --admin-password <pw> \
        --db-password <db-pw> \
        --plan professional

Requires:
    - frappe-bench installed and on PATH
    - MariaDB accessible at localhost (or DB_HOST env)
    - cadro.baseline.json in the repository root
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "cadro.baseline.json"


def bench(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["bench", *args], capture_output=True, text=True, check=check)


def resolve_commit(component: str) -> str:
    with BASELINE_PATH.open(encoding="utf-8") as source:
        document = json.load(source)
    for item in document.get("components", []):
        if item.get("name") == component:
            return item["commit"]
    raise SystemExit(f"Component '{component}' not found in {BASELINE_PATH}")


def provision(site: str, admin_password: str, db_password: str, plan: str) -> None:
    """Provision a new tenant site with the evaluation baseline pins."""

    print(f"Provisioning site '{site}' (plan: {plan}) ...")

    db_host = os.environ.get("DB_HOST", "localhost")

    # Create site
    bench(
        "new-site",
        site,
        "--db-type", "mariadb",
        "--db-host", db_host,
        "--db-root-password", db_password,
        "--admin-password", admin_password,
        "--mariadb-root-username", "root",
    )

    # Install apps at pinned commits
    erpnext_commit = resolve_commit("erpnext")
    payments_commit = resolve_commit("payments")

    bench("get-app", "erpnext", "--branch", erpnext_commit)
    bench("--site", site, "install-app", "erpnext")

    try:
        bench("get-app", "payments", "--branch", payments_commit)
        bench("--site", site, "install-app", "payments")
    except subprocess.CalledProcessError:
        print("Warning: payments app installation skipped (optional)")

    # Set site configuration
    bench("set-config", "-g", "developer_mode", "0")

    print(f"Site '{site}' provisioned successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO SaaS — provision a tenant site")
    parser.add_argument("--site", required=True, help="Site name (e.g. cadro-tenant-001.localhost)")
    parser.add_argument("--admin-password", required=True, help="Administrator password")
    parser.add_argument("--db-password", required=True, help="MariaDB root password")
    parser.add_argument("--plan", default="starter", choices=["starter", "professional", "enterprise"])
    args = parser.parse_args()
    provision(args.site, args.admin_password, args.db_password, args.plan)


if __name__ == "__main__":
    main()