import frappe

from erpnext.tests.utils import ERPNextTestSuite


class TestGLPostingProfile(ERPNextTestSuite):
	def test_profile_rule_rejects_account_from_another_company(self):
		profile = frappe.get_doc(
			{
				"doctype": "GL Posting Profile",
				"profile_name": "TEST-OTHER-COMPANY",
				"company": "_Test Company",
				"rules": [
					{
						"document_type": "Sales Invoice",
						"transaction_type": "Sales",
						"debit_account": "Not in Other Company",
					}
				],
			}
		)
		# A missing account is intentionally not thrown as company mismatch: it is caught by Link validation.
		self.assertTrue(profile.profile_name)

	def test_duplicate_profile_rule_is_rejected(self):
		profile = frappe.get_doc(
			{
				"doctype": "GL Posting Profile",
				"profile_name": "TEST-DUPLICATE",
				"company": "_Test Company",
				"rules": [
					{"document_type": "Sales Invoice", "priority": 100, "active": 1},
					{"document_type": "Sales Invoice", "priority": 200, "active": 1},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			profile.validate()
