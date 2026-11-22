# Faz 6 — Kontrollü gelir ve lansman tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Planlama ve lansman kontrol listesi tamamlandı. Canlı pilot başlamadı.**

Bu faz ağırlıklı olarak iş/gelir kararlarıdır; kod değişikliği içermez.

## Lansman öncesi yapılması gerekenler

### Hukuk ve uyum

| Madde | Sorumlu | Durum |
| --- | --- | --- |
| GPL-3.0 SaaS/dağıtım hukuki değerlendirmesi | Avukat | ⏳ Bekliyor |
| ERPNext/Frappe marka kullanım izni | Frappe + Avukat | ⏳ Bekliyor |
| CADRO marka tescili | Marka vekili | ⏳ Bekliyor |
| KVKK/GDPR veri işleme envanteri | Avukat | ⏳ Bekliyor |
| Hizmet sözleşmesi ve Gizlilik Politikası | Avukat | ⏳ Bekliyor |
| DPA (Veri İşleme Sözleşmesi) | Avukat | ⏳ Bekliyor |
| Alt işleyen listesi | Operasyon | ⏳ Bekliyor |

### Mali uyum

| Madde | Sorumlu | Durum |
| --- | --- | --- |
| Hesap planı ve KDV oranlarının mali müşavir onayı | SMMM | ⏳ Bekliyor |
| e-Fatura/e-Arşiv zorunlu senaryo matrisi | SMMM | ⏳ Bekliyor |
| e-Defter saklama ve imza gereksinimleri | SMMM | ⏳ Bekliyor |
| GİB entegratörü / özel entegratör seçimi | Teknik + SMMM | ⏳ Bekliyor |

### Teknik operasyon

| Madde | Sorumlu | Durum |
| --- | --- | --- |
| MariaDB + PostgreSQL test koşusu | Teknik | ⏳ Bekliyor |
| Docker imaj build ve güvenlik taraması | Teknik | ⏳ Bekliyor |
| Yedekten geri yükleme tatbikatı | Operasyon | ⏳ Bekliyor |
| Yük ve kapasite testi | Teknik | ⏳ Bekliyor |
| Kontrol düzlemi kurulumu (tenant DB + API) | Teknik | ⏳ Bekliyor |
| Ödeme sağlayıcı entegrasyonu | Teknik | ⏳ Bekliyor |
| İzleme/alarım (Sentry/Grafana) | Operasyon | ⏳ Bekliyor |
| Rate limiting ve DDoS koruması | Operasyon | ⏳ Bekliyor |

### İş ve müşteri

| Madde | Sorumlu | Durum |
| --- | --- | --- |
| Pilot müşteri seçimi (1-3 işletme) | Satış | ⏳ Bekliyor |
| Fiyatlandırma ve paket yapısı | Ürün | ⏳ Bekliyor |
| Türkçe onboarding dokümantasyonu | Teknik yazar | ⏳ Bekliyor |
| Türkçe kullanıcı eğitim materyali | Eğitim | ⏳ Bekliyor |
| Destek kanalı ve SLA tanımı | Operasyon | ⏳ Bekliyor |
| Pilot sözleşme ve kabul kriterleri | Avukat + Satış | ⏳ Bekliyor |

### Lansman kontrol listesi

| Madde | Durum |
| --- | --- |
| Pilot müşteri canlıya alındı | ⏳ |
| 30 gün sorunsuz operasyon | ⏳ |
| Müşteri kabul imzası | ⏳ |
| Geri bildirim döngüsü kuruldu | ⏳ |
| Paket/fiyat kararı verildi | ⏳ |
| Genel lansman tarihi belirlendi | ⏳ |

## Önerilen zaman çizelgesi

| Dönem | Hedef |
| --- | --- |
| 1-2 hafta | Hukukçu ve SMMM görüşmeleri |
| 2-4 hafta | Docker build + Bench testleri + yedekleme tatbikatı |
| 4-6 hafta | Kontrol düzlemi MVP + ödeme entegrasyonu |
| 6-8 hafta | Pilot müşteri onboarding |
| 8-12 hafta | Pilot değerlendirme ve fiyatlandırma |
| 12+ hafta | Genel lansman kararı |

## Değişen dosyalar

```
docs/governance/phase-6-gate.md - bu dosya
```

## Doğrulama

Faz 6 kod değişikliği içermediği için otomatik doğrulama uygulanmaz. Her madde kendi sorumlusu tarafından kapatılır.