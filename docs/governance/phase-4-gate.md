# Faz 4 — Türkiye muhasebesi ve e-belge/e-defter uyum ürünü tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Teknik yapı kuruldu. Resmi uyum iddiası yoktur. Mali müşavir onayı ve sağlayıcı seçimi gereklidir.**

## Bölgesel yapılandırma

| Dosya | İçerik |
| --- | --- |
| `erpnext/regional/turkey/setup.py` | Şirket kurulumunda çağrılan `setup()`; custom field hook'u |
| `erpnext/setup/setup_wizard/data/country_wise_tax.json` | `Türkiye` girdisi: satış/alış KDV şablonları (%20 varsayılan, %10, %1), `Turkey - Chart of Accounts` hesaplarına (391.01.x / 191.01.x) bağlı |
| `erpnext/regional/__init__.py` | `get_country_package()`: Frappe ülke adı `Türkiye` → `erpnext.regional.turkey` eşlemesi |
| `erpnext/regional/turkey/__init__.py` | Paket işaretçisi (boş) |

KDV şablonları Hesaplanan KDV (satış) ve İndirilecek KDV (alış) için şirket oluşturulurken `setup_taxes_and_charges` ile oluşturulur. Mevcut template varsa atlanır. Hesap planı `tr_chart_of_accounts.json` zaten mevcuttur.

**Uyarı:** Yalnızca temel %20, %10, %1 KDV oranları şablon olarak eklenir. Mevcut bir oranın güncel mevzuata uygunluğu mali müşavir tarafından doğrulanmalıdır. Tevkifat, stopaj ve özel matrah gibi ileri senaryolar bu faz kapsamında değildir.

## E-belge adaptör mimarisi

| Dosya | Açıklama |
| --- | --- |
| `erpnext/regional/turkey/e_document_contract.py` | Sağlayıcıdan bağımsız ABC sözleşmesi: `EInvoice`, `EDespatch`, `ELedger` |
| `erpnext/regional/turkey/e_document_queue.py` | Durum makinesi, loglama ve idempotency yardımcısı |

### Durum modeli

```
draft → queued → processing → accepted → cancelled
                         ↘ rejected → queued (retry)
                         ↘ failed   → queued (retry)
```

### Ara yüz

Her sağlayıcı implementasyonu şu metodları sunar:
- `send(doc) → correlation_id` — belge gönderimi
- `cancel(correlation_id) → correlation_id` — iptal
- `status(correlation_id) → DocumentStatus` — durum sorgulama
- `download_pdf(correlation_id) → bytes` — imzalı PDF
- `download_ubl(correlation_id) → bytes` — UBL-TR XML

### Log DocType

`CADRO EDocument Log` (`erpnext/regional/doctype/cadro_edocument_log/`) — gerçek, sürüm kontrollü DocType. Önceden çalışma anında `custom` DocType olarak oluşturuluyordu ve System Manager silebiliyordu; artık:

- Formdan kimseye yazma/oluşturma/silme yetkisi yok (System Manager ve Accounts Manager yalnızca okur/dışa aktarır); kayıtları `e_document_queue` kodu yazar.
- Denetleyici durum makinesini zorlar (`VALID_TRANSITIONS` / `can_transition`, `e_document_contract.py`); yeni kayıt yalnızca `draft` başlar; geçersiz geçiş "Geçersiz Durum Geçişi" hatası verir.
- Kayıt silinemez (`on_trash` engeller). Belge türü, yön ve ERP referansı oluşturulduktan sonra değişmez (`set_only_once`). Değişiklikler sürüm geçmişinde izlenir.
- Mevcut bir sitede eski çalışma anı sürümü varsa `patches.txt` (pre_model_sync) `custom` bayrağını kaldırır, tablo ve veriler korunur.

Kayıt alanları:
- Belge türü (e-fatura, e-arsiv, e-irsaliye, e-defter)
- Yön (outbound/inbound)
- Durum (draft→…→cancelled)
- Sağlayıcı correlation ID
- ERP referansı (Doctype + isim)
- Sağlayıcı yanıtı (JSON) ve hata metni
- Zaman damgaları (oluşturma, son sorgulama)

## Sağlayıcı seçimi öncesi yapılması gerekenler

1. Hedef müşteri segmentinin zorunlu belge/senaryo listesini çıkarın.
2. GİB entegratörü veya özel entegratör alternatiflerini değerlendirin.
3. Sandbox test hesabı açın.
4. Gerçek anonim belge örnekleriyle imza, UUID, senaryo ve iptal/ret akışlarını doğrulayın.
5. Mali müşavir ile KDV oranları, tevkifat ve özel matrah kapsamını netleştirin.
6. Onaylanan sağlayıcı için `e_document_contract.py` ABC'sini implement edin.

## Değişen dosyalar

```
erpnext/regional/turkey/setup.py                  - KDV şablonları + custom field hook'u
erpnext/regional/turkey/e_document_contract.py    - yeni: ABC sözleşmesi + VALID_TRANSITIONS
erpnext/regional/turkey/e_document_queue.py       - yeni: durum makinesi + log (artık gerçek DocType kullanır)
erpnext/regional/doctype/cadro_edocument_log/     - yeni: gerçek DocType (JSON + denetleyici)
erpnext/regional/turkey/test_turkey_regional.py   - ülke paketi + e-belge günlüğü testleri
erpnext/patches.txt                                - eski çalışma anı DocType'ının custom bayrağını kaldırır
docs/governance/phase-4-gate.md                    - bu dosya
```

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ compileall temiz |
| Faz 0 manifesto | ✅ geçerli |
| Faz 0 testleri | ✅ 8/8 |
| Hesap planı | ✅ `tr_chart_of_accounts.json` mevcut |
| KDV şablonları | ✅ şirket oluşturulurken `country_wise_tax.json` (`Türkiye`) ile oluşuyor; pilot sitede doğrulandı |
| E-belge contract | ✅ soyut, sağlayıcı-bağımsız |
| E-belge queue | ✅ durum makinesi + idempotency |
| E-belge günlüğü DocType | ✅ gerçek DocType, silinemez, yazma yetkisi yok; `test_turkey_regional.py` 12/12 (MariaDB, taze site: ülke paketi 2 + günlük 10 test) |
| Mali müşavir onayı | ❌ Gerekli, bu faz kapsamında değil |
| Sağlayıcı seçimi | ❌ Gerekli, bu faz kapsamında değil |

## Uçtan uca ana akış testi (24 Kasım 2026)

`erpnext/regional/turkey/test_main_flow.py` Türkiye şirketi üzerinde alım → depolama → satış → tahsilat → banka mutabakatı zincirini çalıştırır. Her adım kendi belge/stok/GL beklentisini hemen doğrular; alt senaryolar önkoşullarını kendileri çalıştırır, `test_main_flow` bütün zinciri koşup defterleri denetler.

```bash
bench --site <site> run-tests --module erpnext.regional.turkey.test_main_flow
```

| Alt senaryo | Beklenen (örnek: 100 adet × 50 TL alım, 40 adet × 80 TL satış, %20 KDV) |
| --- | --- |
| 1 Alım | İrsaliye: `153` 5.000 B / faturasız mallar 5.000 A; fatura: KDV `191` 1.000 B, `320` 6.000 A; stok +100 |
| 2 Tedarikçiye ödeme | `320` B / `102` A; fatura kapanır (kısmi ödeme varyasyonu ayrı) |
| 3 Depolama | Depolar arası transfer: Bin'ler doğru, stok hesabı bakiyesi değişmez |
| 4 Satış | İrsaliye: maliyet 2.000 B / `153` A; fatura: `120` 3.840 B, satış 3.200 A, `391` 640 A |
| 5 Tahsilat | Nakit 1.000 (`100`), çek 1.500 (`101`, vadeli), havale 1.340 (`102`); fatura "Paid" |
| 6 Çek yatırma | `102` B / `101` A; çek hesabı sıfırlanır |
| 7 Banka mutabakatı | 4 ekstre hareketi belgelerle eşlenir, hepsi "Reconciled"; ekstre toplamı = defter bakiyesi |
| Ana akış | Mizan dengeli, stok değeri = `153`, alıcılar/satıcılar = açık faturalar, tüm hesap bakiyeleri beklenen, kâr = 3.200 − 2.000 |
| Varyasyonlar | Kısmi ödeme, stok sayım farkı (`940`), yetersiz stokla satışın reddi, satış iadesi (stok + maliyet + KDV), karşılıksız çek, satışın iptali |

Sonuç: taze MariaDB sitesinde 15/15 geçti (iki ardışık koşu).

### Tamamlayıcı akışlar (`test_main_flow_extended.py`, 12 test)

Aynı şirket ve adım yardımcılarıyla ana akışın dışında kalan uçlar:

| Senaryo | Doğrulanan |
| --- | --- |
| Raporlar defterle tutarlı | Mizan (genel toplam dengeli, hesap bakiyeleri beklenen), Kâr-Zarar (gelir kökü 3.200, gider kökü 2.000 → net kâr 1.200), Bilanço (varlık = yükümlülük + özkaynak + dönem kârı), Stok Bakiyesi (miktar ve değer = Bin) |
| Alıcı/Satıcı özeti | Açık satış faturası 3.840, açık alış faturası 6.000 |
| Hareketli ortalama | 100 × 50 + 50 × 80 → ortalama 60; 40 adet satış maliyeti 2.400 |
| FIFO | Aynı alımlarla 40 adet en eski katmandan: maliyet 2.000 |
| Alış iadesi | İrsaliye ve fatura iadesi: stok, indirilecek KDV ve borç geri alınır |
| Müşteri avansı | Avans `120`'de müşteri lehine bakiye; faturaya Ödeme Mutabakatı ile mahsup; kalan havale |
| KDV oranları ve iskonto | %10 → `391.01.05`, %1 → `391.01.03`, %20 + iskonto → matrah 900, KDV 180 |
| Kısmi teslimat | Bir sipariş, 25 + 15 adet iki irsaliye ve iki fatura; sipariş %62,5 sonra %100 teslim/fatura |
| Dönem kapanışı | Stok kapanışı + Dönem Kapanış Fişi: gelir/gider hesapları sıfırlanır, 1.200 kâr `590.01`'e geçer |
| Dövizli satış | 120 EUR hizmet satışı kur 30, tahsilat kur 32: kambiyo kârı 240 (`646.01`); kur 28: kambiyo zararı 240 (`656.01`); EUR banka bakiyesi doğru |
| Türkçe ekstre | CSV (`Tarih, Açıklama, Referans, Borç, Alacak`, `20.000,00` biçimli sayılar) içe aktarılır, 4 hareket otomatik uzlaştırılır; defter bakiyesi = ekstre toplamı |

Sonuç: `test_turkey_regional` 16 + `test_main_flow` 15 + `test_main_flow_extended` 12 = **43/43, hem MariaDB hem PostgreSQL 17** (taze sitelerde).

Bu turda bulunan ve düzeltilenler:

- Şablon hesap planlarında `account_currency` yok sayılıyordu (her hesap şirket para birimine zorlanıyordu); `EUR KASA`/`USD KASA` aslında TRY hesaptı. Yükleyici artık şablondaki `account_currency` değerini uyguluyor; kasalar EUR/USD cinsinden, `102.02`/`102.03` banka, `120.02`/`120.03` alıcı ve `320.02`/`320.03` satıcı döviz hesapları eklendi.
- Kambiyo (`646.01`, `656.01`, değerleme `646.02`), banka masrafı (`653.01`), yazılan fark (`659.01`) hesapları ve şirket varsayılanları eklendi; Dönem Kapanışı için `570.01`/`580.01`/`590.01` özkaynak yaprakları eklendi.
- Varsayılan banka, alıcı ve satıcı hesapları `set_company_defaults` ile açıkça `102.01`/`120.01`/`320.01` yapılıyor (döviz hesapları artık aynı türde birden çok yaprak oluşturuyor).
- Dönem kapanışı artık Stok Kapanış Kaydı gerektiriyor ve yıl bitmeden yapılamıyor (testte saat yıl sonrasına alınır).

### Ana akış testinin bulduğu eksikler (çözüldü)

İlk koşuda taze Türkiye şirketi ticarete hazır gelmiyordu: 6. sınıf tek `Income` kökündeydi (`621` Satılan Ticari Mallar Maliyeti varsayılan maliyet hesabı olamıyordu), `101`/`102`/`153`/`600`/`500` altında yaprak hesap yoktu, `320.01` `Payable` değildi, `Stock Received But Not Billed` hesabı ve şirket varsayılanları yoktu, çek/havale ödeme yöntemlerinde şirket hesabı yoktu. Pilotta `Allow Negative Stock` kapalı; yetersiz stokla satış reddediliyor.

### Hesap planı düzeltmesi (24 Kasım 2026)

Ana akış testi taze bir Türkiye şirketinin ticarete hazır gelmediğini gösterdi; hesap planı ve ülke kurulumu şöyle düzeltildi (`tr_chart_of_accounts.json`, `regional/turkey/setup.py`, `hooks.py`):

| Sorun | Düzeltme |
| --- | --- |
| 6. sınıf tek `Income` kökünde (`621`, `632` gider olduğu hâlde gelir) | Kök ikiye bölündü: `6` GELİR TABLOSU HESAPLARI (GELİRLER) = `Income` (60, 61, 64, 67, 69); `6G` GELİR TABLOSU HESAPLARI (GİDERLER) = `Expense` (62, 63, 65, 66, 68). Alt hesap numaraları aynı kaldı |
| Yaprak hesap yoktu | `101.01` Alınan Çekler TL (`Cash`), `102.01` TL Banka (`Bank`), `153.01` Ticari Mallar TL (`Stock`), `320.90` Faturası Gelmemiş Mal Alımları (`Stock Received But Not Billed`), `500.01` Sermaye TL, `600.01` Yurt İçi Satışlar TL (`Income Account`), `621.01` Satılan Ticari Mallar Maliyeti TL (`Cost of Goods Sold`), `689.01` Yuvarlama Farkları (`Round Off`) |
| `320.01` türü yoktu | `Payable` |
| Varsayılan kasa USD KASA, varsayılan stok `157.01` seçiliyordu (aynı türde birden çok yaprak) | Company `on_update` kancası `set_company_defaults`: yeni Türkiye şirketinde varsayılan kasa `100.01` TL KASA, stok `153.01` |
| Çek, havale, nakit ödeme yöntemlerinde şirket hesabı yoktu | `setup()` şirket oluşurken `Cash`→`100.01`, `Cheque`→`101.01`, `Wire Transfer` ve `Bank Draft`→`102.01` bağlar |

Doğrulama:

- Ana akış testi artık hesap kurmadan, yalnızca yeni hesap planıyla 15/15 geçiyor; `test_company_is_ready_to_trade` varsayılanları, kök türlerini ve ödeme yöntemi hesaplarını denetler.
- `TestTurkeyChartOfAccounts` (dosya düzeyinde, 4 test): kök türleri, hesap numarası tekilliği, ticaret yaprakları ve türleri, ERPNext'in kendisinin seçtiği türlerin tek yaprakla temsil edilmesi.
- `test_turkey_regional` 16/16, `test_company` 25/25 (MariaDB, taze site).

Sınırlar:

- Düzeltme yalnızca yeni kurulan şirketleri etkiler. Eski plana göre kurulmuş şirketlerin hesapları aynen kalır (mevcut hesapların kökünü değiştirmek raporları etkiler); pilot için yeni planla ikinci bir şirket kuruldu (aşağıya bakın).
- Dövizli işlemler için kambiyo, banka masrafı ve yazılan fark hesapları ve varsayılanları sonraki turda eklendi (aşağıya bakın).

### Pilot şirketi (24 Kasım 2026)

Pilot sitede (`cadro-pilot.localhost`) yeni planla ikinci bir şirket kuruldu: **CADRO Teknoloji A.Ş.** (`CTA`), varsayılan şirket olarak ayarlandı. Tüm varsayılanlar (alıcı, satıcı, gelir, maliyet, stok, faturasız mallar, yuvarlama, banka, kasa, kambiyo, banka masrafı, yazılan fark) ve çek/havale/nakit ödeme yöntemleri doğrulandı; `621`/`632` gider kökünde, `102.02` EUR cinsinden. Banka hesabı `Vadesiz TL (CTA)` bağlandı. Eski şirket (**CADRO Teknoloji**, `CADRO`) eski plan ve demo verisiyle duruyor; silinmedi. Yeni plana geçmeden önceki yedek: `D:\dev\cadro-backups\20261124-pre-new-chart`.

## Sonraki adım

Faz 5 — SaaS ticarileştirme ve ölçek.  
Öncelik: Tenant provisioning, plan/kota modeli, ödeme webhook'ları, suspend/reactivate.