# Copyright (c) 2026, CADRO and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

from typing import Any

import frappe
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)


def resolve_dimension_set(gl_entry: dict[str, Any]) -> str:
	"""Return a stable fingerprint for the active dimensions of a GL entry.

	The fingerprint is a SHA-256 hex digest of a canonical representation
	of the dimension fieldnames and their values.  Every call with the same
	active dimensions and values yields the same fingerprint; the caller does
	not need to persist the fingerprint on 'GL Entry' for the function to
	be useful (the fingerprint can be joined to GL Dimension Set later).
	"""
	import hashlib

	active_dimensions = sorted(get_accounting_dimensions())
	if not active_dimensions:
		return ""

	parts = []
	for dim_field in active_dimensions:
		value = str(gl_entry.get(dim_field) or "")
		parts.append(f"{dim_field}={value}")

	digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
	return digest
