#!/usr/bin/env python3
"""CADRO SaaS site provisioning.

Creates a new Frappe site for a tenant on a bench whose apps are already at the pinned
commits of cadro.baseline.json, installs the apps on the site and registers the tenant
(plan and quota) in the control-plane database. Called by the control plane, never by the
tenant directly.

Usage (from the repository root, with the bench on PATH):
    python -m cadro.saas.provision_site \
        --site cadro-tenant-001.localhost \
        --admin-password-file /run/secrets/admin_password \
        --db-password-file /run/secrets/db_password \
        --plan professional

Passwords are read from files so they do not end up in the shell history.

Requires:
    - frappe-bench installed and on PATH; FRAPPE_BENCH_PATH (default: current directory)
    - apps frappe, erpnext (and optionally payments) checked out at the baseline commits
    - MariaDB reachable at DB_HOST (default localhost)
    - cadro.baseline.json in the repository root
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from cadro.saas import db
from cadro.saas.tenant import PlanTier, validate_site_name

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "cadro.baseline.json"


def bench(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["bench", *args], capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"bench {' '.join(args[:3])} failed: {result.stderr.strip()[-400:]}")
    return result


def resolve_commit(component: str) -> str:
    with BASELINE_PATH.open(encoding="utf-8") as source:
        document = json.load(source)
    for item in document.get("components", []):
        if item.get("name") == component:
            return item["commit"]
    raise SystemExit(f"Component '{component}' not found in {BASELINE_PATH}")


def installed_commit(bench_path: Path, app: str) -> str | None:
    """Commit the bench has checked out for an app, or None when the app is missing."""
    app_dir = bench_path / "apps" / app
    if not (app_dir / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(app_dir), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or None


def check_pins(bench_path: Path) -> None:
    """Refuse to provision on a bench that does not run the baseline commits."""
    for app in ("frappe", "erpnext"):
        expected, actual = resolve_commit(app), installed_commit(bench_path, app)
        if actual != expected:
            raise RuntimeError(f"{app} is at {actual}, the baseline pins {expected}")


def provision(site: str, admin_password: str, db_password: str, plan: PlanTier) -> None:
    """Provision a new tenant site on a bench that runs the evaluation baseline pins."""
    validate_site_name(site)
    bench_path = Path(os.environ.get("FRAPPE_BENCH_PATH", "."))
    check_pins(bench_path)
    if db.get_tenant(site) is not None:
        raise RuntimeError(f"Tenant '{site}' is already registered")

    print(f"Provisioning site '{site}' (plan: {plan.value}) ...")
    bench(
        "new-site",
        site,
        "--db-type", "mariadb",
        "--db-host", os.environ.get("DB_HOST", "localhost"),
        "--db-root-password", db_password,
        "--admin-password", admin_password,
        "--mariadb-root-username", "root",
    )
    bench("--site", site, "install-app", "erpnext")

    if installed_commit(bench_path, "payments") == resolve_commit("payments"):
        bench("--site", site, "install-app", "payments")
    else:
        print("Note: payments is not at the baseline commit; not installed (optional app)")

    db.create_tenant(site, plan)
    print(f"Site '{site}' provisioned and registered.")


def _read_secret(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="CADRO SaaS — provision a tenant site")
    parser.add_argument("--site", required=True, help="Site name (e.g. cadro-tenant-001.localhost)")
    parser.add_argument("--admin-password-file", required=True, help="File holding the Administrator password")
    parser.add_argument("--db-password-file", required=True, help="File holding the MariaDB root password")
    parser.add_argument("--plan", default="starter", choices=[tier.value for tier in PlanTier])
    args = parser.parse_args()
    try:
        provision(
            args.site,
            _read_secret(args.admin_password_file),
            _read_secret(args.db_password_file),
            PlanTier(args.plan),
        )
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(f"ERROR: {error}") from error


if __name__ == "__main__":
    main()