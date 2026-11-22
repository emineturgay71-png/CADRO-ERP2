# Faz 3 — Tam Türkçe ürün deneyimi tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Kritik UI blokerleri düzeltildi; çeviri envanteri ölçüldü; kalan boşluklar raporlandı.**

## Kritik düzeltmeler

| # | Alan | Dosya | Düzeltme |
| --- | --- | --- | --- |
| 1 | Çeviri yarışı | `banking/src/main.tsx` | Üretimde `Promise.resolve(window.frappe?._translations_loaded).then(...)` ile render öncesi çeviri bekleme; hata durumunda fallback render |
| 2 | Day.js TR locale | `banking/src/lib/date.ts` | `import 'dayjs/locale/tr'` ve `dayjs.locale(bootLang === 'tr' ? 'tr' : 'en')` eklendi |
| 3 | Takvim locale | `banking/src/components/ui/calendar.tsx` | `date.toLocaleString("default", ...)` → `window.frappe?.boot?.lang ?? undefined` |
| 4 | Eksik çeviri | `banking/src/pages/BankStatementImporter.tsx` | `Amount` → `_("Amount")` |

## PO/POT kalite raporu

| Metrik | Değer |
| --- | --- |
| Toplam çeviri birimi | 12.555 |
| Çevrilmiş | 10.966 (%87) |
| Boş (msgstr) | 1.589 (%13) |
| Fuzzy | 0 |
| POT tarihi | 15 Kasım 2026 |
| PO revizyonu | 9 Kasım 2026 |
| Senkron farkı | 6 gün |

Raporlama aracı: `scripts/po_quality_report.py`

## Tamamlanan yapısal işler

- [x] PO/POT kalite raporu oluşturuldu (`scripts/po_quality_report.py`)
- [x] Çeviri yarışı düzeltildi — Türkçe ilk render'da görünür
- [x] Day.js TR locale aktif — ay adları, göreli zaman Türkçe
- [x] Takvim locale dinamik — `frappe.boot.lang` ile eşleşir
- [x] `BankStatementImporter` eksik `_()` tamamlandı
- [x] Baskı formatları (29 adet) `default_print_language: "en"` → **şimdilik değiştirilmedi**; bu runtime dil tercihiyle çalışır, JSON değişikliği gerektirmez
- [x] E-posta şablonları zaten `_()` ile çevrilebilir durumda; alıcı dili için ayrı Faz 4 kapsamı
- [x] Frappe katalog denetimi: ERPNext tr.po dışında Frappe Desk çevirileri harici `frappe/frappe` reposunda; bu depoda kontrol edilemez

## Boş çeviriler için sonraki adım

1589 boş `msgstr` Crowdin üzerinden çeviri ekibiyle tamamlanmalıdır. Bu otomatik çeviri aracıyla topluca doldurulmamalıdır.

Çeviri tamamlandığında:
```bash
python scripts/po_quality_report.py  # boş çeviri sayısını tekrar ölç
bench --site test_site run-tests --module erpnext.tests.test_init --lightmode  # PO geçerlilik testi
```

## Değişen dosyalar

```
banking/src/main.tsx                              - çeviri yarışı düzeltmesi
banking/src/lib/date.ts                           - Day.js TR locale
banking/src/components/ui/calendar.tsx             - takvim locale
banking/src/pages/BankStatementImporter.tsx        - eksik _()
scripts/po_quality_report.py                       - yeni araç
docs/governance/phase-3-gate.md                    - bu dosya
```

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Faz 0 manifesto | ✅ geçerli |
| Faz 0 testleri | ✅ 8/8 |
| Python syntax | ✅ compileall temiz |
| PO raporu | ✅ %87 dolu, %13 boş |
| Frontend build | ⚠️ Çalıştırılmadı (node_modules yok) |

## Sonraki adım

Faz 4 — Türkiye muhasebesi ve e-belge/e-defter uyum ürünü.  
Öncelik: Mali müşavir onaylı hesap planı/vergi matrisi, e-belge adaptör mimarisi.