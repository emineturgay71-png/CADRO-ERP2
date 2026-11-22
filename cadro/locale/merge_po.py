"""Merge CADRO overlay translations into a base .po file.

usage: merge_po.py BASE.po OVERLAY.po

Entries in OVERLAY replace (or are added to) BASE, keyed by msgid. Used at container
start to apply cadro/locale/frappe_tr_overlay.po on top of erpnext's tr.po. Runs with
the bench virtualenv python (babel is installed there).
"""
import sys

from babel.messages.catalog import Message
from babel.messages.pofile import read_po, write_po


def main(base_path, overlay_path):
    with open(base_path, "rb") as f:
        base = read_po(f, locale="tr")
    with open(overlay_path, "rb") as f:
        overlay = read_po(f, locale="tr")
    changed = added = 0
    for m in overlay:
        if not m.id:
            continue
        cur = base.get(m.id, m.context)
        if cur is None:
            base[m.id] = Message(m.id, m.string, auto_comments=m.auto_comments, context=m.context)
            added += 1
        elif cur.string != m.string:
            cur.string = m.string
            cur.flags.discard("fuzzy")
            changed += 1
    with open(base_path, "wb") as f:
        write_po(f, base, width=0, sort_output=False)
    print("overlay merged: %d changed, %d added" % (changed, added))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
