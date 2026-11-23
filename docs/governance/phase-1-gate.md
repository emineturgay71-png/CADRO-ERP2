# Faz 1 — Tenant/auth ve finansal bütünlük tamamlanma kaydı

Tarih: 20 Kasım 2026 (Bench test sonuçları: 23 Kasım 2026).
Durum: **Kaynak düzeltmeleri tamamlandı; bankacılık testleri MariaDB ve PostgreSQL üzerinde Bench'te çalıştırıldı ve geçti.**

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
| Regresyon testleri | ✅ Bench'te çalıştırıldı; sonuçlar aşağıda |
| Frontend dep kilitleri | ✅ `cadro.baseline.json` değişmedi |

## Bench test sonuçları (23 Kasım 2026)

Ortam: `cadro-bench` imajı (Python 3.14, Frappe `96c27e16ed`, ERPNext `920f1d5` + CADRO overlay), her koşu için geçici site, `allow_tests`. MariaDB 11.8 ve PostgreSQL 17 üzerinde aynı modül listesi çalıştırıldı.

| Modül | Test | MariaDB | PostgreSQL |
| --- | --- | --- | --- |
| `bank_account` | 1 | ✅ | ✅ |
| `bank_account_balance` | 1 | ✅ | ✅ |
| `bank_transaction` | 10 (1 atlandı) | ✅ | ✅ |
| `bank_transaction` ücretler | 10 | ✅ | ✅ |
| `bank_transaction` auto match party | 5 | ✅ | ✅ |
| `bank_transaction_rule` | 20 | ✅ | ✅ |
| `bank_statement_import_log` | 23 | ✅ | ✅ |
| `bank_statement_import` | 17 | ✅ | ✅ |
| `bank_clearance` | 3 (1 atlandı) | ✅ | ✅ |
| `bank_reconciliation_tool` | 34 | ✅ | ✅ |
| `bank_guarantee` | 7 | ✅ | ✅ |

Koşu sırasında bulunan ve düzeltilen sorunlar:

- `test_bank_reconciliation_tool.py` içindeki `RATE_METHOD` sabiti önceki commit'te yanlışlıkla silinmişti (5 test `NameError`); geri eklendi.
- Üç yetki testi, rol düzeyinde `Bank Account` okuma izni olan `Accounts User` kullanıcısıyla "izin yok" varsaymıştı; kullanıcı başka bir şirkete sınırlanarak düzeltildi. Üretim kodu değişmedi.
- İmajda Chromium'un paylaşımlı kütüphaneleri yoktu; PDF ekstre testleri (`bank_statement_import_log`) ve PDF üretimi çalışmıyordu. `cadro/Dockerfile` düzeltildi.
- PostgreSQL site kurulumu için imajda `psql`/`pg_dump` yoktu; `postgresql-client` Dockerfile'a eklendi.
- Testler için `freezegun` gerekir; imajda yoktur (yalnızca geliştirme/test bağımlılığı).

Tekrar koşmak için:

```bash
bench new-site test.localhost --db-type mariadb ... --install-app erpnext
bench --site test.localhost set-config allow_tests true
bench --site test.localhost run-tests --module erpnext.accounts.doctype.bank_reconciliation_tool.test_bank_reconciliation_tool
```

## Açık kalanlar

- Bankacılık dışındaki ERPNext modüllerinin tam test paketi çalıştırılmadı.
- Bankacılık React ekranları (işlem, mutabakat) tarayıcıda uçtan uca gezilmedi.
- Yük ve eşzamanlılık altında import idempotency denenmedi.

## Sonraki adım

Faz 2 — Tekrarlanabilir üretim ve kontrollü pilot altyapısı.  
Öncelik: Docker/Compose üretim imajı, CI pin'leri, staging, yedekleme/geri yükleme.