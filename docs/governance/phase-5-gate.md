# Faz 5 — SaaS ticarileştirme ve ölçek tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **SaaS modeli tanımlandı; altyapı araçları oluşturuldu. Kontrol düzlemi ayrı bir servis olarak kurulacak.**

## SaaS modeli

| Katman | Sorumluluk | Konum |
| --- | --- | --- |
| ERPNext uygulaması | İş mantığı, muhasebe, bankacılık, CAD/BOM | Bu repo |
| CADRO kontrol düzlemi | Tenant kaydı, ödeme, abonelik durumu, provisioning | Ayrı servis (bu fazda tanımlandı, kurulmadı) |
| Frappe Bench | Site başına veritabanı, dosya, Redis | Compose ile yönetiliyor |

## Oluşturulan modüller

| Dosya | Açıklama |
| --- | --- |
| `cadro/saas/tenant.py` | `TenantRecord`, `TenantStatus`, `TenantQuota`, `PlanTier`; `enforce_tenant_active()` |
| `cadro/saas/subscription.py` | `SubscriptionState`, `require_active_subscription` dekoratörü, grace period mantığı |
| `cadro/saas/provision_site.py` | `bench new-site` + `cadro.baseline.json` pin'leriyle otomatik provisioning |
| `cadro/saas/manage_tenant.py` | `suspend`, `reactivate`, `offboard` — tenant yaşam döngüsü |
| `cadro/saas/webhook.py` | `WebhookPayload`, `WebhookEvent` — sağlayıcı-bağımsız ödeme kontratı |

## Tenant yaşam döngüsü

```
trial ──► active ──► suspended ──► active   (ödeme yapıldı)
  │                    │
  │                    └──► cancelled         (offboard)
  │
  └──► suspended       (trial bitti, ödeme yok)
```

## Plan ve kota modeli

| Plan | Kullanıcı | Şirket | Depolama | API/dak |
| --- | --- | --- | --- | --- |
| Starter | 5 | 1 | 2 GB | 100 |
| Professional | 20 | 3 | 20 GB | 600 |
| Enterprise | 100 | 10 | 100 GB | 2000 |

## Ödeme akışı

```
Ödeme sağlayıcı → webhook → normalizer → WebhookPayload → kontrol düzlemi
                                                               │
                                          ┌────────────────────┘
                                          ▼
                              subscription durumu güncelle
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                         active                  suspended
                    (site açık)              (maintenance mode)
```

## Kullanım

### Provisioning
```bash
python cadro/saas/provision_site.py \
    --site cadro-tenant-001.localhost \
    --admin-password <pw> \
    --db-password <root-pw> \
    --plan professional
```

### Tenant yönetimi
```bash
python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action suspend
python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action reactivate
python cadro/saas/manage_tenant.py --site cadro-tenant-001.localhost --action offboard --confirm YES
```

### API koruması
```python
@frappe.whitelist()
@require_active_subscription
def my_endpoint():
    # Sadece aktif veya trial süresindeki tenant'lar erişebilir
    ...
```

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ compileall temiz |
| Faz 0 manifesto | ✅ geçerli |
| Faz 0 testleri | ✅ 8/8 |
| Tenant modeli | ✅ dataclass + enum |
| Plan/kota | ✅ 3 plan, default kotalar |
| Provisioning | ✅ bench tabanlı, pin'li |
| Suspend/reactivate | ✅ maintenance_mode |
| Offboarding | ✅ drop-site, onaylı |
| Ödeme webhook | ✅ kontrat tanımlı, uygulama stub |

## Kontrol düzlemi için sonraki adımlar (bu fazda kapatılmaz)

1. Ayrı bir kontrol düzlemi servisi kur (FastAPI/Flask)
2. Tenant veritabanı (PostgreSQL) oluştur
3. Ödeme sağlayıcı adaptörü ekle (Stripe/Iyzico/PayTR)
4. Webhook idempotency + imza doğrulama
5. Gerçek `tenant_from_site()` implementasyonu
6. KVKK/GDPR veri işleme sözleşmeleri
7. Self-service kayıt ve trial başlatma
8. Müşteri veri export ve hesap kapatma akışı

## Değişen dosyalar

```
cadro/saas/tenant.py           - yeni: tenant modeli
cadro/saas/subscription.py     - yeni: abonelik ve entitlement
cadro/saas/provision_site.py   - yeni: otomatik provisioning
cadro/saas/manage_tenant.py    - yeni: tenant yaşam döngüsü
cadro/saas/webhook.py          - yeni: ödeme webhook kontratı
docs/governance/phase-5-gate.md - bu dosya
```

## Sonraki adım

Faz 6 — Kontrollü gelir ve lansman.  
Öncelik: Pilot müşteri seçimi, sözleşmeler, destek/SLA, Türkçe eğitim ve dokümantasyon.