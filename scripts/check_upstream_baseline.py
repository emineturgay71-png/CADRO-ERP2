"""Verify fork ancestry against a recorded upstream GitHub commit using stdlib only.

The local commit must be present in the selected upstream commit's ancestry. The
report distinguishes upstream changes missing locally from CADRO-only changes.
No repositories or local Git refs are modified by this read-only check.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SHA_PATTERN = __import__("re").compile(r"^[0-9a-f]{40}$")


def github_json(endpoint: str) -> dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CADRO-Faz0-Governance"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com{endpoint}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code in (403, 429):
            raise RuntimeError(
                "GitHub API rate/access limit reached. Retry later or supply GITHUB_TOKEN through the environment, never in a file."
            ) from error
        raise RuntimeError(f"GitHub API returned HTTP {error.code} for {endpoint}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot verify upstream through GitHub: {error.reason}") from error


def upstream_erpnext_record(manifest: Path) -> dict[str, Any]:
    with manifest.open(encoding="utf-8") as source:
        document = json.load(source)
    for component in document.get("components", []):
        if component.get("name") == "erpnext" and component.get("repository", "").endswith("/frappe/erpnext"):
            return component
    raise ValueError("ERPNext component must use the canonical frappe/erpnext upstream repository")


def check(record: dict[str, Any], remote: str) -> int:
    """Compare the selected CADRO remote commit with a known upstream starting point.

    Compare is the ownership report, not the resolver of a moving development line.
    Uncommitted files are deliberately excluded from current/fork evidence.
    """
    fork_repository = subprocess.run(
        ["git", "remote", "get-url", remote], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    if fork_repository not in {
        "https://github.com/emineturgay71-png/CADRO-ERP2.git",
        "https://github.com/emineturgay71-png/CADRO-ERP2",
        "git@github.com:emineturgay71-png/CADRO-ERP2.git",
    }:
        raise RuntimeError(f"Unexpected CADRO origin: {fork_repository}")
    fork_commit = subprocess.run(
        ["git", "ls-remote", remote, "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.split()[0]
    upstream_commit = record["reference_commit"]
    comparison = github_json(f"/repos/emineturgay71-png/CADRO-ERP2/compare/{upstream_commit}...{fork_commit}")
    if comparison.get("status") not in {"identical", "behind", "ahead", "diverged"}:
        raise RuntimeError(f"Unexpected compare status: {comparison.get('status')}")
    print(
        f"CADRO fork compare {upstream_commit}...{fork_commit}: {comparison['status']}; "
        f"fork commits since base={comparison.get('ahead_by')}, missing base-to-reference upstream commits={comparison.get('behind_by')}"
    )
    merge_base = comparison.get("merge_base_commit", {}).get("sha")
    print(f"Measured common ancestor: {merge_base}. Do not interpret behind/ahead counts as a current product diff.")
    for commit in comparison.get("commits", []):
        print(f"Review CADRO commit attribution: {commit.get('sha')} — {commit.get('commit', {}).get('message', '').splitlines()[0]}")
    print("Uncommitted files are not included in this comparison; follow repository audit before any SaaS launch.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "cadro.baseline.json")
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--reference-commit",
        default="807222631c4f50a09e2d6351941562dbc1e90eb5",
        help="A known upstream commit, not a moving branch name",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if not SHA_PATTERN.fullmatch(arguments.reference_commit):
        raise SystemExit("Reference commit must be a full lowercase commit SHA")
    record = upstream_erpnext_record(arguments.manifest)
    record["reference_commit"] = arguments.reference_commit
    try:
        sys.exit(check(record, remote=arguments.remote))
    except (RuntimeError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Upstream baseline verification failed: {error}") from error
