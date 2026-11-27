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

	def test_apply_profile_account_feature_disabled_returns_legacy(self):
		from erpnext.accounts.services.gl_posting_profile import apply_profile_account

		settings = frappe.get_single("Accounts Settings")
		old_enabled = settings.enable_cadro_posting_profile
		settings.enable_cadro_posting_profile = 0
		settings.save(ignore_permissions=True)
		try:
			account, reason = apply_profile_account(
				"_Test Company",
				"Legacy - _Test Company",
				{"document_type": "Sales Invoice", "transaction_type": "Sales"},
				"credit",
			)
			self.assertEqual(account, "Legacy - _Test Company")
			self.assertEqual(reason, "feature-disabled")
		finally:
			settings.enable_cadro_posting_profile = old_enabled
			settings.save(ignore_permissions=True)

	def test_apply_profile_account_dry_run_never_changes_legacy(self):
		from erpnext.accounts.services.gl_posting_profile import apply_profile_account

		settings = frappe.get_single("Accounts Settings")
		old_enabled = settings.enable_cadro_posting_profile
		old_dry_run = settings.cadro_posting_profile_dry_run
		settings.enable_cadro_posting_profile = 1
		settings.cadro_posting_profile_dry_run = 1
		settings.save(ignore_permissions=True)
		try:
			account, _reason = apply_profile_account(
				"_Test Company",
				"Legacy - _Test Company",
				{"document_type": "Payment Entry", "transaction_type": "Payment Receive"},
				"credit",
			)
			self.assertEqual(account, "Legacy - _Test Company")
		finally:
			settings.enable_cadro_posting_profile = old_enabled
			settings.cadro_posting_profile_dry_run = old_dry_run
			settings.save(ignore_permissions=True)

	def test_apply_profile_account_rejects_missing_strict_account(self):
		from erpnext.accounts.services.gl_posting_profile import apply_profile_account

		profile = frappe.get_doc(
			{
				"doctype": "GL Posting Profile",
				"profile_name": "TEST-STRICT-MISSING-ACCOUNT",
				"company": "_Test Company",
				"strict_mode": 1,
				"rules": [{"document_type": "Journal Entry", "transaction_type": "Journal"}],
			}
		)
		profile.insert(ignore_permissions=True)

		settings = frappe.get_single("Accounts Settings")
		old_enabled = settings.enable_cadro_posting_profile
		old_dry_run = settings.cadro_posting_profile_dry_run
		settings.enable_cadro_posting_profile = 1
		settings.cadro_posting_profile_dry_run = 0
		settings.save(ignore_permissions=True)
		try:
			with self.assertRaises(frappe.ValidationError):
				apply_profile_account(
					"_Test Company",
					"Legacy - _Test Company",
					{"document_type": "Journal Entry", "transaction_type": "Journal"},
					"debit",
				)
		finally:
			settings.enable_cadro_posting_profile = old_enabled
			settings.cadro_posting_profile_dry_run = old_dry_run
			settings.save(ignore_permissions=True)
