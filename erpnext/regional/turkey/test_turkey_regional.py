# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public v3. See license.txt

import json
import os

from frappe.tests import IntegrationTestCase

from erpnext.regional import get_country_package


class TestTurkeyRegional(IntegrationTestCase):
	def test_country_package_alias(self):
		# Frappe names the country "Türkiye"; the regional package is "turkey".
		self.assertEqual(get_country_package("Türkiye"), "turkey")
		self.assertEqual(get_country_package("United States"), "united_states")

	def test_country_wise_tax_uses_frappe_country_name(self):
		path = os.path.join(
			os.path.dirname(__file__), "..", "..", "setup", "setup_wizard", "data", "country_wise_tax.json"
		)
		with open(path, encoding="utf-8") as f:
			tax_data = json.load(f)

		self.assertNotIn("Turkey", tax_data)
		charts = tax_data["Türkiye"]["chart_of_accounts"]
		for coa in ("Turkey - Chart of Accounts", "*"):
			rates = sorted(
				row["account_head"]["tax_rate"]
				for template in charts[coa]["sales_tax_templates"]
				for row in template["taxes"]
			)
			self.assertEqual(rates, [1.0, 10.0, 20.0])
