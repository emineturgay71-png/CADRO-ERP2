# CADRO ürün ve teknik taban kararı

Durum: Faz 0 — ürün sınırı tanımlandı; üretim ve ticari destek onaylanmadı.
Karar tarihi: 20 Kasım 2026.

## Ürün kararı

CADRO; yönetilen SaaS olarak ERP, bankacılık/mutabakat ve CAD/BOM yeteneklerini bir ürün ailesinde sunmayı hedefler. İlk dil Türkçe, tenant modeli ise müşteri başına ayrı Frappe sitesidir.

Bu belge yalnızca ürün sınırını tanımlar. Lisans uyumluluğu, marka kullanım izni, genel kullanıma hazır oluş, resmî mali uyum ve hizmet seviyesi iddiası oluşturmaz.

| Ürün alanı | Mevcut teknik taban | Faz 0 kapsamı | Sonraki zorunlu iş |
| --- | --- | --- | --- |
| ERP çekirdeği | ERPNext/Frappe modülleri | Sürümün ve modül sınırlarının korunması | Üretim sürümü, migration, roller ve operasyon |
| Bankacılık | `banking/` React SPA ve ERPNext muhasebe uçları | Ayrı ürün değil, CADRO modülü | Kayıt/tenant yetkileri, import bütünlüğü ve testler |
| CAD/BOM | `erpnext/manufacturing/doctype/bom_creator/` ve ilgili ön yüz | Manufacturing ailesinin ürün modülü | İzinler, dosya güvenliği ve gerçek CAD kabulü |
| Türkçe | Gettext PO/POT, `tr.po`, Türkçe hesap planı | Mevcut altyapının devam ettirilmesi | Kapsam ölçümü, tarih/TRY, baskı/e-posta ve E2E |
| Türkiye uyumu | Bölgesel başlangıç dosyaları | Ölçülmemiş, ayrı iş paketi | Mali müşavir matrisi ve resmî entegrasyon kabulü |
| SaaS | Frappe site modeli | Müşteri başına ayrı site kararı | Provisioning, entitlement, audit, yedekleme ve offboarding |

## Teknik kimlik ve kaynak sahipliği

`erpnext` teknik uygulama/paket kimliği korunur. CADRO, ürün adı olarak belgelenir; ERPNext, açık kaynak teknik taban ve upstream projedir. Paket adını veya `app_name` değerini değiştirmek bir marka veya lisans kararı değildir; Bench uyumluluğunu ve migration yüzeyini etkiler.

Bu karar tarihinde ölçülen CADRO-ERP2 çalışma tabanı ERPNext geçmişindedir. Bankacılık ve CAD/BOM kodunun varlığı tek başına CADRO'ya ait özgün çalışma kanıtı değildir. Sahiplik yalnızca doğrulanabilir commit ve sözleşme kayıtlarıyla tutulur.

Yeni veya değiştirilen her çalışma için şu kayıt tutulur:

- Kaynak commit ve upstream başlangıç revizyonu.
- CADRO değişikliğinin amacı, tarihi ve sorumlu ekibi.
- Upstream'den alınan, değiştirilen veya CADRO'ya özgü eklenen dosyalar.
- Upstream'e katkı durumu ve takip bağlantısı.
- Telif/lisans envanteri ve üçüncü taraf bildirimi gerekip gerekmediği.

## Ürün ve yayın ilkeleri

1. Tek doğruluk kaynağı Frappe/ERPNext uygulama modeli ve bu depodaki belgelerdir; aynı iş için paralel modeller kurulmaz.
2. Yeni CADRO işlevleri mevcut DocType, API, permission, task ve test kalıplarını korur.
3. Company seçimi tenant sınırı değildir. Kullanıcı–tenant eşlemesi ve her kaydın yetkisi ayrıca doğrulanır.
4. ERPNext adı veya logosu CADRO marka varlığı olarak kullanılmaz. Gerekli atıflar korunur; ürün, alan adı ve pazarlama kullanımı yasal incelemeye tabidir.
5. `license.txt`, `TRADEMARK_POLICY.md`, `attributions.md` ve mevcut kaynak bildirimleri Faz 0'da değiştirilmez.
6. CADRO güvenlik/destek adresleri ve sürüm desteği henüz ilan edilmedi. Üretime alma öncesinde ayrı karar gerekir.
7. Önce kimlik, modül bütünlüğü, kayıt/tenant/auth ve kalite kapıları; UX iyileştirmeleri bu kapıların yerine geçmez.

## Sürüm kararının durumu

Kaynak sürüm `17.0.0-dev`, upstream dal da `develop`'tır. `SECURITY.md` yalnızca ERPNext 15.x ve 16.x'i desteklenen sürümler olarak listeler. Bu nedenle mevcut kaynak üretim sürümü olarak ilan edilmemiştir.

Sabitlenen `develop` revizyonları reprodüksiyon tabanıdır; kararlılık onayı değildir. Üretim hattı için seçenekler:

- CADRO değişikliklerini ERPNext/Frappe v16 uyumlu hattına taşımak, veya
- v17 kararlı sürüm yayımlanana kadar Faz 1–3 düzeltmeleriyle devam etmek.

Seçenekler gerçek fark, migration ve geriye taşıma maliyetiyle karşılaştırılmadan karar verilmez.

## Faz dışı bırakılanlar

- ERP çekirdeğini yeniden yazmak veya `erpnext` paketini yeniden adlandırmak.
- Henüz atanmamış CADRO ürün sürüm numarası, SLA veya fiyat uydurmak.
- Var olan işlevlerin CADRO tarafından geliştirildiğini varsaymak.
- e-Fatura/e-Arşiv/e-İrsaliye/e-Defter uyumluluğu ilanı.
- Onaysız genel ticari lansman.

## İlgili kararlar

- [Upstream ve değişiklik envanteri](../governance/upstream-baseline.md)
- [Sürüm ve bağımlılık manifestosu](../governance/version-and-dependencies.md)
- [Yasal, marka ve sahiplik kontrolleri](../governance/legal-decisions.md)
- [Faz 0 tamamlanma kapısı](../governance/phase-0-gate.md)
