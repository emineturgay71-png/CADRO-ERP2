#!/usr/bin/env python3
"""Small HTTP load check for a CADRO site (standard library only).

Logs in once, then drives a few endpoints at increasing concurrency and prints requests per
second, latency percentiles and error counts. It is a smoke-level capacity baseline, not a
substitute for a production load test with realistic data.

usage:
    python scripts/load_smoke.py --base http://127.0.0.1:8001 --site cadro-pilot.localhost \
        --password-file cadro/secrets/admin_password [--seconds 15] [--levels 1,5,20,50]

Scenarios (--scenario): `read` (default; list and count endpoints), `reports` (General Ledger,
Accounts Receivable, Trial Balance through the report API), `write` (each request inserts and
submits a Sales Invoice, i.e. writes GL entries) and `write-stock` (the same with update_stock, so
every request also writes stock ledger entries and updates shared Bin rows). `reports` and the
write scenarios need --company; the write scenarios need the customers and items of
scripts/seed_load_data.py and, because they create data that cannot be removed again, refuse a
site whose name does not contain "load" (override with --force).
"""

from __future__ import annotations

import argparse
import collections
import http.cookiejar
import json
import random
import re
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

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


ERROR_SAMPLES: dict[int, str] = {}


def worker(opener, base, site, method, path, deadline, results, make_body=None, headers=None):
    local = []
    while time.monotonic() < deadline:
        request_headers = {"Host": site, **(headers or {})}
        body = None
        if make_body is not None:
            body = make_body()
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(base + path, data=body, method=method, headers=request_headers)
        started = time.monotonic()
        try:
            with opener.open(request, timeout=120) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            ERROR_SAMPLES.setdefault(status, error.read(600).decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError):
            status = 0
        local.append((time.monotonic() - started, status))
    results.extend(local)


def run_level(opener, base, site, method, path, concurrency, seconds, make_body=None, headers=None):
    results: list[tuple[float, int]] = []
    deadline = time.monotonic() + seconds
    threads = [
        threading.Thread(target=worker, args=(opener, base, site, method, path, deadline, results, make_body, headers))
        for _ in range(concurrency)
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started
    latencies = sorted(latency for latency, _ in results)
    failures = collections.Counter(status for _, status in results if status != 200)
    errors = sum(failures.values())
    if not latencies:
        return 0.0, 0.0, 0.0, 0.0, 0, failures
    q = statistics.quantiles(latencies, n=100) if len(latencies) >= 100 else None
    p50 = statistics.median(latencies)
    p95 = q[94] if q else latencies[-1]
    p99 = q[98] if q else latencies[-1]
    return len(latencies) / elapsed, p50, p95, p99, errors, failures


def api_get(opener, base, host, path):
    request = urllib.request.Request(base + path, headers={"Host": host})
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read())


def csrf_token(opener, base, host) -> str:
    """The desk page embeds the session's CSRF token; a session POST needs it in a header."""
    request = urllib.request.Request(base + "/app", headers={"Host": host})
    with opener.open(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")
    match = re.search(r'csrf_token"?\s*[:=]\s*"([^"]+)"', page)
    if not match:
        raise SystemExit("could not find the CSRF token on /app")
    return match.group(1)


def report_path(name: str, filters: dict) -> str:
    query = urllib.parse.urlencode({"report_name": name, "filters": json.dumps(filters)})
    return f"/api/method/frappe.desk.query_report.run?{query}"


def report_endpoints(opener, base, host, company):
    years = api_get(
        opener, base, host,
        "/api/resource/Fiscal%20Year?fields=%5B%22name%22%2C%22year_start_date%22%2C%22year_end_date%22%5D"
        "&order_by=year_start_date%20desc&limit_page_length=1",
    )["data"]
    if not years:
        raise SystemExit("the site has no Fiscal Year")
    year = years[0]
    today = date.today().isoformat()
    return {
        "report General Ledger": ("GET", report_path("General Ledger", {
            "company": company, "from_date": year["year_start_date"], "to_date": today,
            "group_by": "Group by Voucher (Consolidated)"}), True, None),
        "report Accounts Receivable": ("GET", report_path("Accounts Receivable", {
            "company": company, "report_date": today, "ageing_based_on": "Due Date",
            "range": "30, 60, 90, 120"}), True, None),
        "report Trial Balance": ("GET", report_path("Trial Balance", {
            "company": company, "fiscal_year": year["name"], "from_date": year["year_start_date"],
            "to_date": year["year_end_date"], "show_zero_values": 0}), True, None),
    }


def write_endpoint(opener, base, host, company, stock=False, hot_items=0):
    """Insert and submit a Sales Invoice per request, using the seeded customers and items.

    With `stock` the invoice delivers stock-item units from a warehouse (update_stock), which
    also writes stock ledger entries and updates the Bin rows that concurrent requests share.
    `hot_items` > 0 restricts the stock items to that many, so concurrent requests collide on the
    same Bin and stock ledger rows (the worst case: everybody sells the same product).
    """
    def names(doctype: str, field: str, prefix: str) -> list[str]:
        filters = urllib.parse.quote(json.dumps([[field, "like", prefix + "%"]]))
        return [row["name"] for row in api_get(
            opener, base, host, f"/api/resource/{doctype}?limit_page_length=200&filters={filters}"
        )["data"]]

    customers = names("Customer", "customer_name", "LOAD ")
    items = names("Item", "item_code", "LOAD Stok" if stock else "LOAD Hizmet")
    if hot_items:
        items = sorted(items)[:hot_items]
    if not customers or not items:
        raise SystemExit("seed the site first (scripts/seed_load_data.py)")
    warehouse = None
    if stock:
        filters = urllib.parse.quote(json.dumps([["company", "=", company], ["is_group", "=", 0]]))
        rows = api_get(opener, base, host, f"/api/resource/Warehouse?limit_page_length=1&filters={filters}")["data"]
        if not rows:
            raise SystemExit("the company has no warehouse")
        warehouse = rows[0]["name"]
    today = date.today().isoformat()

    def make_body() -> bytes:
        lines = []
        for _ in range(random.randint(1, 3)):
            line = {"item_code": random.choice(items), "qty": random.randint(1, 5), "rate": random.randint(10, 500)}
            if warehouse:
                line["warehouse"] = warehouse
            lines.append(line)
        doc = {
            "doctype": "Sales Invoice", "company": company, "customer": random.choice(customers),
            "posting_date": today, "set_posting_time": 1, "due_date": today, "update_stock": 1 if stock else 0,
            "remarks": "LOAD write test", "items": lines,
        }
        return json.dumps({"doc": json.dumps(doc)}).encode()

    name = "write Sales Invoice (stock)" if stock else "write Sales Invoice submit"
    return {name: ("POST", "/api/method/frappe.client.submit", True, make_body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--site", required=True, help="site name, sent as the Host header")
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--levels", default="1,5,20,50")
    parser.add_argument("--scenario", choices=["read", "reports", "write", "write-stock"], default="read")
    parser.add_argument("--company", help="company name (reports and write scenarios)")
    parser.add_argument("--hot-items", type=int, default=0, help="write-stock: sell only this many distinct items")
    parser.add_argument("--force", action="store_true", help='allow write scenarios on a site not named "*load*"')
    args = parser.parse_args()
    writes = args.scenario in ("write", "write-stock")
    if (writes or args.scenario == "reports") and not args.company:
        parser.error(f"--scenario {args.scenario} needs --company")
    if writes and "load" not in args.site.lower() and not args.force:
        parser.error(f'--scenario {args.scenario} creates data that cannot be removed; the site name must contain "load"')

    with open(args.password_file, encoding="utf-8") as handle:
        password = handle.read().strip()
    host = args.site if ":" in args.site else args.site + ":8001"
    opener = login(args.base, host, password)

    headers = None
    if args.scenario == "reports":
        endpoints = report_endpoints(opener, args.base, host, args.company)
    elif writes:
        endpoints = write_endpoint(opener, args.base, host, args.company, stock=args.scenario == "write-stock", hot_items=args.hot_items)
        headers = {"X-Frappe-CSRF-Token": csrf_token(opener, args.base, host)}
    else:
        endpoints = {name: (*spec, None) for name, spec in ENDPOINTS.items()}

    print(f"{'endpoint':26} {'conc':>4} {'req/s':>8} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'errors':>7}")
    for name, (method, path, needs_auth, make_body) in endpoints.items():
        client = opener if needs_auth else make_opener()
        for level in (int(value) for value in args.levels.split(",")):
            rps, p50, p95, p99, errors, failures = run_level(
                client, args.base, host, method, path, level, args.seconds, make_body, headers
            )
            print(f"{name:26} {level:>4} {rps:>8.1f} {p50 * 1000:>8.0f} {p95 * 1000:>8.0f} {p99 * 1000:>8.0f} {errors:>7}")
            if failures:
                print(f"{'':26} non-200 statuses: {dict(failures)}")
                for status in failures:
                    if status in ERROR_SAMPLES:
                        print(f"{'':26} first {status} body: {ERROR_SAMPLES.pop(status)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
