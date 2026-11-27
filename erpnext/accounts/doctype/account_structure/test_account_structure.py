import frappe

from erpnext.tests.utils import ERPNextTestSuite


class TestAccountStructure(ERPNextTestSuite):
	def test_rejects_repeated_dimension(self):
		doc = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-REPEATED-DIM",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "mandatory": 1},
					{"dimension_fieldname": "cost_center", "mandatory": 0},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_rejects_block_without_mirror(self):
		doc = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-BLOCK-NO-MIRROR",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "blocked_dimensions": "project"},
					{"dimension_fieldname": "project"},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_accepts_a_valid_structure(self):
		doc = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-VALID-STRUCT",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "mandatory_for_pl": 1},
					{"dimension_fieldname": "project"},
				],
			}
		)
		doc.validate()

	def test_structure_validator_enforces_mandatory_dimension(self):
		from erpnext.accounts.services.gl_structure_validator import validate_account_structure

		structure = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-MANDATORY-STRUCT",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "mandatory": 1},
				],
			}
		)
		structure.insert()

		entry = frappe._dict(
			account="Sales - _TC",
			company="_Test Company",
			cost_center=None,
		)
		with self.assertRaises(frappe.ValidationError):
			validate_account_structure(entry)

	def test_structure_validator_allows_satisfied_dimension(self):
		from erpnext.accounts.services.gl_structure_validator import validate_account_structure

		structure = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-SATISFIED-STRUCT",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "mandatory": 1},
				],
			}
		)
		structure.insert()

		entry = frappe._dict(
			account="Sales - _TC",
			company="_Test Company",
			cost_center="_Test Cost Center - _TC",
		)
		try:
			validate_account_structure(entry)
		except frappe.ValidationError:
			self.fail("Valid dimension should not be rejected")

	def test_structure_validator_rejects_blocked_combination(self):
		from erpnext.accounts.services.gl_structure_validator import validate_account_structure

		structure = frappe.get_doc(
			{
				"doctype": "Account Structure",
				"structure_name": "TEST-BLOCKED-COMBO-STRUCT",
				"company": "_Test Company",
				"segments": [
					{"dimension_fieldname": "cost_center", "blocked_dimensions": "project"},
					{"dimension_fieldname": "project", "blocked_dimensions": "cost_center"},
				],
			}
		)
		structure.insert()

		entry = frappe._dict(
			account="Sales - _TC",
			company="_Test Company",
			cost_center="_Test Cost Center - _TC",
			project="_Test Project - _TC",
		)
		with self.assertRaises(frappe.ValidationError):
			validate_account_structure(entry)
