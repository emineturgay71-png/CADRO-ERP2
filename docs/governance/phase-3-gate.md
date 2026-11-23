# Faz 3 — Tam Türkçe ürün deneyimi tamamlanma kaydı

Tarih: 20 Kasım 2026 (güncelleme: 23 Kasım 2026).
Durum: **Türkçe arayüz büyük ölçüde tamam: ERPNext kataloğu %99,99 dolu, Frappe çekirdeği için CADRO katmanı eklendi, bankacılık ekranları tarayıcıda Faz 3 kapsamında gezildi. Kalan boşluklar aşağıda.**

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

(20 Kasım ölçümü; güncel durum aşağıdaki "Güncel durum" bölümündedir.)

1589 boş `msgstr` Crowdin üzerinden çeviri ekibiyle tamamlanmalıdır. Bu otomatik çeviri aracıyla topluca doldurulmamalıdır.

Çeviri tamamlandığında:
```bash
python scripts/po_quality_report.py  # boş çeviri sayısını tekrar ölç
bench --site test_site run-tests --module erpnext.tests.test_init --lightmode  # PO geçerlilik testi
```

## Güncel durum (23 Kasım 2026)

### Çeviri kapsamı

| Katman | Durum |
| --- | --- |
| `erpnext/locale/tr.po` | 12.651 birim, 12.650 çevrilmiş (%99,99), 0 fuzzy (`scripts/po_quality_report.py`) |
| Frappe çekirdeği | Frappe'in kendi kataloğunda boş kalan ~3.240 metinden ~2.940'ı `cadro/locale/frappe_tr_overlay.po` ile çevrildi (Desk, Studio, Flow, otomasyon, sunucu mesajları). 297 metin bilerek çevrilmedi (teknik kimlikler, marka adları, geliştirici notları) |
| Terim sözlüğü | `Prospect`=Aday Firma, `Lead`=Potansiyel Müşteri, `Timesheet`=Zaman Çizelgesi, `Share Transfer`=Hisse Devri, `Share Type`=Hisse Türü |
| Dağıtım | Katman her konteyner başlangıcında `tr.po`'ya birleştirilir ve `.mo` derlenir (`cadro/locale/merge_po.py`) |
| Tarama | Faz 0–7 (525 rota) taramasında 0 hata sayfası; çevrilmemiş kalanlar marka adları, HTML parçaları ve veri kayıtlarıdır |

### Bankacılık ekranlarının tarayıcıda gezilmesi

Pilotun yedeğinden kurulan bir demo sitede (6 örnek işlem, bir banka hesabı) gezildi: Eşleştir ve Uzlaştır, Mutabakat Ekstresi, İşlemler, Takas Özeti, Yanlış Takas Edildi, Ayarlar (Tercihler, Eşleştirme Kuralları, Klavye Kısayolları), ekstre içe aktarma sayfası. Ödeme Kaydet akışı uçtan uca çalıştırıldı: işlem seçildi, cari ve hesap otomatik doldu, ödeme girişi oluşturuldu, işlem uzlaştırıldı (1/6, kapanış bakiyesi `₺ 15.000,00`).

Biçimler doğrulandı: tarih `dd.mm.yyyy`, tutar `₺ 1.250,75`, ay adları Türkçe.

Gezinti sırasında bulunan ve düzeltilen sorunlar:

| Sorun | Düzeltme |
| --- | --- |
| `or`, `Select {0}`, cari türü listesi ve `Select Customer` gibi yer tutucular İngilizce | `_()` ile sarıldı; belge türü adları da çevrilir hale getirildi |
| `Yeni Customer Oluştur`, eylem günlüğündeki belge türü adları | Belge türü adı `_()` ile çevrilerek yerleştirildi |
| Sunucu mesajlarında ve açıklama metinlerinde `<strong>…</strong>` etiketleri düz metin olarak görünüyordu (XSS düzeltmesi sonrası HTML çizilmiyor) | `MarkdownRenderer` basit etiketleri Markdown'a çevirir, diğer etiketleri siler; HTML yine çizilmez |
| Sunucu mesajında `invoices` / `orders` İngilizce | Katalog girdileri eklendi |
| Ekstre ayrıntılarında algılanan tutar biçimi, `Closing Balance as of`, `(e.g. …)` İngilizce | Katalog girdileri eklendi, ekranda çevriliyor |
| `i̇şlemler` gibi bozuk "i̇" karakteri (i + birleşik nokta) ve `Returned` karşılığı | `tr.po` düzeltildi; sayı sonrası çoğul `işlem` yapıldı |
| `Close` ekran okuyucu etiketi | Çevrildi |
| Bankacılık sayfasında gerçek zamanlı bağlantı `:9000` portuna gidiyordu (SDK, standart dışı portta geliştirme düzeni varsayıyor) | Bağlantı sayfanın portunu kullanır; nginx arkasında çalışır |

### Açık kalanlar

- Ekstre içe aktarmada sütun eşleme adımı (başlık satırı ve tür seçimi) ve gerçek bir CSV'nin içe aktarılması uçtan uca denenmedi; sayfa ve ilk adım Türkçe doğrulandı. Türkçe sütun başlıkları (`Tarih`, `Tutar`) otomatik tanınmıyor, başlık satırı kullanıcı tarafından belirtilir.
- İşlem/Banka Girişi ve Transfer pencereleri, kural oluşturma ve geri alma akışları ayrıca gezilmedi.
- Bazı erişilebilirlik etiketleri (`Close toast`, `Select all rows`) üçüncü taraf bileşenlerden İngilizce gelir.
- Türkiye hesap planında `Bank` türünde varsayılan bir genel muhasebe hesabı yoktur; banka hesabı eklemeden önce `102 BANKALAR` altında hesap oluşturulmalıdır. Kurulum sihirbazına varsayılan banka hesabı eklenmesi ayrı bir iştir.
- Baskı formatları (29 adet) ve e-posta şablonlarında alıcı dili için ayrı kapsam (Faz 4) geçerlidir; `default_print_language` değiştirilmedi.
- Bankacılık dışı ERPNext ekranlarının tamamı tarayıcıda tek tek gezilmedi; kapsam otomatik taramalarla (525 rota) ölçülmüştür.

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
| PO raporu | ✅ %99,99 dolu (23 Kasım), 0 fuzzy |
| Frontend build | ✅ `yarn build` konteynerde çalışıyor (imaj güncellemesinde yeniden derlenir) |

## Sonraki adım

Faz 4 — Türkiye muhasebesi ve e-belge/e-defter uyum ürünü.  
Öncelik: Mali müşavir onaylı hesap planı/vergi matrisi, e-belge adaptör mimarisi.