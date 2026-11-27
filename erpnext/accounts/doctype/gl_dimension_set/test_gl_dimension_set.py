import frappe

from erpnext.tests.utils import ERPNextTestSuite


class TestGLDimensionSet(ERPNextTestSuite):
	def test_empty_dimensions_return_empty_fingerprint(self):
		"""With no custom dimensions, the fingerprint is an empty string."""
		from unittest.mock import patch

		from erpnext.accounts.services.gl_dimension_set import resolve_dimension_set

		with patch("erpnext.accounts.services.gl_dimension_set.get_accounting_dimensions", return_value=[]):
			self.assertEqual(resolve_dimension_set(frappe._dict()), "")

	def test_same_values_produce_same_fingerprint(self):
		from unittest.mock import patch

		from erpnext.accounts.services.gl_dimension_set import resolve_dimension_set

		with patch(
			"erpnext.accounts.services.gl_dimension_set.get_accounting_dimensions",
			return_value=["cost_center", "project"],
		):
			fp1 = resolve_dimension_set(frappe._dict(cost_center="Main", project="P1"))
			fp2 = resolve_dimension_set(frappe._dict(cost_center="Main", project="P1"))
			self.assertEqual(fp1, fp2)

	def test_different_dimensions_produce_different_fingerprint(self):
		from unittest.mock import patch

		from erpnext.accounts.services.gl_dimension_set import resolve_dimension_set

		with patch(
			"erpnext.accounts.services.gl_dimension_set.get_accounting_dimensions",
			return_value=["cost_center", "project"],
		):
			fp1 = resolve_dimension_set(frappe._dict(cost_center="A", project="X"))
			fp2 = resolve_dimension_set(frappe._dict(cost_center="A"))
		self.assertNotEqual(fp1, fp2)

	def test_doc_is_immutable(self):
		doc = frappe.get_doc(
			{
				"doctype": "GL Dimension Set",
				"dimension_fingerprint": "TEST-FP-01",
				"values": [
					{"dimension_fieldname": "cost_center", "dimension_value": "Main"},
				],
			}
		)
		doc.insert()
		self.assertEqual(doc.dimension_fingerprint, "TEST-FP-01")
		self.assertEqual(len(doc.values), 1)
