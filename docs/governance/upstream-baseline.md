# Upstream tabanı ve CADRO değişiklik envanteri

Gözlem tarihi: 20 Kasım 2026.
Durum: Yerel commit ve GitHub API compare kanıtıyla doğrulanan başlangıç envanteri.

## Commit karşılaştırması

| Alan | Değer |
| --- | --- |
| CADRO uzak deposu | `https://github.com/emineturgay71-png/CADRO-ERP2.git` |
| ERPNext upstream | `https://github.com/frappe/erpnext.git` |
| Yerel dal | `tr-translation-complete` |
| Başlangıç commit | `920f1d5b3d18142cf3c4cc6edf59e53950a7832b` |
| Başlangıç dal | ERPNext `develop` |
| Karşılaştırılan upstream tabanı | `807222631c4f50a09e2d6351941562dbc1e90eb5` |
| Compare sonucu | Başlangıç commit upstream'den **0 ileride, 16 geride** |
| Farklı/CADRO-özgü commit kanıtı | Bu karşılaştırmada yok |

Upstream `develop` hareketli bir daldır. 16 geride olma değeri yalnızca yukarıdaki iki commit arasında, gözlem anında ölçülmüştür. Sürekli güncel sayı olarak kullanılmaz.

Yöntem: yerel `git log`, `git status`; GitHub commit ve `compare/{upstream_commit}...{local_commit}` API yanıtları. Yerel `refs/remotes/upstream/*` olmadığından bu kanıt kullanılmıştır; network yanlış SHA için değil commit varlığı ve compare durumu için kanıttır.

**Sonuç:** Bankacılık, CAD/BOM Creator, Türkçe PO ve diğer mevcut kodlar otomatik olarak CADRO'ya ait sayılmaz. Bu başlangıçta doğrulanabilir CADRO commit farkı ölçülmemiştir. Yeni Faz 0 belgeleriyle birlikte CADRO değişiklik envanteri başlar.

## Özellik ve modül sınırı

| Alan | Kaynak/konum | Ölçülen sahiplik | Bakım ve doğrulama sınırı |
| --- | --- | --- | --- |
| Temel ERP | `erpnext/` | Upstream ERPNext | Sürüm ve migration stratejisiyle uyum tutulur |
| Bankacılık/mutabakat | `banking/` ve accounts doctype'ları | Başlangıçta upstream | Kayıt/şirket/tenant yetkileri ve finans bütünleşmesi regresyonlu |
| Ekstre import | `erpnext/accounts/doctype/bank_statement_import_log/` | Başlangıçta upstream | Idempotency/job/durum ve parser testleri |
| CAD/BOM | `erpnext/manufacturing/doctype/bom_creator/`, `erpnext/public/js/bom_creator/` | Başlangıçta upstream | Dosya güvenliği, Item/BOM, parser ve performans testleri |
| Türkçe katalog | `erpnext/locale/tr.po`, POT/Crowdin | Başlangıçta upstream/Crowdin katkıları | ERPNext ve Frappe katalogları birlikte yaşam döngüsü |
| CADRO ürünleşme belgeleri | `docs/product/`, `docs/governance/` | Bu Faz 0 değişikliği | Ürün sahibi ve teknik yayın sorumlusu |
| CADRO üretim/SaaS kontrol düzlemi | Henüz yok | CADRO kapsamı | Faz 2 ve Faz 5'te oluşturulacak |
| Türkiye mali uyum/e-belge | Başlangıç dosyaları var, ürün yok | Henüz sahiplenilmedi | Faz 4; uzman ve sağlayıcı kabulü |

## Yeni fark kayıt biçimi

Bundan sonraki upstream'den sapma kayıtları aşağıdaki şema takip edilir. Bir satır, yalnız gerçek fark commit'iyle birlikte doldurulur.

| Commit/PR | Dosya/alan | Sınıf | Amaç | Sorumlu | Upstream katkısı | Kalite kanıtı |
| --- | --- | --- | --- | --- | --- | --- |
| Faz 0 PR sonrası atanacak | `docs/product/`, `docs/governance/` | CADRO belgesi | Ticari ürün/sürüm tabanı | CADRO | İstenmiyor | Manifest ve doküman kontrolleri |

Sınıflar:

- **Upstream alımı:** Hiçbir yerel değişiklik olmadan seçilen upstream commit.
- **Upstream değişikliği:** Upstream dosyasında CADRO için zorunlu değişiklik.
- **CADRO eklentisi:** Tekrarlanmayan yeni ürün/operasyon bileşeni.
- **Katkı bekleniyor:** CADRO işlevinin mümkünse upstream katkısı olarak gönderilmesi.

Her yeni kayıt, upstream ile birleştirme veya güncelleme sırasında yeniden değerlendirilir. Sahiplik bir dosya adından veya repo adından değil Git geçmişinden belirlenir.

## Upstream senkronizasyonu kuralı

1. Hedef ERPNext, Frappe ve payments revizyonları manifestoda açıkça seçilir.
2. Çalışma başlamadan mevcut çalışma ağacı ve test varsa önceki hatalar kaydedilir.
3. Farklı CADRO değişiklikleri tekil commit/PR'lerde tutulur; upstream pull/merge ile ürün geliştirmeleri karıştırılmaz.
4. Her güncelleme sonrasında fark envanteri ve manifest yenilenir; kaynak sahipliği yeniden ölçülür.
5. Frappe `develop` ve payments `develop` revizyonuna dinamik güncelleme yerine gözden geçirilmiş pin kullanılır.
6. Güvenlik yamaları önceliklidir; upstream değişikliğini geri almak CADRO değişikliklerini silme izni değildir.

## Karar bekleyen üretim hattı

`SECURITY.md` 20 Kasım 2026 itibarıyla 15.x/16.x'i desteklenen ERPNext hatları olarak listeler; mevcut kaynak ise 17.0.0-dev'tir.

Geriye taşıma için önceden seçilen kararlı ERPNext etiketi: `v16.23.0` (`b1ca423e119e14c8edb54138c3be4b493b71834e`). Bu, taşıma işleminin yapıldığı veya v16'nın CADRO ile uyumlu olduğu anlamına gelmez; Frappe eşleşmesi ve mevcut kodun geriye taşıma analizi ayrıca yapılacaktır.

Üretim hattı kararı için v16 referanslı karşılaştırma yapılır:

- Faydalanılan v17 bankacılık import/PDF/CAD/BOM yeteneklerinin v17 bağımlılıkları.
- Frappe ve payments sürüm eşleşmesi.
- DocType/migration geri uyumluluğu ve test matrisi.
- İlk müşteri katılımına kadar CADRO değişikliklerinin bakım maliyeti.

Bu analiz yapılmadan dal değiştirme, sürüm numarasını değiştirme veya taşıma yapılmaz.
