#!/usr/bin/env python3
"""Small HTTP load check for a CADRO site (standard library only).

Logs in once, then drives a few endpoints at increasing concurrency and prints requests per
second, latency percentiles and error counts. It is a smoke-level capacity baseline, not a
substitute for a production load test with realistic data.

usage:
    python scripts/load_smoke.py --base http://127.0.0.1:8001 --site cadro-pilot.localhost \
        --password-file cadro/secrets/admin_password [--seconds 15] [--levels 1,5,20,50]
"""

from __future__ import annotations

import argparse
import http.cookiejar
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINTS = {
    "ping (public)": ("GET", "/api/method/ping", False),
    "login page (public)": ("GET", "/login", False),
    "list Account (auth)": ("GET", "/api/resource/Account?limit_page_length=50&fields=%5B%22name%22%2C%22root_type%22%5D", True),
    "list DocType (auth)": ("GET", "/api/resource/DocType?limit_page_length=100", True),
    # Volume endpoints: meaningful once the site holds many rows (scripts/seed_load_data.py).
    "list Sales Invoice (auth)": (
        "GET",
        "/api/resource/Sales%20Invoice?limit_page_length=50&order_by=posting_date%20desc"
        "&fields=%5B%22name%22%2C%22customer%22%2C%22grand_total%22%2C%22posting_date%22%5D",
        True,
    ),
    "count GL Entry (auth)": ("GET", "/api/method/frappe.client.get_count?doctype=GL%20Entry", True),
}


def make_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login(base: str, site: str, password: str) -> urllib.request.OpenerDirector:
    opener = make_opener()
    data = urllib.parse.urlencode({"usr": "Administrator", "pwd": password}).encode()
    request = urllib.request.Request(base + "/api/method/login", data=data, headers={"Host": site})
    with opener.open(request, timeout=30) as response:
        if response.status != 200:
            raise SystemExit(f"login failed: HTTP {response.status}")
    return opener


def worker(opener, base, site, method, path, deadline, results):
    local = []
    while time.monotonic() < deadline:
        request = urllib.request.Request(base + path, method=method, headers={"Host": site})
        started = time.monotonic()
        try:
            with opener.open(request, timeout=60) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, OSError):
            status = 0
        local.append((time.monotonic() - started, status))
    results.extend(local)


def run_level(opener, base, site, method, path, concurrency, seconds):
    results: list[tuple[float, int]] = []
    deadline = time.monotonic() + seconds
    threads = [
        threading.Thread(target=worker, args=(opener, base, site, method, path, deadline, results))
        for _ in range(concurrency)
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started
    latencies = sorted(latency for latency, _ in results)
    errors = sum(1 for _, status in results if status != 200)
    if not latencies:
        return 0.0, 0.0, 0.0, 0.0, 0
    q = statistics.quantiles(latencies, n=100) if len(latencies) >= 100 else None
    p50 = statistics.median(latencies)
    p95 = q[94] if q else latencies[-1]
    p99 = q[98] if q else latencies[-1]
    return len(latencies) / elapsed, p50, p95, p99, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--site", required=True, help="site name, sent as the Host header")
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--levels", default="1,5,20,50")
    args = parser.parse_args()

    with open(args.password_file, encoding="utf-8") as handle:
        password = handle.read().strip()
    host = args.site if ":" in args.site else args.site + ":8001"
    opener = login(args.base, host, password)

    print(f"{'endpoint':24} {'conc':>4} {'req/s':>8} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'errors':>7}")
    for name, (method, path, needs_auth) in ENDPOINTS.items():
        client = opener if needs_auth else make_opener()
        for level in (int(value) for value in args.levels.split(",")):
            rps, p50, p95, p99, errors = run_level(client, args.base, host, method, path, level, args.seconds)
            print(f"{name:24} {level:>4} {rps:>8.1f} {p50 * 1000:>8.0f} {p95 * 1000:>8.0f} {p99 * 1000:>8.0f} {errors:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
