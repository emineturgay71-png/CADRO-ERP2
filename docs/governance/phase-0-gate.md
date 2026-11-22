# Faz 0 — Ürün, lisans ve sürüm tabanı tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Kaynak girdileri doğrulandı; üretim ve ticari destek onaylanmadı.**

## Otomatik doğrulama sonuçları

| Kapı | Araç | Sonuç |
| --- | --- | --- |
| Manifesto şema bütünlüğü | `scripts/validate_cadro_baseline.py` | ✅ Geçerli |
| Yarn v1 doğrudan seçiciler | Aynı (üç lockfile) | ✅ Tüm bağımlılık blokları kilitli |
| Python/Frappe beyanları | Aynı (`pyproject.toml`) | ✅ v17-dev, Python ≥3.14, beklenen bağımlılıklar |
| Yerel Git soy kanıtı | `git merge-base --is-ancestor` | ✅ HEAD, `920f1d5b` içeriyor |
| Upstream fork kanıtı | `scripts/check_upstream_baseline.py` | ✅ Fork = upstream, 0 CADRO commit, 16 geride |
| Olumsuz testler | `scripts/test_validate_cadro_baseline.py` | ✅ 8/8 |
| `license.txt` ve kaynak bildirimleri | Değiştirilmedi | ✅ Orijinal korunuyor |

## Kaynak düzeyinde tamamlananlar

- [x] CADRO ürün adı belgelendi; ERPNext teknik uygulama kimliği korundu.
- [x] ERPNext, Frappe ve payments için değerlendirme commit pin'leri seçildi.
- [x] `cadro.baseline.json` makine okunur pin manifestosu oluşturuldu.
- [x] Üç Yarn lockfile'ında her doğrudan seçicinin registry bloğu ve integrity kaydı doğrulandı.
- [x] Python ve Frappe temel bağımlılıkları belgelendi ve denetlendi.
- [x] Upstream ile CADRO farkı: fork'ta sıfır CADRO commit, ölçülen ortak ata doğrulandı.
- [x] GPL-3.0 metni, marka politikası ve mevcut bildirimler dokunulmadan korundu.
- [x] Üretim onayı hiçbir belgede verilmedi; her araçta `production_approved: false`.

## Dış onay veya kurulum bekleyenler (bu Faz'da kapatılmaz)

Bu maddelerin tamamlanması Faz 0'ı kapatmak için zorunlu değildir; her biri sonraki fazlarda ele alınır.

| Madde | Sahibi | Hedef faz |
| --- | --- | --- |
| Hukukçu onaylı GPL SaaS/dağıtım değerlendirmesi | Hukuk | Faz 2 öncesi |
| CADRO marka/alan adı incelemesi | Ürün + Hukuk | Faz 0 sonrası |
| Frappe/payments/UI lisans uyumluluğu | Hukuk + Teknik | Faz 2 öncesi |
| SBOM, üçüncü taraf lisans envanteri | Teknik | Faz 2 |
| CI kurulumunun manifest pinlerine geçirilmesi | Teknik | Faz 1 |
| Üretim imajı ve dağıtım manifestosu | Operasyon | Faz 2 |
| v16/v17 kararlı sürüm hattı kararı | Teknik + Ürün | Faz 1 öncesi |
| Bench entegrasyon testleri (MariaDB/PostgreSQL) | Teknik | Faz 1 |
| CADRO güvenlik/destek iletişimi | Güvenlik | Faz 2 öncesi |
| KVKK/GDPR veri envanteri ve sözleşmeler | Hukuk | Faz 2 |

## Mevcut durum ve sınırlar

- Şu an üretim onayı verilmiş **yoktur**. Manifestoda ve tüm belgelerde `evaluation-only` olarak işaretlenmiştir.
- Faz 0 yalnızca **kaynak girdilerinin tekrarlanabilirliğini ve doğrulanabilirliğini** sağlar.
- Hiçbir build, test veya deployment çalıştırılmamıştır.
- Mevcut ERPNext işlev kodu, telif bildirimleri ve upstream CI otomasyonu değiştirilmemiştir.

## Sonraki adım

Faz 1 — Tenant/auth ve finansal bütünlük yayın blokerleri.  
Öncelik: Kayıt bazlı yetki kontrolleri, import idempotency, storage kapsamı ve XSS doğrulaması.