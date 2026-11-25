#!/usr/bin/env python3
"""Derive the CADRO image tag and a release record from the git state.

No product version number is assigned here (that is a separate release decision, see
docs/governance/version-and-dependencies.md); the tag identifies the exact source.

Usage (from the repository root):
    python scripts/cadro_version.py                 # prints the tag, e.g. 3ec6b7bd67 or 3ec6b7bd67-dirty
    python scripts/cadro_version.py --report        # prints a JSON release record

    $env:CADRO_IMAGE_TAG = python scripts/cadro_version.py          # PowerShell
    export CADRO_IMAGE_TAG="$(python scripts/cadro_version.py)"     # bash

The tag is `<commit>` of a clean checkout and `<commit>-dirty` when tracked files have uncommitted
changes; a `-dirty` image does not correspond to any commit and must not be released. With
`--require-clean` the script exits with status 1 instead of printing a `-dirty` tag.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "cadro.baseline.json"
SHORT_SHA_LENGTH = 10


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def commit() -> str:
    return _git("rev-parse", "HEAD")


def is_dirty() -> bool:
    return bool(_git("status", "--porcelain", "--untracked-files=no"))


def image_tag() -> str:
    tag = commit()[:SHORT_SHA_LENGTH]
    return f"{tag}-dirty" if is_dirty() else tag


def release_record() -> dict:
    """Source commit, cleanliness, and the pinned upstream components the image is built from."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {
        "image_tag": image_tag(),
        "commit": commit(),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": is_dirty(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline": baseline["baseline"]["name"],
        "production_approved": baseline["baseline"]["production_approved"],
        "components": {c["name"]: c["commit"] for c in baseline["components"]},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", action="store_true", help="print a JSON release record")
    parser.add_argument("--require-clean", action="store_true", help="fail when the checkout is dirty")
    args = parser.parse_args(argv)

    try:
        if args.require_clean and is_dirty():
            print("ERROR: tracked files have uncommitted changes", file=sys.stderr)
            return 1
        print(json.dumps(release_record(), indent=2) if args.report else image_tag())
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
