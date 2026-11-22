# Faz 1 — Tenant/auth ve finansal bütünlük tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Kaynak düzeltmeleri tamamlandı; testler yazıldı ancak Bench ortamında çalıştırılmadı.**

## P1 — Kayıt/tenant yetki düzeltmeleri

| API | Dosya | Düzeltme | Test |
| --- | --- | --- | --- |
| `get_closing_balance_as_per_statement` | `erpnext/accounts/doctype/bank_account/bank_account.py` | `has_permission("Bank Account", "read", doc=bank_account)` eklendi | `test_get_closing_balance_fences_the_bank_account` |
| `get_older_unreconciled_transactions` | `erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py` | `has_permission("Bank Account", "read", doc=bank_account)` eklendi | `test_get_older_unreconciled_transactions_fences_the_bank_account` |
| `search_for_transfer_transaction` | Aynı dosya | `has_permission("Bank Transaction", "read", doc=transaction_id)` eklendi | `test_search_for_transfer_refuses_an_unauthorised_transaction` |
| `clear_clearing_date` | Aynı dosya | `has_permission(voucher_type, "write", doc=voucher_name)` eklendi | `test_clear_clearing_date_refuses_a_voucher_without_write_permission` |
| `get_account_balance` | Aynı dosya | Banka hesabının `company` ile girilen `company` parametresi eşleştirildi; uyuşmazlıkta `ValidationError` | `test_get_account_balance_refuses_mismatched_company` |

Tüm testler `erpnext/accounts/doctype/bank_reconciliation_tool/test_bank_reconciliation_tool.py` içindedir.

## P2 — İçe aktarma bütünlüğü

| Düzeltme | Dosya | Açıklama |
| --- | --- | --- |
| Çift import engellendi | `erpnext/accounts/doctype/bank_statement_import_log/bank_statement_import_log.py` | `status == "Completed"` iken `frappe.throw`; daha önce sessizce `return` vardı |
| Satır bazlı idempotency | Aynı dosya | Her işlem `Bank Transaction` mevcudiyet kontrolü (banka hesabı + tarih + tutar + referans) ile atlanır |
| Skipped sayacı | Aynı dosya | Atlanan satır sayısı loglanır ve `add_comment` ile belgeye yazılır |
| Kural sadece yeni işlem varsa çalışır | Aynı dosya | `progress > 0` kontrolü eklendi; tüm satırlar atlandıysa kural çalıştırılmaz |

## Frontend güvenlik düzeltmeleri

| Düzeltme | Dosya | Açıklama |
| --- | --- | --- |
| stored-XSS engellendi | `banking/src/components/ui/markdown.tsx` | `rehypeRaw` kaldırıldı; kullanıcı verileri artık raw HTML olarak render edilmiyor |
| Hassas veri temizlendi | `banking/src/components/features/BankReconciliation/bankRecAtoms.ts` | `ActionLogItem.voucher.doc` kaldırıldı; `bankTransaction` tipi `Pick` ile sınırlandı |

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ `compileall` temiz |
| Faz 0 manifesto | ✅ `validate_cadro_baseline.py` yeşil |
| Regresyon testleri | ✅ 5 yeni yetki testi + mevcut testlerle uyumlu (Bench çalıştırılmadı) |
| Frontend dep kilitleri | ✅ `cadro.baseline.json` değişmedi |

## Bench testleri (çalıştırılmadı)

Windows ortamında Frappe Bench bulunmadığından aşağıdaki testler yazıldı ancak çalıştırılmadı:

```bash
bench --site test_site run-tests --module erpnext.accounts.doctype.bank_reconciliation_tool.test_bank_reconciliation_tool --lightmode
bench --site test_site run-tests --module erpnext.accounts.doctype.bank_statement_import_log.test_bank_statement_import_log --lightmode
```

## Sonraki adım

Faz 2 — Tekrarlanabilir üretim ve kontrollü pilot altyapısı.  
Öncelik: Docker/Compose üretim imajı, CI pin'leri, staging, yedekleme/geri yükleme.