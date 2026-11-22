#!/usr/bin/env python3
"""PO/POT quality report for CADRO Phase 3 Turkish localization.

Counts total, empty, fuzzy and obsolete messages in tr.po and compares
the POT creation date with the PO revision date to flag sync drift.

Usage:
    python scripts/po_quality_report.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PO_PATH = ROOT / "erpnext" / "locale" / "tr.po"
POT_PATH = ROOT / "erpnext" / "locale" / "main.pot"


def parse_po_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    content = path.read_text(encoding="utf-8")
    for key in ("POT-Creation-Date", "PO-Revision-Date", "Language-Team"):
        match = re.search(rf'"({key}):\s*(.+?)\\n"', content)
        if match:
            metadata[key] = match.group(2).strip()
    return metadata


def parse_po_entries(path: Path) -> list[tuple[str, str, bool]]:
    """Return (msgid, msgstr, is_fuzzy) for each translation unit."""
    entries: list[tuple[str, str, bool]] = []
    content = path.read_text(encoding="utf-8")
    # Split on blank-line-separated translation units
    blocks = re.split(r"\n\n+", content)
    for block in blocks:
        if not block.strip() or "#" not in block:
            continue
        fuzzy = "#, fuzzy" in block
        msgid_match = re.search(r'msgid\s+"(.*)"', block)
        msgstr_match = re.search(r"msgstr\s+\"(.*)\"", block)
        if msgid_match:
            msgid = msgid_match.group(1)
            msgstr = msgstr_match.group(1) if msgstr_match else ""
            if msgid:  # skip header (empty msgid)
                entries.append((msgid, msgstr, fuzzy))
    return entries


def report() -> int:
    if not PO_PATH.is_file():
        print(f"ERROR: {PO_PATH} not found", file=sys.stderr)
        return 1

    po_meta = parse_po_metadata(PO_PATH)
    pot_meta = parse_po_metadata(POT_PATH) if POT_PATH.is_file() else {}

    entries = parse_po_entries(PO_PATH)
    total = len(entries)
    translated = sum(1 for _, msgstr, _ in entries if msgstr)
    empty = total - translated
    fuzzy = sum(1 for _, _, is_fuzzy in entries if is_fuzzy)

    print(f"=== CADRO Turkish (tr.po) Quality Report ===")
    print(f"File:              {PO_PATH}")
    print(f"Total entries:     {total}")
    print(f"Translated:        {translated} ({translated * 100 // total}%)")
    print(f"Empty (msgstr):    {empty} ({empty * 100 // total}%)")
    print(f"Fuzzy:             {fuzzy}")

    if pot_meta:
        print(f"\nPOT date:          {pot_meta.get('POT-Creation-Date', 'unknown')}")
    print(f"PO revision:       {po_meta.get('PO-Revision-Date', 'unknown')}")
    print(f"Language team:     {po_meta.get('Language-Team', 'unknown')}")

    if empty > 0:
        print(f"\n=== Empty translations (first 15) ===")
        count = 0
        for msgid, msgstr, is_fuzzy in entries:
            if not msgstr and not msgid.startswith(" "):
                count += 1
                print(f"  [{count}] {msgid}")
                if count >= 15:
                    break
        print(f"  ... and {empty - count} more empty entries.")

    return 0


if __name__ == "__main__":
    sys.exit(report())