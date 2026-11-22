#!/usr/bin/env python3
"""CADRO health check for container orchestration.

Validates that the Frappe Bench and its dependencies are responsive.
Exit 0 on healthy, non-zero otherwise. Designed for Docker HEALTHCHECK.

Usage:
    python scripts/healthcheck.py --site cadro-pilot.localhost
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def check_redis(label: str, host: str, port: int) -> bool:
    try:
        result = subprocess.run(
            ["redis-cli", "-h", host, "-p", str(port), "ping"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0 or "PONG" not in result.stdout:
            print(f"FAIL: {label} ({host}:{port}) did not respond with PONG", file=sys.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"FAIL: {label}: {exc}", file=sys.stderr)
        return False


def check_db(site: str) -> bool:
    """Open a MariaDB connection with the site's own credentials (fast, no bench start-up)."""
    bench_path = Path(os.environ.get("FRAPPE_BENCH_PATH", str(Path.home() / "frappe-bench")))
    code = (
        "import json,sys,MySQLdb;"
        "sc=json.load(open(sys.argv[1]));cc=json.load(open(sys.argv[2]));"
        "c=MySQLdb.connect(host=cc.get('db_host','db'),port=int(cc.get('db_port',3306)),"
        "user=sc['db_name'],passwd=sc['db_password'],db=sc['db_name'],connect_timeout=5);"
        "c.cursor().execute('select 1');print('ok')"
    )
    try:
        result = subprocess.run(
            [
                str(bench_path / "env" / "bin" / "python"),
                "-c",
                code,
                str(bench_path / "sites" / site / "site_config.json"),
                str(bench_path / "sites" / "common_site_config.json"),
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"FAIL: database connection for {site}: {exc}", file=sys.stderr)
        return False
    if result.returncode != 0 or "ok" not in result.stdout:
        print(f"FAIL: database connection for {site}: {result.stderr.strip()[-200:]}", file=sys.stderr)
        return False
    return True


def check_web(site: str) -> bool:
    """The web process answers /api/method/ping for the site."""
    request = urllib.request.Request("http://127.0.0.1:8000/api/method/ping", headers={"Host": site})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310 - fixed local URL
            if response.status == 200 and b"pong" in response.read():
                return True
    except (OSError, ValueError) as exc:
        print(f"FAIL: web ping for {site}: {exc}", file=sys.stderr)
        return False
    print(f"FAIL: web ping for {site}: unexpected response", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, help="Frappe site name")
    args = parser.parse_args()

    checks = [
        ("redis-cache", check_redis("cache", os.environ.get("REDIS_CACHE_HOST", "redis-cache"), 6379)),
        ("redis-queue", check_redis("queue", os.environ.get("REDIS_QUEUE_HOST", "redis-queue"), 6379)),
        ("redis-socketio", check_redis("socketio", os.environ.get("REDIS_SOCKETIO_HOST", "redis-socketio"), 6379)),
        ("database", check_db(args.site)),
        ("web", check_web(args.site)),
    ]

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"Health check FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1

    print("Health check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())