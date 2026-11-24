# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public v3. See license.txt
"""Ana akışın tamamlayıcıları (Türkiye): defterlerin raporlarla tutarlılığı, hareketli ortalama maliyet,
alış iadesi, müşteri avansı, KDV oranları ve iskonto, kısmı teslimat, dönem kapanışı, dövizli satış,
banka ekstresi içe aktarma ve otomatik uzlaştırma.

`test_main_flow.py` ana zinciri ve temel varyasyonları sınar; bu dosya aynı şirket ve aynı adım
yardımcılarıyla (`TradingFlow`) kalan uçları kapsar. Her test sonunda geri alınır.

    bench --site <site> run-tests --module erpnext.regional.turkey.test_main_flow_extended
"""

import json
from unittest.mock import patch

import frappe
from freezegun import freeze_time
from frappe import _dict
from frappe.utils import add_days, flt, getdate, nowdate

from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import auto_reconcile_vouchers
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.report.accounts_payable_summary.accounts_payable_summary import (
	execute as payable_summary,
)
from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import (
	execute as receivable_summary,
)
from erpnext.accounts.report.balance_sheet.balance_sheet import execute as balance_sheet
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
	execute as profit_and_loss,
)
from erpnext.accounts.report.trial_balance.trial_balance import execute as trial_balance
from erpnext.accounts.utils import get_fiscal_year
from erpnext.regional.turkey.test_main_flow import (
	ABBR,
	BANK_NAME,
	BANK_PART,
	BUY_QTY,
	BUY_RATE,
	CAPITAL,
	CASH_PART,
	CHEQUE_PART,
	COGS,
	COGS_NO,
	CUSTOMER,
	ITEM,
	KDV,
	MAIN_FLOW_BALANCES,
	PURCHASE_KDV,
	PURCHASE_NET,
	PURCHASE_TOTAL,
	SALE_KDV,
	SALE_NET,
	SALE_TOTAL,
	SELL_QTY,
	SELL_RATE,
	SERVICE,
	SUPPLIER,
	COMPANY,
	TradingFlow,
	acc,
	apply_kdv,
	balance,
	bin_of,
	outstanding,
	setup_company,
	voucher_gl,
)
from erpnext.stock.report.stock_balance.stock_balance import execute as stock_balance
from erpnext.tests.utils import ERPNextTestSuite


def rows_by_account(data):
	return {row["account"]: row for row in data if row.get("account")}


class TestExtendedFlows(ERPNextTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_company()

	def setUp(self):
		self.flow = TradingFlow(self)
		self.today = nowdate()

	# ---- yardımcılar ------------------------------------------------------

	def buy_more(self, qty, rate, tag):
		"""İkinci bir alım: sipariş -> irsaliye -> fatura (aynı KDV %20)."""
		from erpnext.buying.doctype.purchase_order.mapper import make_purchase_receipt
		from erpnext.stock.doctype.purchase_receipt.mapper import make_purchase_invoice

		f = self.flow
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": COMPANY,
				"supplier": SUPPLIER,
				"currency": "TRY",
				"transaction_date": self.today,
				"schedule_date": self.today,
				"set_warehouse": f.warehouse,
				"taxes_and_charges": f"KDV %20 - {ABBR}",
				"items": [
					{
						"item_code": ITEM,
						"qty": qty,
						"rate": rate,
						"schedule_date": self.today,
						"warehouse": f.warehouse,
					}
				],
			}
		)
		apply_kdv(po, "Purchase Taxes and Charges Template")
		po.insert()
		po.submit()
		pr = make_purchase_receipt(po.name)
		pr.insert()
		pr.submit()
		pi = make_purchase_invoice(pr.name)
		pi.bill_no = f"TED-{tag}"
		pi.bill_date = self.today
		pi.insert()
		pi.submit()
		net = qty * rate
		f.assert_gl("Purchase Receipt", pr.name, {"153.01": net, "320.90": -net})
		f.assert_gl(
			"Purchase Invoice", pi.name, {"320.90": net, "191.01.04": net * KDV, "320.01": -net * (1 + KDV)}
		)
		return pr, pi

	def service_invoice(self, template, net, discount=0):
		"""Stoksuz hizmet satış faturası; KDV şablonu ve iskonto parametreli."""
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "TRY",
				"posting_date": self.today,
				"set_posting_time": 1,
				"due_date": self.today,
				"taxes_and_charges": f"KDV {template} - {ABBR}",
				"items": [{"item_code": SERVICE, "qty": 1, "rate": net}],
			}
		)
		if discount:
			si.apply_discount_on = "Net Total"
			si.discount_amount = discount
		apply_kdv(si, "Sales Taxes and Charges Template", template)
		si.insert()
		si.submit()
		return si

	# ---- 1. Raporlar defterlerle tutarlı mı -----------------------------

	def test_reports_agree_with_the_books_after_the_main_flow(self):
		self.flow.run_main_flow()
		fiscal_year = get_fiscal_year(self.today, company=COMPANY)[0]

		# Mizan: genel toplam dengeli, hesap bakiyeleri defterle aynı.
		data = trial_balance(_dict(company=COMPANY, fiscal_year=fiscal_year))[1]
		total = data[-1]
		self.assertEqual(flt(total["debit"], 2), flt(total["credit"], 2))
		rows = rows_by_account(data)
		for number, expected in MAIN_FLOW_BALANCES.items():
			row = rows[acc(number)]
			closing = flt(row.get("closing_debit", 0) - row.get("closing_credit", 0), 2)
			self.assertEqual(closing, flt(expected, 2), f"mizan {number}")

		period = _dict(
			company=COMPANY,
			filter_based_on="Date Range",
			period_start_date=self.today,
			period_end_date=self.today,
			periodicity="Yearly",
			accumulated_values=1,
		)
		# Kâr-zarar: gelir kökü 3.200, gider kökü (maliyet) 2.000 -> net kâr 1.200.
		pnl = rows_by_account(profit_and_loss(_dict(period))[1])
		self.assertEqual(flt(pnl[acc("6")]["total"], 2), SALE_NET)
		self.assertEqual(flt(pnl[acc("6G")]["total"], 2), COGS)

		# Bilanço: varlıklar = yükümlülükler + özkaynak + dönem kârı (henüz kapatılmadı).
		bs_data = balance_sheet(_dict(period))[1]
		bs = rows_by_account(bs_data)
		provisional = sum(
			flt(row.get("total", 0), 2)
			for row in bs_data
			if str(row.get("account_name", "")).strip("'").startswith("Provisional Profit")
		)
		assets = flt(bs[acc("1")]["total"], 2)
		liabilities = flt(bs[acc("3")]["total"], 2) if acc("3") in bs else 0
		equity = flt(bs[acc("5")]["total"], 2)
		self.assertEqual(assets, flt(liabilities + equity + provisional, 2))
		self.assertEqual(provisional, SALE_NET - COGS)
		self.assertEqual(liabilities, SALE_KDV)  # ödenecek KDV (391) alınan KDV'den indirilecek KDV düşülmeden

		# Stok bakiye raporu: miktar ve değer = Bin.
		stock = stock_balance(
			_dict(company=COMPANY, from_date=add_days(self.today, -30), to_date=self.today, item_code=[ITEM])
		)[1]
		self.assertEqual(sum(flt(r["bal_qty"]) for r in stock), BUY_QTY - SELL_QTY)
		self.assertEqual(flt(sum(r["bal_val"] for r in stock), 2), PURCHASE_NET - COGS)

	def test_receivable_and_payable_summaries_show_the_open_invoices(self):
		self.flow.sell()
		filters = _dict(company=COMPANY, report_date=self.today, range="30, 60, 90, 120")
		receivable = {r["party"]: r for r in receivable_summary(_dict(filters))[1]}
		payable = {r["party"]: r for r in payable_summary(_dict(filters))[1]}
		self.assertEqual(flt(receivable[CUSTOMER]["outstanding"], 2), SALE_TOTAL)
		self.assertEqual(flt(payable[SUPPLIER]["outstanding"], 2), PURCHASE_TOTAL)

	# ---- 2. Hareketli ortalama maliyet -----------------------------------

	def test_moving_average_cost_feeds_the_cost_of_sales(self):
		f = self.flow
		frappe.db.set_value("Item", ITEM, "valuation_method", "Moving Average")
		f.purchase()  # 100 adet x 50
		self.buy_more(50, 80, "2")  # 50 adet x 80 -> ortalama (5000 + 4000) / 150 = 60
		average = (BUY_QTY * BUY_RATE + 50 * 80) / (BUY_QTY + 50)
		self.assertEqual(average, 60)
		self.assertEqual(bin_of(ITEM, f.warehouse), (150, 9000))

		f.sell(unit_cost=average)
		self.assertEqual(balance(COGS_NO), SELL_QTY * average)  # 2.400
		self.assertEqual(bin_of(ITEM, f.warehouse), (110, 110 * average))
		f.verify_books({"153.01": 9000 - SELL_QTY * average, COGS_NO: SELL_QTY * average})

	def test_fifo_cost_of_sales_uses_the_oldest_purchase_first(self):
		f = self.flow
		frappe.db.set_value("Item", ITEM, "valuation_method", "FIFO")
		f.purchase()  # 100 adet x 50
		self.buy_more(50, 80, "2")  # 50 adet x 80
		f.sell()  # 40 adet en eski katmandan: 40 x 50
		self.assertEqual(balance(COGS_NO), COGS)
		self.assertEqual(bin_of(ITEM, f.warehouse), (110, 9000 - COGS))
		f.verify_books({"153.01": 9000 - COGS, COGS_NO: COGS})

	# ---- 3. Alış iadesi (irsaliye + fatura) ----------------------------

	def test_purchase_return_reverses_stock_vat_and_payable(self):
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		f = self.flow
		f.purchase()
		qty = 10
		net = qty * BUY_RATE

		pr_return = make_return_doc("Purchase Receipt", f.docs["pr"])
		pr_return.items[0].qty = -qty
		pr_return.insert()
		pr_return.submit()
		f.assert_gl("Purchase Receipt", pr_return.name, {"320.90": net, "153.01": -net})

		pi_return = make_return_doc("Purchase Invoice", f.docs["pi"])
		pi_return.items[0].qty = -qty
		pi_return.insert()
		pi_return.submit()
		f.assert_gl(
			"Purchase Invoice",
			pi_return.name,
			{"320.01": net * (1 + KDV), "320.90": -net, "191.01.04": -net * KDV},
		)
		self.assertEqual(bin_of(ITEM, f.warehouse), (BUY_QTY - qty, PURCHASE_NET - net))
		f.verify_books(
			{
				"153.01": PURCHASE_NET - net,
				"191.01.04": PURCHASE_KDV - net * KDV,
				"320.01": -(PURCHASE_TOTAL - net * (1 + KDV)),
				"320.90": 0,
			}
		)

	# ---- 4. Müşteri avansı, sonra faturaya mahsup -------------------------

	def test_customer_advance_is_applied_to_the_invoice(self):
		f = self.flow
		advance = 2000
		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": COMPANY,
				"posting_date": self.today,
				"mode_of_payment": "Wire Transfer",
				"party_type": "Customer",
				"party": CUSTOMER,
				"paid_from": acc("120.01"),
				"paid_to": acc("102.01"),
				"paid_amount": advance,
				"received_amount": advance,
				"reference_no": "HVL-AVANS-1",
				"reference_date": self.today,
			}
		).insert()
		pe.submit()
		f.assert_gl("Payment Entry", pe.name, {"102.01": advance, "120.01": -advance})
		self.assertEqual(balance("120.01"), -advance)  # müşteri lehine bakiye

		f.sell()
		self.assertEqual(outstanding("Sales Invoice", f.docs["si"]), SALE_TOTAL)

		reconciliation = frappe.new_doc("Payment Reconciliation")
		reconciliation.company = COMPANY
		reconciliation.party_type = "Customer"
		reconciliation.party = CUSTOMER
		reconciliation.receivable_payable_account = acc("120.01")
		reconciliation.from_invoice_date = reconciliation.to_invoice_date = self.today
		reconciliation.from_payment_date = reconciliation.to_payment_date = self.today
		reconciliation.get_unreconciled_entries()
		self.assertEqual(len(reconciliation.invoices), 1)
		self.assertEqual(len(reconciliation.payments), 1)
		invoices = [row.as_dict() for row in reconciliation.invoices]
		payments = [row.as_dict() for row in reconciliation.payments]
		reconciliation.allocate_entries(frappe._dict({"invoices": invoices, "payments": payments}))
		reconciliation.reconcile()

		self.assertEqual(outstanding("Sales Invoice", f.docs["si"]), SALE_TOTAL - advance)
		f.collect_bank(amount=SALE_TOTAL - advance)
		self.assertEqual(outstanding("Sales Invoice", f.docs["si"]), 0)
		self.assertEqual(balance("120.01"), 0)
		self.assertEqual(balance("102.01"), advance + SALE_TOTAL - advance)

	# ---- 5. KDV oranları ve iskonto -----------------------------------------

	def test_vat_rates_and_discount(self):
		f = self.flow
		cases = (
			# şablon, net, iskonto, KDV hesabı, KDV tutarı
			("%10", 1000, 0, "391.01.05", 100),
			("%1", 1000, 0, "391.01.03", 10),
			("%20", 1000, 100, "391.01.04", 180),  # iskontolu matrah 900
		)
		for template, net, discount, vat_account, vat in cases:
			si = self.service_invoice(template, net, discount)
			taxable = net - discount
			f.assert_gl(
				"Sales Invoice",
				si.name,
				{"120.01": taxable + vat, "600.01": -taxable, vat_account: -vat},
			)
			self.assertEqual(outstanding("Sales Invoice", si.name), taxable + vat)
		self.assertEqual(balance("600.01"), -(1000 + 1000 + 900))
		self.assertEqual(balance("120.01"), 1100 + 1010 + 1080)

	# ---- 6. Kısmi teslimat: bir sipariş, iki irsaliye, iki fatura ---------

	def test_partial_deliveries_and_invoices(self):
		from erpnext.selling.doctype.sales_order.mapper import make_delivery_note
		from erpnext.stock.doctype.delivery_note.mapper import make_sales_invoice

		f = self.flow
		f.purchase()
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "TRY",
				"transaction_date": self.today,
				"delivery_date": self.today,
				"set_warehouse": f.warehouse,
				"taxes_and_charges": f"KDV %20 - {ABBR}",
				"items": [
					{
						"item_code": ITEM,
						"qty": SELL_QTY,
						"rate": SELL_RATE,
						"delivery_date": self.today,
						"warehouse": f.warehouse,
					}
				],
			}
		)
		apply_kdv(so, "Sales Taxes and Charges Template")
		so.insert()
		so.submit()

		invoices = []
		for delivered in (25, 15):
			dn = make_delivery_note(so.name)
			dn.items[0].qty = delivered
			dn.insert()
			dn.submit()
			f.assert_gl(
				"Delivery Note", dn.name, {COGS_NO: delivered * BUY_RATE, "153.01": -delivered * BUY_RATE}
			)
			si = make_sales_invoice(dn.name)
			si.insert()
			si.submit()
			net = delivered * SELL_RATE
			f.assert_gl(
				"Sales Invoice",
				si.name,
				{"120.01": net * (1 + KDV), "600.01": -net, "391.01.04": -net * KDV},
			)
			invoices.append(si.name)
			if delivered == 25:
				so.reload()
				self.assertEqual(flt(so.per_delivered, 2), 62.5)

		so.reload()
		self.assertEqual(flt(so.per_delivered, 2), 100)
		self.assertEqual(flt(so.per_billed, 2), 100)
		self.assertEqual(sum(outstanding("Sales Invoice", name) for name in invoices), SALE_TOTAL)
		f.verify_books({COGS_NO: COGS, "120.01": SALE_TOTAL, "600.01": -SALE_NET, "391.01.04": -SALE_KDV})

	# ---- 7. Dönem kapanışı ---------------------------------------------------

	def test_period_closing_moves_profit_to_equity(self):
		f = self.flow
		f.run_main_flow()
		year, start, end = get_fiscal_year(self.today, company=COMPANY)
		# Dönem, bittikten sonra kapatılır (stok kapanışı gelecek tarihli olamaz): saati yıl sonrasına al.
		freezer = freeze_time(add_days(end, 5))
		freezer.start()
		self.addCleanup(freezer.stop)
		# Dönem kapanışından önce şirketin stok kapanışı (Stock Closing Entry) gerekir.
		stock_closing = frappe.get_doc(
			{"doctype": "Stock Closing Entry", "company": COMPANY, "from_date": start, "to_date": end}
		).insert()
		with patch("erpnext.stock.doctype.stock_closing_entry.stock_closing_entry.enqueue"):
			stock_closing.submit()
		stock_closing.create_stock_closing_balance_entries()
		stock_closing.db_set("status", "Completed")
		pcv = frappe.get_doc(
			{
				"doctype": "Period Closing Voucher",
				"transaction_date": end,
				"period_start_date": start,
				"period_end_date": end,
				"company": COMPANY,
				"fiscal_year": year,
				"cost_center": f"Main - {ABBR}",
				"closing_account_head": acc("590.01"),
				"remarks": "Dönem kapanışı",
			}
		).insert()
		pcv.submit()
		pcv.reload()
		self.assertEqual(pcv.gle_processing_status, "Completed")
		f.assert_gl(
			"Period Closing Voucher",
			pcv.name,
			{"600.01": SALE_NET, COGS_NO: -COGS, "590.01": -(SALE_NET - COGS)},
		)
		# Gelir tablosu hesapları sıfırlanır, kâr özkaynakta.
		self.assertEqual((balance("600.01"), balance(COGS_NO)), (0, 0))
		self.assertEqual(balance("590.01"), -(SALE_NET - COGS))
		# Bilanço hesapları değişmez.
		self.assertEqual(balance("102.01"), MAIN_FLOW_BALANCES["102.01"])
		self.assertEqual(balance("153.01"), MAIN_FLOW_BALANCES["153.01"])
		data = trial_balance(_dict(company=COMPANY, fiscal_year=year))[1]
		self.assertEqual(flt(data[-1]["debit"], 2), flt(data[-1]["credit"], 2))

	# ---- 8. Dövizli satış: farklı kurla tahsilat -------------------------------

	def fx_sale(self, invoice_rate, payment_rate):
		"""120 EUR'luk (100 EUR + %20 KDV) hizmet satışı; EUR banka hesabına payment_rate kuruyla tahsilat."""
		frappe.db.set_value("Currency", "EUR", "enabled", 1)
		customer = "Akış Euro Müşteri"
		if not frappe.db.exists("Customer", customer):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer,
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}),
					"default_currency": "EUR",
					"accounts": [{"company": COMPANY, "account": acc("120.02")}],
				}
			).insert()
		frappe.get_doc(
			{
				"doctype": "Currency Exchange",
				"date": self.today,
				"from_currency": "EUR",
				"to_currency": "TRY",
				"exchange_rate": payment_rate,
				"for_selling": 1,
				"for_buying": 1,
			}
		).insert(ignore_if_duplicate=True)

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": customer,
				"currency": "EUR",
				"conversion_rate": invoice_rate,
				"selling_price_list": frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}),
				"price_list_currency": "EUR",
				"plc_conversion_rate": invoice_rate,
				"debit_to": acc("120.02"),
				"posting_date": self.today,
				"set_posting_time": 1,
				"due_date": self.today,
				"taxes_and_charges": f"KDV %20 - {ABBR}",
				"items": [{"item_code": SERVICE, "qty": 1, "rate": 100}],
			}
		)
		apply_kdv(si, "Sales Taxes and Charges Template")
		si.insert()
		si.submit()
		invoice_base = flt(120 * invoice_rate, 2)
		self.flow.assert_gl(
			"Sales Invoice",
			si.name,
			{"120.02": invoice_base, "600.01": -flt(100 * invoice_rate, 2), "391.01.04": -flt(20 * invoice_rate, 2)},
		)

		pe = get_payment_entry("Sales Invoice", si.name, bank_account=acc("102.02"))
		pe.mode_of_payment = "Wire Transfer"
		pe.reference_no = "EUR-HVL-1"
		pe.reference_date = self.today
		pe.insert()
		pe.submit()
		return si, pe

	def test_fx_sale_collected_at_a_higher_rate_books_an_exchange_gain(self):
		si, _pe = self.fx_sale(invoice_rate=30, payment_rate=32)
		self.assertEqual(outstanding("Sales Invoice", si.name), 0)
		self.assertEqual(balance("102.02"), 3840)  # 120 EUR x 32
		self.assertEqual(balance("120.02"), 0)
		self.assertEqual(balance("646.01"), -240)  # kambiyo kârı

	def test_fx_sale_collected_at_a_lower_rate_books_an_exchange_loss(self):
		si, _pe = self.fx_sale(invoice_rate=30, payment_rate=28)
		self.assertEqual(outstanding("Sales Invoice", si.name), 0)
		self.assertEqual(balance("102.02"), 3360)  # 120 EUR x 28
		self.assertEqual(balance("120.02"), 0)
		self.assertEqual(balance("656.01"), 240)  # kambiyo zararı

	# ---- 9. Türkçe banka ekstresi -> içe aktarma -> otomatik uzlaştırma ----

	def test_turkish_statement_import_and_auto_reconciliation(self):
		f = self.flow
		f.fund_bank()
		f.pay_supplier()
		f.collect_bank()
		f.deposit_cheque()
		bank_account = frappe.db.get_value("Bank Account", {"bank": BANK_NAME, "account": acc("102.01")}, "name")

		day = getdate(self.today).strftime("%d.%m.%Y")
		supplier_ref = frappe.db.get_value("Payment Entry", f.docs["supplier_payments"][0], "reference_no")
		bank_ref = frappe.db.get_value("Payment Entry", f.docs["receipts"]["Wire Transfer"], "reference_no")
		cheque_ref = frappe.db.get_value("Journal Entry", f.docs["cheque_deposit_je"], "cheque_no")
		capital_ref = frappe.db.get_value("Journal Entry", f.docs["fund_je"], "cheque_no")
		content = (
			"Tarih,Açıklama,Referans,Borç,Alacak\n"
			f'{day},Sermaye girişi,{capital_ref},,"20.000,00"\n'
			f'{day},Tedarikçi ödemesi,{supplier_ref},"6.000,00",\n'
			f'{day},Müşteri havalesi,{bank_ref},,"1.340,00"\n'
			f'{day},Çek tahsili,{cheque_ref},,"1.500,00"\n'
		)
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "akis-ekstre.csv", "content": content, "is_private": 1}
		).insert()
		log = frappe.get_doc(
			{"doctype": "Bank Statement Import Log", "bank_account": bank_account, "file": file.file_url}
		).insert()
		self.assertEqual(log.number_of_transactions, 4)
		self.assertEqual(flt(log.total_debits, 2), PURCHASE_TOTAL)
		self.assertEqual(flt(log.total_credits, 2), CAPITAL + BANK_PART + CHEQUE_PART)
		log.insert_transactions()
		self.assertEqual(frappe.db.count("Bank Transaction", {"bank_account": bank_account, "docstatus": 1}), 4)

		auto_reconcile_vouchers(
			bank_account=bank_account, from_date=self.today, to_date=self.today, filter_by_reference_date=False
		)
		statuses = frappe.get_all(
			"Bank Transaction", filters={"bank_account": bank_account, "docstatus": 1}, pluck="status"
		)
		self.assertEqual(statuses, ["Reconciled"] * 4)
		self.assertEqual(balance("102.01"), CAPITAL - PURCHASE_TOTAL + BANK_PART + CHEQUE_PART)
