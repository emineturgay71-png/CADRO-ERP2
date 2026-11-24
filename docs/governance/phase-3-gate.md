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

### Ekstre içe aktarma (24 Kasım 2026)

Üç satırlık bir CSV (`Tarih,Açıklama,Tutar,Referans`; `24.11.2026`, `5000.00`, `-320.40`) demo sitede içe aktarıldı:

| Adım | Sonuç |
| --- | --- |
| Yükleme ve sütun eşleme | Sütun türü listesi Türkçe (Tarih, Açıklama, Tutar, Referans, Para Çekme, Mevduat…). Başlık satırı kullanıcı tarafından işaretlenir; Türkçe başlıklar bu turda otomatik tanınmadı (aşağıdaki düzeltmeyle tanınır) |
| Biçim algısı | Tarih `DD.MM.YYYY`, tutar "pozitif/negatif değerler"; önizleme 3 işlem, borç `₺ 12.820,40`, alacak `₺ 5.000,00` |
| İçe aktarma | 3 işlem oluştu, uzlaştırma ekranına geçildi, `Mutabık 0 / 3` |
| Aynı dosyanın tekrarı | "Çakışan İşlemler" uyarısı gösterildi; yine de içe aktarılınca **0 yeni kayıt** oluştu (veritabanında 9 işlem: 6 örnek + 3), günlükte "3 yinelenen satır atlandı" notu |

Gezilen pencereler: Banka Girişi ve Transfer (tamamen Türkçe), Ödeme Kaydet (önceki turda uçtan uca).

Bu turda bulunan: günlük notu `Imported {0} transactions (skipped {1} duplicate rows).` İngilizce kalıyordu; katalog girdisi eklendi.

### Türkçe başlık ve sayı tanıma

Ekstre içe aktarıcı yalnızca İngilizce başlıkları tanıyor ve `1.250,75` gibi sayıları `1.25075` okuyordu. Düzeltme (`bank_statement_import_log.py`):

- `fold_text`: Türkçe `İ`/`ı` ve aksanları katlar (`İŞLEM TARİHİ` → `islem tarihi`).
- Başlık sözlüğü: `Tarih`, `İşlem Tarihi`, `Açıklama`/`Detay`, `Tutar`/`Miktar`, `Borç`, `Alacak`, `Borç/Alacak`, `İşlem Türü`, `Referans`/`Dekont`/`İşlem No`, `Bakiye`/`Kalan`. `Valör Tarihi` işlem tarihi sütununun yerini almaz.
- Sayılar: iki ayraç varsa sonuncusu ondalık; tek virgül `^\d{1,3}(,\d{3})+$` ise binlik, değilse ondalık (`320,40`); `1.250.000` binlik; `24.11.2026` gibi tarihler sayı sayılmaz.
- `Borç`/`Alacak` tür sütunu değerleri tanınır.
- 6 yeni birim test; ekstre içe aktarma günlüğü (29), içe aktarma (17) ve banka uzlaştırma (34) testleri MariaDB üzerinde geçti.

### XLSX ve PDF içe aktarma (demo site, yeni imaj)

| Dosya | Sonuç |
| --- | --- |
| XLSX: üstte `HESAP HAREKETLERİ` başlığı, boş satır, büyük harfli `VALÖR TARİHİ / İŞLEM TARİHİ / AÇIKLAMA / REFERANS / BORÇ / ALACAK / BAKİYE`, tutarlar metin (`8.200,00`) | Başlık satırı 3. satır olarak, sütunlar otomatik eşlendi (valör sütunu hariç); `DD.MM.YYYY`, ayrı borç/alacak; 3 işlem, borç ₺ 3.751,25, alacak ₺ 8.200,00, kapanış ₺ 4.448,75; içe aktarma tamam, uzlaştırma ekranında 3 işlem |
| PDF (Türkçe tablo: `Tarih, Açıklama, Borç, Alacak, Bakiye`) | Tablo algılandı, 3 işlem doğru okundu (`Müşteri tahsilatı - Beta A.Ş.`, `Güneş Ltd.` dahil Türkçe harfler); borç ₺ 1.730,75, alacak ₺ 6.400,00, kapanış ₺ 4.669,25 |

Bu turda bulunan: Frappe çekirdeğindeki `Page {0} of {1}` çevirisi `{1} {0} Sayfası` olduğundan PDF ekranında `1 1 Sayfası` görünüyordu; overlay'e `Sayfa {0} / {1}` eklendi (sonraki imaj derlemesiyle devreye girer). Ayrıca içe aktarma hemen sonrasında uzlaştırma sayacı bir an `3 / 3`, liste boş görünüyor; sayfa yenilenince `0 / 3` ve 3 işlem geliyor (önbellek yenileme gecikmesi, veri doğru).

### Eşleştirme kuralı ve geri alma metinleri

Ayarlar → Eşleştirme Kuralları sekmesi klavyeyle açıldı (başlık, açıklama, `Kural Ekle`, boş durum Türkçe). `Kural Ekle` formu ve geri alma pencereleri gömülü tarayıcıda açılmadı (Radix düğme tıklamaları iletilmiyor). Bunun yerine `Settings`, `Rules`, `ActionLog` ve `BankTransactionUnreconcileModal` bileşenlerindeki tüm `_()` metinleri çalışan sitenin çeviri tablosuyla karşılaştırıldı: 26 eksik görünen metnin 24'ü Türkçe (`Kaydet`, `Sil`, `Geri Al`, `Kaldır`, `Değer`, `Vade Tarihi`…), kalan ikisi metin değil (`0.00`, `{} :`).

### Açık kalanlar

- `Kural Ekle` formu ve işlem geri alma penceresi tarayıcıda çalıştırılamadı; yalnızca metin kapsamı doğrulandı, işlevi arka uç testleri kapsıyor.
- Türkçe başlık tanıma birim testlerle doğrulandı; gerçek bir Türk bankası ekstresiyle denenmedi.
- Bazı erişilebilirlik etiketleri (`Close toast`, `Select all rows`) üçüncü taraf bileşenlerden İngilizce gelir.
- Türkiye hesap planında `Bank` türünde yaprak hesap yok (bkz. yukarıdaki not).
- Baskı formatları (29 adet) ve e-posta şablonlarında alıcı dili için ayrı kapsam (Faz 4) geçerlidir.
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