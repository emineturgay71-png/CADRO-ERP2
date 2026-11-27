# Copyright (c) 2026, CADRO and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AccountStructure(Document):
	def validate(self):
		if not self.company:
			frappe.throw(_("Company is required"))
		self.validate_segments()

	def validate_segments(self):
		seen = set()
		for segment in self.segments:
			if not segment.dimension_fieldname:
				frappe.throw(_("Row {0}: a segment needs a dimension").format(segment.idx))

			field = segment.dimension_fieldname
			if field in seen:
				frappe.throw(_("Row {0}: Dimension {1} is repeated").format(segment.idx, field))
			seen.add(field)

			for other in self.segments:
				if other is segment:
					continue
				if segment.blocked_dimensions and other.dimension_fieldname in (segment.blocked_dimensions or ""):
					frappe.throw(
						_("Row {0}: blocking {1} also means {1} must block {2} — both are required").format(
							segment.idx, segment.dimension_fieldname, other.dimension_fieldname
						)
					)
