# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public v3. See license.txt
"""CADRO ana akış testi (Türkiye): alım -> depolama -> satış -> tahsilat -> banka mutabakatı.

Ana akış (`TradingFlow`) adım adım ilerler. Her adım kendi belge, stok ve muhasebe beklentisini
hemen doğrular, bu yüzden bir adım bozulursa test tam o adımda durur. Her alt senaryo testi
ihtiyaç duyduğu önceki adımları kendisi çalıştırır; böylece tek başına da koşabilir. En sonda
`test_main_flow` bütün zinciri çalıştırıp defterleri bütünüyle denetler.

Çalıştırma:
    bench --site <site> run-tests --module erpnext.regional.turkey.test_main_flow

Taze bir Türkiye şirketi hesap planıyla ticarete hazır gelmediği için `setup_company` eksik
hesapları ve şirket varsayılanlarını kurar. Neleri kurması gerektiği `GAPS` listesine yazılır
ve test çıktısında "CADRO-GAP" satırlarıyla görünür: ürünün kendisinin karşılaması gereken
eksiklerin listesidir.
"""

import frappe
from frappe.utils import add_days, flt, nowdate

from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.services.taxes import _get_taxes_and_charges
from erpnext.tests.utils import ERPNextTestSuite

COMPANY = "CADRO Akış Test Ltd"
ABBR = "CAT"
SUPPLIER = "Akış Tedarikçi A.Ş."
CUSTOMER = "Akış Müşteri Ltd."
ITEM = "AKIS-MAL-001"
BANK_NAME = "Akış Test Bankası"

BUY_QTY, BUY_RATE = 100, 50
SELL_QTY, SELL_RATE = 40, 80
KDV = 0.20
CAPITAL = 20000

PURCHASE_NET = BUY_QTY * BUY_RATE  # 5000
PURCHASE_KDV = PURCHASE_NET * KDV  # 1000
PURCHASE_TOTAL = PURCHASE_NET + PURCHASE_KDV  # 6000
SALE_NET = SELL_QTY * SELL_RATE  # 3200
SALE_KDV = SALE_NET * KDV  # 640
SALE_TOTAL = SALE_NET + SALE_KDV  # 3840
COGS = SELL_QTY * BUY_RATE  # 2000

CASH_PART, CHEQUE_PART = 1000, 1500
BANK_PART = SALE_TOTAL - CASH_PART - CHEQUE_PART  # 1340

GAPS: list[str] = []

# Satılan malın maliyet hesabı. Türkiye planında 621 Income köküne bağlı olduğundan ERPNext'in
# "varsayılan maliyet hesabı" kuralını (Expense kökü) karşılamıyor; bkz. setup_company.
COGS_NO = "7.99"


# ---------------------------------------------------------------------------
# Şirket ve temel veri
# ---------------------------------------------------------------------------


def acc(number):
	"""Şirketin hesabını hesap numarasından bul."""
	name = frappe.db.get_value("Account", {"company": COMPANY, "account_number": number}, "name")
	if not name:
		raise AssertionError(f"{COMPANY} hesap planında {number} numaralı hesap yok")
	return name


def ensure_account(number, name, parent_number, account_type=""):
	existing = frappe.db.get_value("Account", {"company": COMPANY, "account_number": number}, "name")
	if existing:
		if account_type and frappe.db.get_value("Account", existing, "account_type") != account_type:
			frappe.db.set_value("Account", existing, "account_type", account_type)
			GAPS.append(f"{number} hesabının türü '{account_type}' olmalı")
		return existing
	parent = acc(parent_number)
	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": name,
			"account_number": number,
			"parent_account": parent,
			"company": COMPANY,
			"account_type": account_type,
			"is_group": 0,
		}
	).insert()
	GAPS.append(f"{number} {name} yaprak hesabı yok ({parent_number} grubunun altına eklendi)")
	return doc.name


def ensure_fiscal_year():
	today = nowdate()
	if frappe.db.exists(
		"Fiscal Year", {"year_start_date": ["<=", today], "year_end_date": [">=", today], "disabled": 0}
	):
		return
	year = today[:4]
	frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": f"CADRO {year}",
			"year_start_date": f"{year}-01-01",
			"year_end_date": f"{year}-12-31",
		}
	).insert()


def setup_company():
	"""Türkiye şirketini sihirbazın yaptığı gibi oluştur, ticarete hazır hale getir. Tekrar çalıştırılabilir."""
	GAPS.clear()
	ensure_fiscal_year()
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": ABBR,
				"default_currency": "TRY",
				"country": "Türkiye",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Turkey - Chart of Accounts",
				"enable_perpetual_inventory": 1,
			}
		).insert()

	stock = ensure_account("153.01", "TİCARİ MALLAR TL", "153", "Stock")
	cheques = ensure_account("101.01", "ALINAN ÇEKLER TL", "101", "Cash")
	bank = ensure_account("102.01", "VADESİZ TL BANKA", "102", "Bank")
	sales = ensure_account("600.01", "YURT İÇİ SATIŞLAR TL", "600", "Income Account")
	cogs = ensure_account(COGS_NO, "SATILAN TİCARİ MALLAR MALİYETİ TL", "7", "Cost of Goods Sold")
	GAPS.append(
		"621 Satılan Ticari Mallar Maliyeti, 6 numaralı Income köküne bağlı: ERPNext varsayılan gider/maliyet "
		"hesabı için Expense kökü ister; test maliyet hesabını 7 köküne (7.99) koyuyor"
	)
	srbnb = ensure_account("320.90", "ALINAN FATURASIZ MALLAR", "320", "Stock Received But Not Billed")
	payable = ensure_account("320.01", "SATICILAR TRY", "320", "Payable")
	capital = ensure_account("500.01", "ÖDENMİŞ SERMAYE TL", "500")

	company = frappe.get_doc("Company", COMPANY)
	wanted = {
		"default_inventory_account": stock,
		"default_payable_account": payable,
		"default_income_account": sales,
		"default_expense_account": cogs,
		"stock_received_but_not_billed": srbnb,
		"default_bank_account": bank,
		"default_cash_account": acc("100.01"),
	}
	changed = [field for field, value in wanted.items() if company.get(field) != value]
	for field in changed:
		company.set(field, wanted[field])
	if changed:
		GAPS.append("şirket varsayılan hesapları kuruldu: " + ", ".join(changed))
		company.save()

	for mode, account in (("Cash", acc("100.01")), ("Cheque", cheques), ("Wire Transfer", bank)):
		if not frappe.db.exists("Mode of Payment", mode):
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode, "type": "Bank"}).insert()
		mop = frappe.get_doc("Mode of Payment", mode)
		if not any(row.company == COMPANY for row in mop.accounts):
			mop.append("accounts", {"company": COMPANY, "default_account": account})
			mop.save()
			GAPS.append(f"ödeme yöntemi '{mode}' için şirket hesabı tanımlandı")

	if not frappe.db.exists("Bank", BANK_NAME):
		frappe.get_doc({"doctype": "Bank", "bank_name": BANK_NAME}).insert()
	if not frappe.db.exists("Bank Account", {"bank": BANK_NAME, "account": bank}):
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "Vadesiz TL",
				"bank": BANK_NAME,
				"account": bank,
				"company": COMPANY,
				"is_company_account": 1,
			}
		).insert()

	if not frappe.db.exists("Supplier", SUPPLIER):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": SUPPLIER,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}),
				"default_currency": "TRY",
			}
		).insert()
	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": CUSTOMER,
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}),
				"default_currency": "TRY",
			}
		).insert()
	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_name": "Akış Test Malı",
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"item_defaults": [{"company": COMPANY, "default_warehouse": f"Stores - {ABBR}"}],
			}
		).insert()
	frappe.db.commit()  # nosemgrep -- testler arası paylaşılan şirket verisi; her test sonda geri alınır


# ---------------------------------------------------------------------------
# Defter yardımcıları
# ---------------------------------------------------------------------------


def balance(number):
	"""Hesabın borç - alacak bakiyesi (iptal edilmemiş kayıtlar)."""
	row = frappe.db.sql(
		"select coalesce(sum(debit - credit), 0) from `tabGL Entry` where company=%s and account=%s and is_cancelled=0",
		(COMPANY, acc(number)),
	)
	return flt(row[0][0], 2)


def voucher_gl(doctype, name):
	"""Belgenin GL etkisi: {hesap numarası: borç - alacak}, sıfır olanlar atılır."""
	rows = frappe.get_all(
		"GL Entry",
		filters={"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
		fields=["account", "debit", "credit"],
	)
	net = {}
	for row in rows:
		number = frappe.db.get_value("Account", row.account, "account_number")
		net[number] = flt(net.get(number, 0) + row.debit - row.credit, 2)
	return {number: value for number, value in net.items() if value}


def bin_of(item, warehouse):
	row = frappe.db.get_value("Bin", {"item_code": item, "warehouse": warehouse}, ["actual_qty", "stock_value"])
	return (flt(row[0]), flt(row[1], 2)) if row else (0.0, 0.0)


def outstanding(doctype, name):
	return flt(frappe.db.get_value(doctype, name, "outstanding_amount"), 2)


def apply_kdv(doc, master_doctype):
	for row in _get_taxes_and_charges(master_doctype, f"KDV %20 - {ABBR}"):
		doc.append("taxes", row)


# ---------------------------------------------------------------------------
# Ana akış
# ---------------------------------------------------------------------------


class TradingFlow:
	def __init__(self, test):
		self.t = test
		self.today = nowdate()
		self.warehouse = f"Stores - {ABBR}"
		self.second_warehouse = f"Finished Goods - {ABBR}"
		self.done = set()
		self.docs = {}

	def assert_gl(self, doctype, name, expected):
		self.t.assertEqual(voucher_gl(doctype, name), {k: flt(v, 2) for k, v in expected.items()}, f"{doctype} {name} GL")

	def _once(self, step):
		if step in self.done:
			return False
		self.done.add(step)
		return True

	# -- Sermaye: bankaya açılış parası ------------------------------------
	def fund_bank(self):
		if not self._once("fund_bank"):
			return
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Bank Entry",
				"company": COMPANY,
				"posting_date": self.today,
				"cheque_no": "SERMAYE-1",
				"cheque_date": self.today,
				"accounts": [
					{"account": acc("102.01"), "debit_in_account_currency": CAPITAL},
					{"account": acc("500.01"), "credit_in_account_currency": CAPITAL},
				],
			}
		).insert()
		je.submit()
		self.docs["fund_je"] = je.name
		self.assert_gl("Journal Entry", je.name, {"102.01": CAPITAL, "500.01": -CAPITAL})

	# -- 1. Alım: sipariş -> irsaliye -> fatura ------------------------------
	def purchase(self):
		if not self._once("purchase"):
			return
		from erpnext.buying.doctype.purchase_order.mapper import make_purchase_receipt
		from erpnext.stock.doctype.purchase_receipt.mapper import make_purchase_invoice

		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": COMPANY,
				"supplier": SUPPLIER,
				"currency": "TRY",
				"transaction_date": self.today,
				"schedule_date": self.today,
				"set_warehouse": self.warehouse,
				"taxes_and_charges": f"KDV %20 - {ABBR}",
				"items": [
					{
						"item_code": ITEM,
						"qty": BUY_QTY,
						"rate": BUY_RATE,
						"schedule_date": self.today,
						"warehouse": self.warehouse,
					}
				],
			}
		)
		apply_kdv(po, "Purchase Taxes and Charges Template")
		po.insert()
		po.submit()
		self.t.assertEqual(flt(po.grand_total, 2), PURCHASE_TOTAL)

		pr = make_purchase_receipt(po.name)
		pr.insert()
		pr.submit()
		self.docs.update(po=po.name, pr=pr.name)
		# İrsaliye: mal depoya girer, henüz faturalanmadığı için "faturasız mallar" hesabına alacak.
		self.assert_gl("Purchase Receipt", pr.name, {"153.01": PURCHASE_NET, "320.90": -PURCHASE_NET})
		self.t.assertEqual(bin_of(ITEM, self.warehouse), (BUY_QTY, PURCHASE_NET))

		pi = make_purchase_invoice(pr.name)
		pi.bill_no = "TED-0001"
		pi.bill_date = self.today
		pi.insert()
		pi.submit()
		self.docs["pi"] = pi.name
		# Fatura: geçici hesap kapanır, KDV indirilecek, tedarikçiye borç doğar.
		self.assert_gl(
			"Purchase Invoice",
			pi.name,
			{"320.90": PURCHASE_NET, "191.01.04": PURCHASE_KDV, "320.01": -PURCHASE_TOTAL},
		)
		self.t.assertEqual(outstanding("Purchase Invoice", pi.name), PURCHASE_TOTAL)
		self.t.assertEqual(balance("153.01"), PURCHASE_NET)
		self.t.assertEqual(balance("320.90"), 0)

	# -- 2. Tedarikçiye banka ile ödeme --------------------------------------
	def pay_supplier(self, amount=PURCHASE_TOTAL):
		self.fund_bank()
		self.purchase()
		if not self._once("pay_supplier"):
			return
		pe = get_payment_entry("Purchase Invoice", self.docs["pi"], party_amount=amount, bank_account=acc("102.01"))
		pe.mode_of_payment = "Wire Transfer"
		pe.reference_no = f"HVL-ODEME-{len(self.docs)}"
		pe.reference_date = self.today
		pe.insert()
		pe.submit()
		self.docs.setdefault("supplier_payments", []).append(pe.name)
		self.assert_gl("Payment Entry", pe.name, {"320.01": amount, "102.01": -amount})
		self.t.assertEqual(outstanding("Purchase Invoice", self.docs["pi"]), PURCHASE_TOTAL - sum(
			frappe.db.get_value("Payment Entry", name, "paid_amount") for name in self.docs["supplier_payments"]
		))

	# -- 3. Depolama: depolar arası transfer ---------------------------------
	def store(self, qty=10):
		self.purchase()
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

		stock_before = balance("153.01")
		se = make_stock_entry(
			item_code=ITEM, source=self.warehouse, target=self.second_warehouse, qty=qty, company=COMPANY
		)
		self.docs["transfer"] = se.name
		self.t.assertEqual(bin_of(ITEM, self.warehouse)[0], BUY_QTY - qty)
		self.t.assertEqual(bin_of(ITEM, self.second_warehouse), (qty, qty * BUY_RATE))
		# Aynı stok hesabında kalan transfer defter bakiyesini değiştirmez.
		self.t.assertEqual(balance("153.01"), stock_before)

	# -- 4. Satış: sipariş -> irsaliye -> fatura -----------------------------
	def sell(self, qty=SELL_QTY):
		self.purchase()
		if not self._once("sell"):
			return
		from erpnext.selling.doctype.sales_order.mapper import make_delivery_note
		from erpnext.stock.doctype.delivery_note.mapper import make_sales_invoice

		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "TRY",
				"transaction_date": self.today,
				"delivery_date": self.today,
				"set_warehouse": self.warehouse,
				"taxes_and_charges": f"KDV %20 - {ABBR}",
				"items": [
					{
						"item_code": ITEM,
						"qty": qty,
						"rate": SELL_RATE,
						"delivery_date": self.today,
						"warehouse": self.warehouse,
					}
				],
			}
		)
		apply_kdv(so, "Sales Taxes and Charges Template")
		so.insert()
		so.submit()

		stock_qty, stock_value = bin_of(ITEM, self.warehouse)  # depoya transfer yapıldıysa 100'den azdır
		dn = make_delivery_note(so.name)
		dn.insert()
		dn.submit()
		self.docs.update(so=so.name, dn=dn.name)
		cost = qty * BUY_RATE
		# Giden irsaliye: mal stoktan çıkar, maliyet gider yazılır.
		self.assert_gl("Delivery Note", dn.name, {COGS_NO: cost, "153.01": -cost})
		self.t.assertEqual(bin_of(ITEM, self.warehouse), (stock_qty - qty, stock_value - cost))

		si = make_sales_invoice(dn.name)
		si.insert()
		si.submit()
		self.docs["si"] = si.name
		net = qty * SELL_RATE
		self.assert_gl(
			"Sales Invoice",
			si.name,
			{"120.01": net * (1 + KDV), "600.01": -net, "391.01.04": -net * KDV},
		)
		self.t.assertEqual(outstanding("Sales Invoice", si.name), net * (1 + KDV))

	# -- 5. Tahsilat: nakit, çek, havale -------------------------------------
	def _receive(self, mode, amount, account_number, reference):
		self.sell()
		pe = get_payment_entry("Sales Invoice", self.docs["si"], party_amount=amount, bank_account=acc(account_number))
		pe.mode_of_payment = mode
		pe.reference_no = reference
		pe.reference_date = self.today if mode != "Cheque" else add_days(self.today, 30)
		pe.insert()
		pe.submit()
		self.t.assertEqual(pe.paid_to, acc(account_number), f"{mode} tahsilatı doğru hesaba gitmeli")
		self.assert_gl("Payment Entry", pe.name, {account_number: amount, "120.01": -amount})
		self.docs.setdefault("receipts", {})[mode] = pe.name
		return pe

	def collect_cash(self, amount=CASH_PART):
		if self._once("collect_cash"):
			self._receive("Cash", amount, "100.01", "KASA-1")

	def collect_cheque(self, amount=CHEQUE_PART):
		if self._once("collect_cheque"):
			self._receive("Cheque", amount, "101.01", "CEK-0001")

	def collect_bank(self, amount=BANK_PART):
		if self._once("collect_bank"):
			self._receive("Wire Transfer", amount, "102.01", "HVL-TAHSILAT-1")

	def collect_all(self):
		self.collect_cash()
		self.collect_cheque()
		self.collect_bank()
		self.t.assertEqual(outstanding("Sales Invoice", self.docs["si"]), 0)
		self.t.assertEqual(frappe.db.get_value("Sales Invoice", self.docs["si"], "status"), "Paid")

	# -- 6. Çekin bankaya yatırılması ----------------------------------------
	def deposit_cheque(self, amount=CHEQUE_PART):
		self.collect_cheque()
		self.fund_bank()
		if not self._once("deposit_cheque"):
			return
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Bank Entry",
				"company": COMPANY,
				"posting_date": self.today,
				"cheque_no": "CEK-0001",
				"cheque_date": self.today,
				"accounts": [
					{"account": acc("102.01"), "debit_in_account_currency": amount},
					{"account": acc("101.01"), "credit_in_account_currency": amount},
				],
			}
		).insert()
		je.submit()
		self.docs["cheque_deposit_je"] = je.name
		self.assert_gl("Journal Entry", je.name, {"102.01": amount, "101.01": -amount})
		self.t.assertEqual(balance("101.01"), 0)

	# -- 7. Banka mutabakatı --------------------------------------------------
	def bank_reconcile(self):
		self.fund_bank()
		self.pay_supplier()
		self.collect_bank()
		self.deposit_cheque()
		if not self._once("bank_reconcile"):
			return
		bank_account = frappe.db.get_value("Bank Account", {"bank": BANK_NAME, "account": acc("102.01")}, "name")
		statement = [
			(self.docs["fund_je"], "Journal Entry", CAPITAL, 0),
			(self.docs["supplier_payments"][0], "Payment Entry", 0, PURCHASE_TOTAL),
			(self.docs["receipts"]["Wire Transfer"], "Payment Entry", BANK_PART, 0),
			(self.docs["cheque_deposit_je"], "Journal Entry", CHEQUE_PART, 0),
		]
		for voucher, doctype, deposit, withdrawal in statement:
			transaction = frappe.get_doc(
				{
					"doctype": "Bank Transaction",
					"date": self.today,
					"bank_account": bank_account,
					"deposit": deposit,
					"withdrawal": withdrawal,
					"currency": "TRY",
				}
			).insert()
			transaction.submit()
			reconcile_vouchers(transaction.name, [{"payment_doctype": doctype, "payment_name": voucher}])
			transaction.reload()
			self.t.assertEqual(transaction.status, "Reconciled", f"{doctype} {voucher}")
			self.t.assertEqual(flt(transaction.unallocated_amount, 2), 0)
		unreconciled = frappe.db.count(
			"Bank Transaction", {"bank_account": bank_account, "docstatus": 1, "status": ["!=", "Reconciled"]}
		)
		self.t.assertEqual(unreconciled, 0)
		# Ekstre hareketlerinin toplamı = defterdeki banka bakiyesi.
		statement_total = sum(deposit - withdrawal for _v, _d, deposit, withdrawal in statement)
		self.t.assertEqual(balance("102.01"), statement_total)

	# -- Varyasyon: stok sayımı farkı ----------------------------------------
	def stock_count(self, counted=98):
		self.purchase()
		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": COMPANY,
				"purpose": "Stock Reconciliation",
				"posting_date": self.today,
				"expense_account": acc("940.01"),
				"cost_center": f"Main - {ABBR}",
				"items": [
					{
						"item_code": ITEM,
						"warehouse": self.warehouse,
						"qty": counted,
						"valuation_rate": BUY_RATE,
					}
				],
			}
		).insert()
		sr.submit()
		loss = (BUY_QTY - counted) * BUY_RATE
		self.assert_gl("Stock Reconciliation", sr.name, {"940.01": loss, "153.01": -loss})
		self.t.assertEqual(bin_of(ITEM, self.warehouse), (counted, counted * BUY_RATE))

	# -- Varyasyon: satış iadesi (irsaliye + fatura) ---------------------------
	def sales_return(self, qty=5):
		self.sell()
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		dn_return = make_return_doc("Delivery Note", self.docs["dn"])
		dn_return.items[0].qty = -qty
		dn_return.insert()
		dn_return.submit()
		# İade edilen mal ilk maliyetiyle depoya döner, maliyet gideri geri alınır.
		self.assert_gl("Delivery Note", dn_return.name, {"153.01": qty * BUY_RATE, COGS_NO: -qty * BUY_RATE})

		si_return = make_return_doc("Sales Invoice", self.docs["si"])
		si_return.items[0].qty = -qty
		si_return.insert()
		si_return.submit()
		net = qty * SELL_RATE
		self.assert_gl(
			"Sales Invoice",
			si_return.name,
			{"600.01": net, "391.01.04": net * KDV, "120.01": -net * (1 + KDV)},
		)
		self.docs.update(dn_return=dn_return.name, si_return=si_return.name)

	# -- Varyasyon: çek karşılıksız çıktı -------------------------------------
	def bounce_cheque(self):
		self.collect_cash()
		self.collect_bank()
		self.deposit_cheque()
		frappe.get_doc("Journal Entry", self.docs["cheque_deposit_je"]).cancel()
		frappe.get_doc("Payment Entry", self.docs["receipts"]["Cheque"]).cancel()
		self.t.assertEqual(outstanding("Sales Invoice", self.docs["si"]), CHEQUE_PART)
		self.t.assertEqual(balance("101.01"), 0)

	# -- Varyasyon: faturayı ve irsaliyeyi iptal et ----------------------------
	def cancel_sale(self):
		self.sell()
		frappe.get_doc("Sales Invoice", self.docs["si"]).cancel()
		self.t.assertEqual((balance("120.01"), balance("600.01"), balance("391.01.04")), (0, 0, 0))
		frappe.get_doc("Delivery Note", self.docs["dn"]).cancel()
		self.t.assertEqual(balance(COGS_NO), 0)
		self.t.assertEqual(bin_of(ITEM, self.warehouse), (BUY_QTY, PURCHASE_NET))

	# -- Defterlerin bütünü ---------------------------------------------------
	def verify_books(self, expected):
		"""Mizan dengeli mi, stok değeri = stok hesabı mı, cari bakiyeler = açık faturalar mı + hesap bakiyeleri."""
		totals = frappe.db.sql(
			"select coalesce(sum(debit),0), coalesce(sum(credit),0) from `tabGL Entry` where company=%s and is_cancelled=0",
			COMPANY,
		)[0]
		self.t.assertEqual(flt(totals[0], 2), flt(totals[1], 2), "mizan: borç toplamı = alacak toplamı")

		stock_value = sum(
			flt(v, 2)
			for v in frappe.get_all("Bin", filters={"item_code": ITEM}, pluck="stock_value")
		)
		self.t.assertEqual(balance("153.01"), stock_value, "stok hesabı = stok değeri")

		open_si = sum(
			flt(v, 2)
			for v in frappe.get_all(
				"Sales Invoice", filters={"company": COMPANY, "docstatus": 1}, pluck="outstanding_amount"
			)
		)
		self.t.assertEqual(balance("120.01"), flt(open_si, 2), "alıcılar = açık satış faturaları")
		open_pi = sum(
			flt(v, 2)
			for v in frappe.get_all(
				"Purchase Invoice", filters={"company": COMPANY, "docstatus": 1}, pluck="outstanding_amount"
			)
		)
		self.t.assertEqual(-balance("320.01"), flt(open_pi, 2), "satıcılar = açık alış faturaları")

		for number, value in expected.items():
			self.t.assertEqual(balance(number), flt(value, 2), f"{number} hesap bakiyesi")

	def run_main_flow(self):
		self.fund_bank()
		self.purchase()
		self.pay_supplier()
		self.store()
		self.sell()
		self.collect_all()
		self.deposit_cheque()
		self.bank_reconcile()


MAIN_FLOW_BALANCES = {
	"102.01": CAPITAL - PURCHASE_TOTAL + BANK_PART + CHEQUE_PART,
	"100.01": CASH_PART,
	"101.01": 0,
	"120.01": 0,
	"320.01": 0,
	"320.90": 0,
	"153.01": PURCHASE_NET - COGS,
	"191.01.04": PURCHASE_KDV,
	"391.01.04": -SALE_KDV,
	"600.01": -SALE_NET,
	COGS_NO: COGS,
	"500.01": -CAPITAL,
}


class TestMainFlow(ERPNextTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_company()

	@classmethod
	def tearDownClass(cls):
		for gap in GAPS:
			print("CADRO-GAP:", gap)

	def setUp(self):
		self.flow = TradingFlow(self)

	# ---- Alt senaryolar (her biri kendi önkoşullarını çalıştırır) ----------

	def test_company_is_ready_to_trade(self):
		company = frappe.get_doc("Company", COMPANY)
		for field in (
			"default_receivable_account",
			"default_payable_account",
			"default_income_account",
			"default_expense_account",
			"default_inventory_account",
			"stock_received_but_not_billed",
			"default_bank_account",
			"default_cash_account",
		):
			self.assertTrue(company.get(field), field)
		self.assertTrue(company.enable_perpetual_inventory)
		for template in ("%20", "%10", "%1"):
			self.assertTrue(frappe.db.exists("Sales Taxes and Charges Template", f"KDV {template} - {ABBR}"))
			self.assertTrue(frappe.db.exists("Purchase Taxes and Charges Template", f"KDV {template} - {ABBR}"))

	def test_1_purchase(self):
		self.flow.purchase()

	def test_2_supplier_payment_by_bank(self):
		self.flow.pay_supplier()
		self.assertEqual(outstanding("Purchase Invoice", self.flow.docs["pi"]), 0)
		self.assertEqual(balance("320.01"), 0)

	def test_3_storage_transfer(self):
		self.flow.store()

	def test_4_sale(self):
		self.flow.sell()
		self.assertEqual(balance(COGS_NO), COGS)
		self.assertEqual(balance("153.01"), PURCHASE_NET - COGS)

	def test_5_collections_cash_cheque_bank(self):
		self.flow.collect_all()
		self.assertEqual(balance("100.01"), CASH_PART)
		self.assertEqual(balance("101.01"), CHEQUE_PART)
		self.assertEqual(balance("120.01"), 0)

	def test_6_cheque_deposit(self):
		self.flow.deposit_cheque()

	def test_7_bank_reconciliation(self):
		self.flow.bank_reconcile()

	# ---- Ana akışın tamamı -------------------------------------------------

	def test_main_flow(self):
		self.flow.run_main_flow()
		self.flow.verify_books(MAIN_FLOW_BALANCES)
		profit = -(balance("600.01") + balance(COGS_NO))
		self.assertEqual(profit, SALE_NET - COGS)

	# ---- Varyasyonlar (ana akışın dışında) --------------------------------

	def test_variant_partial_supplier_payment_leaves_the_rest_open(self):
		self.flow.pay_supplier(amount=2500)
		self.assertEqual(outstanding("Purchase Invoice", self.flow.docs["pi"]), PURCHASE_TOTAL - 2500)
		self.assertEqual(-balance("320.01"), PURCHASE_TOTAL - 2500)

	def test_variant_stock_count_loss_is_booked_to_stock_adjustment(self):
		self.flow.stock_count(98)
		self.flow.verify_books({"153.01": PURCHASE_NET - 100, "940.01": 100})

	def test_variant_sale_of_more_than_the_stock_is_refused(self):
		self.flow.purchase()
		# Test verisi negatif stoğa izin verebilir; varsayılan ERPNext davranışı (kapalı) sınanır.
		frappe.db.savepoint("oversell")
		with self.change_settings("Stock Settings", allow_negative_stock=0):
			with self.assertRaises(frappe.ValidationError):
				self.flow.sell(qty=BUY_QTY + 50)
		# Gerçek bir istekte hata bütün işlemi geri alır; testte yalnızca bu denemeyi geri al.
		frappe.db.rollback(save_point="oversell")
		self.assertEqual(bin_of(ITEM, self.flow.warehouse), (BUY_QTY, PURCHASE_NET))

	def test_variant_sales_return_restores_stock_cost_and_vat(self):
		self.flow.sales_return(5)
		self.flow.verify_books(
			{
				"153.01": PURCHASE_NET - COGS + 5 * BUY_RATE,
				COGS_NO: COGS - 5 * BUY_RATE,
				"600.01": -(SALE_NET - 5 * SELL_RATE),
				"391.01.04": -(SALE_KDV - 5 * SELL_RATE * KDV),
			}
		)

	def test_variant_bounced_cheque_reopens_the_receivable(self):
		self.flow.bounce_cheque()
		self.assertEqual(balance("120.01"), CHEQUE_PART)

	def test_variant_cancelling_the_sale_reverses_everything(self):
		self.flow.cancel_sale()
		self.flow.verify_books({"153.01": PURCHASE_NET, "191.01.04": PURCHASE_KDV})
