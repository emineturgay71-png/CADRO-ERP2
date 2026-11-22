# Faz 0 yasal, marka ve sahiplik kontrolleri

Durum: Teknik kontrol listesi. **Hukuki görüş veya dış onay değildir.**
Tarih: 20 Kasım 2026.

## Alınan teknik kararlar

CADRO ürünleşmesi mevcut GPL-3.0 tabanını koruyacaktır. Ticari kullanım veya ücretli hizmet planlaması, kaynak ve marka haklarını sınırlandırma kararı anlamına gelmez.

- Kök `license.txt` ve mevcut Frappe/ERPNext telif bildirimleri korunur.
- `TRADEMARK_POLICY.md` ve `attributions.md` korunur; atıflar kaldırılmaz.
- Kaynak dosyalarındaki telif satırları, yalnızca lisans görünümünü değiştirmek amacıyla topluca düzenlenmez.
- Yeni CADRO belge ve kod değişiklikleri tarih, kaynak commit ve sorumlu ekiple izlenebilir olur.
- CADRO markası ile ERPNext teknik tabanı ayrıştırılır; ERPNext resmî sponsorluğu veya ortaklığı ima edilmez.
- Yönetilen SaaS ile müşteriye kurulum/imaj dağıtımı için ayrı dağıtım kontrol listesi uygulanır.

## SaaS veya dağıtım öncesi kontrol listesi

| Kontrol | Yönetilen SaaS | Kaynak/binary/container dağıtımı | Kanıt |
| --- | --- | --- | --- |
| Uygulanabilir GPL-3.0 yükümlülükleri | İlgili kapsam | İlgili kapsam | Hukukçu imzalı değerlendirme |
| Telif, lisans ve garanti reddi bildirimleri | Korumak | Korumak ve alıcıya ulaştırmak | Dağıtım artefaktı/dokümanı |
| Değiştirilmiş çalışma bildirimleri | Değişiklik envanteri | Belirgin değişiklik ve tarih bildirimi | Release ve kaynak kaydı |
| Corresponding Source değerlendirmesi | KOPYA aktarımı varsa değerlendir | Zorunlu kapsam hukukçuyla belirlenir | Erişim veya teklif mekanizması |
| ERPNext/Frappe marka kullanımı | Pazarlama ve ürün adı denetimi | Ambalaj ve ürün adı denetimi | İzin veya açıklayıcı kullanım kararı |
| Frappe, payments, Frappe UI lisansları | Sevkiyat öncesi | Sevkiyat öncesi | Bileşen lisans matrisi |
| Transitive sistem ve uygulama paketleri | Runtime envanteri | İmaj/paket envanteri | SBOM ve bildirim paketi |
| KVKK/GDPR ve veri işleme sözleşmeleri | Üretim/pilot öncesi | Hizmet kapsamına göre | DPA, saklama, silme ve dış hizmet listesi |
| CADRO destek ve güvenlik sorumlusu | Yayın öncesi | Sevkiyat öncesi | Onaylı iletişim ve olay süreci |

Bu tablo otomatik “uyumlu” sonucu üretmez. Özellikle ayrı CADRO bileşenlerinin birleşik/türev çalışma sınırı ve ağ üzerinden kullanımın kaynak yükümlülüğü, gerçek mimari ve dağıtım yöntemiyle hukukçu tarafından incelenir.

## Bileşen sahipliği ve SBOM alanı

En az şu alanları kapsayan SBOM ve bildirim envanteri hazırlanmadan dağıtım yapılmaz:

- Python uygulama bağımlılıkları ve imajdaki sistem paketleri.
- Frappe Framework, ERPNext ve payments uygulamaları.
- Root, Banking ve Islands NPM/Yarn bağımlılıkları ile lockfile çözümleri.
- `@framework/ui` için kullanılan Frappe içindeki yerel UI kaynağı.
- Üretim imajı ve base OS digestleri, PDF/CAD/rendering araçları, fontlar ve görseller.
- Harici e-belge, ödeme, banka, barındırma ve gözlem hizmetleri; bunların API koşulları ve veri işleme koşulları SBOM'dan ayrı izlenir.

Mevcut `attributions.md`, bu geniş kapsamın tamamını karşıladığı anlamına gelmez. Orijinal bağlantılar korunarak eksik envanter ayrı üretilmelidir.

## Sözleşme ve katkı kaydı

Faz 0 sonrasında her yeni CADRO değişikliği için kaynak sahipliği dosyası bulunur:

- Çalışan ve yüklenicilerin fikrî mülkiyet/işveren/iş sözleşmeleri.
- Dış katkıların kaynağı ve uygulanabilir DCO/CLA kararı.
- Yapay zekâ/üçüncü taraf kaynaklı varlıkların lisans ve kaynak kanıtı.
- Marka başvurusu, alan adı ve hedef pazar incelemesi.
- Gizlilik politikası, hizmet şartları, veri saklama/silme ve alt işleyen politikası.

Bu belgelerin repo içinde bulunmaması, dışarıda bulunmadıklarını kanıtlamaz; Faz 0'daki durum “doğrulanmadı”dır.

## Açık karar sahipleri

- [ ] CADRO marka/ad/alan adı incelemesi: hukuk ve ürün sahibi.
- [ ] GPL SaaS/dağıtım şartları: açık kaynak hukuku uzmanı.
- [ ] Frappe Framework, payments ve Frappe UI lisansları: hukuk + teknik yayın sorumlusu.
- [ ] KVKK/GDPR, veri bölgesi, DPA ve saklama: hukuk + güvenlik + operasyon.
- [ ] CADRO güvenlik iletişimi ve desteklenen sürüm politikası: ürün + güvenlik.
- [ ] Türkiye mali mevzuatı ve e-belge/e-defter kapsamı: mali müşavir + hukuk; Faz 4 kapsamı.

## Kaynak kanıtları

- `license.txt`: depodaki GNU GPL sürüm 3 metni.
- `TRADEMARK_POLICY.md`: ERPNext adı ve logosunun kullanım ilkeleri.
- `attributions.md`: mevcut ERPNext/Frappe atıf bağlantıları.
- `SECURITY.md`: mevcut upstream destek ve güvenlik bildirim bilgileri; CADRO politikası değildir.
- `erpnext/hooks.py`: teknik uygulama ve lisans bildirimi.
