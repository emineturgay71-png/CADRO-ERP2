"""Resolve application pins from cadro.baseline.json for use in CI and deployment scripts.

Usage:
    python scripts/ci_pin_resolver.py --component erpnext
    >> 920f1d5b3d18142cf3c4cc6edf59e53950a7832b

    FRAPPE_BRANCH=$(python scripts/ci_pin_resolver.py --component frappe)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "cadro.baseline.json"


def resolve(component: str) -> str:
    with MANIFEST_PATH.open(encoding="utf-8") as source:
        document = json.load(source)
    for item in document.get("components", []):
        if item.get("name") == component:
            return item["commit"]
    raise SystemExit(f"Component '{component}' not found in {MANIFEST_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True, choices=["erpnext", "frappe", "payments"])
    parser.add_argument("--field", default="commit", choices=["commit", "ref"])
    args = parser.parse_args()
    with MANIFEST_PATH.open(encoding="utf-8") as source:
        document = json.load(source)
    for item in document.get("components", []):
        if item.get("name") == args.component:
            print(item[args.field])
            return
    raise SystemExit(f"Component '{args.component}' not found in {MANIFEST_PATH}")


if __name__ == "__main__":
    main()