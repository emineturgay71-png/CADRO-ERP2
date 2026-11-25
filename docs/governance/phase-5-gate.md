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
| `cadro/saas/webhook.py` | `WebhookPayload`, `WebhookEvent`; imza doğrulama, genel (CADRO imzalı JSON) adaptör, `handle_webhook` (idempotent abonelik durumu geçişleri), `sweep_overdue` |
| `cadro/saas/control_plane.py` | Bileşen servis: `serve` (HTTP webhook alıcı) ve `sweep` (süresi dolan deneme/gecikmiş ödemeleri askiya al) |

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
# depo kökünden; bench PATH'te, uygulamalar baseline commit'lerinde olmalı
python -m cadro.saas.provision_site \
    --site cadro-tenant-001.localhost \
    --admin-password-file /run/secrets/admin_password \
    --db-password-file /run/secrets/db_password \
    --plan professional
```

### Tenant yönetimi
```bash
python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action suspend
python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action reactivate
python -m cadro.saas.manage_tenant --site cadro-tenant-001.localhost --action offboard \
    --confirm cadro-tenant-001.localhost
```

### Kontrol düzlemi servisi (Docker Compose)

```bash
# paylaşımlı sır (git'te yok sayılır) — ödeme adaptörü ile aynı değer
cadro/secrets/webhook_secret

docker compose -p cadro --project-directory . --env-file cadro/.env -f cadro/docker-compose.yml \
    --profile control-plane up -d --build

# kiracı kaydı ve plan fiyatı (kayıt defteri `control-plane-data` biriminde)
docker exec -e PYTHONPATH=/home/frappe/control-plane -e CADRO_CONTROL_PLANE_DB=/control-plane-data/control_plane.db \
    cadro-control-plane python -m cadro.saas.control_plane register --site <site> --plan starter
```

- nginx yalnızca `/cadro/webhooks/` yolunu yayımlar (`POST /cadro/webhooks/generic`, hız sınırlı, 64 KB); `/healthz`, `/metrics` ve `/v1/access/<site>` yalnızca `cadro-net` içindedir.
- Profil verilmezse servis başlamaz ve `webhook_secret` dosyası gerekmez; webhook yolu 502 döner.
- `payment.succeeded` tutarı plan fiyatından farklıysa sonuç `mismatch` olur (abonelik değişmez, olay kaydedilir); fiyat `set-price` ile tanımlanır.
- `offboard` öncesi `--action export` zorunludur (en fazla 7 gün eski dışa aktarım); aksi halde reddedilir.
- 25 Kasım 2026 canlı doğrulama (Compose, nginx üzerinden): imzasız/bayat zaman damgası 401, bilinmeyen kiracı 404, uyuşmayan `tenant_id` 400, `payment.failed` → `grace`, tekrar → `duplicate`, `payment.succeeded` → `applied` (kiracı `trial` → `active`), `/metrics` nginx üzerinden 404. İlk denemede iki hata bulundu ve düzeltildi: `/control-plane-data` birimi root sahipliydi (Dockerfile'da frappe sahipliğinde oluşturuldu) ve nginx'te `rewrite … break` sonrası `set` çalışmıyordu (`set` öne alındı).

### API koruması
```python
@frappe.whitelist()
@require_active_subscription
def my_endpoint():
    # Sadece aktif veya trial süresindeki tenant'lar erişebilir
    ...
```

**Sınır:** Bu dekoratör kontrol düzlemi veritabanını (`cadro.saas.db`) okur. `cadro/` paketi bench imajında bulunmadığı için dekoratör bugünkü imajda çalıştırılamaz; kontrol düzlemi ayrı servis olarak kurulduğunda bir API üzerinden sorgulamalıdır. Bugün askıya alma `maintenance_mode` ile siteye uygulanır.

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ compileall temiz |
| Faz 0 manifesto | ✅ geçerli |
| Faz 0 testleri | ✅ 8/8 |
| Kontrol düzlemi testleri | ✅ 57/57 (`python -m unittest cadro.saas.test_saas`, CI'da çalışır) |
| Tenant modeli ve SQLite kayıt defteri | ✅ yaşam döngüsü, kota, deneme süresi |
| Provisioning | ✅ pin doğrulaması, kayıt defterine yazma (gerçek bir bench'te çalıştırılmadı) |
| Suspend/reactivate/offboard | ✅ yalnızca tenant sitesi değişir, kayıt defteri güncellenir (komutlar testte taklit edildi) |
| Ödeme webhook | ✅ `handle_webhook` ve HTTP alıcı uygulanıp test edildi (23 yeni test, gerçek yerel HTTP sunucusu dahil); somut bir ödeme sağlayıcısı bağlanmadı (bkz. “Ödeme webhook'u”) |

### 23-24 Kasım 2026 incelemesinde bulunan ve düzeltilenler

Bu modüller önceki turda hiç çalıştırılmamıştı. Testler yazılırken şu hatalar çıktı:

| Sorun | Düzeltme |
| --- | --- |
| `can_access()` UTC'siz `utcnow()` ile UTC'li kayıt tarihini karşılaştırıp `TypeError` veriyordu (her yeni tenant için) | Tüm zaman damgaları UTC farkındalıklı |
| `subscription.py` olmayan `erpnext.cadro.saas` yolundan içe aktarıyordu | `cadro.saas` olarak düzeltildi |
| `tenant_from_site` / `enforce_tenant_active` biri `NotImplementedError`, biri başka dosyada olmak üzere iki kopyaydı | Tek uygulama (`tenant.py`), kayıt defterine bakar |
| `suspend` genel (`-g`) `disable_website` ayarını yapıyordu: bir tenant'ın askıya alınması bench'teki **tüm** tenant'ların web sitesini kapatırdı | Yalnızca tenant sitesinin ayarı değişir |
| `provision_site` genel `developer_mode` ayarını değiştiriyordu, `get-app --branch <commit>` (SHA ile çalışmaz) kullanıyordu, planı uygulamıyordu, parolaları komut satırından alıyordu | Pin doğrulaması, parola dosyaları, kayıt defterine yazma; genel ayar yok |
| Site adı doğrulanmıyordu (bench argümanına gidiyor) | `validate_site_name` |
| `offboard` için `--confirm YES` herkes için aynı onaydı | Onay olarak site adının tekrarı |
| Askıya alma/yeniden etkinleştirme kayıt defterini güncellemiyordu | Güncelliyor |

## Ödeme webhook'u (24 Kasım 2026)

`NotImplementedError` veren `webhook_payment_succeeded` / `webhook_payment_failed` kısa yolları kaldırıldı; yerine olay tabanlı işleyici geldi.

| Olay | Sonuç |
| --- | --- |
| `payment.succeeded`, `subscription.renewed` | Tenant `active`; ödeme hatası temizlenir; askidaysa site yeniden etkinleştirilir |
| `payment.failed` | İlk hatada `payment_failed_since` kaydedilir, 7 gün tolerans (`grace`); süre dolunca site askiya alınır |
| `subscription.cancelled` | Site askiya alınır, tenant `cancelled` (geçersiz kalan olaylar tenant'ı geri getirmez) |
| `subscription.created`, `trial.ending` | Yalnızca olay günlüğüne yazılır |

Garanti edilenler:

- **Idempotency:** sağlayıcının `event_id` değeri `webhook_events` tablosunda birincil anahtardır; aynı teslimat `duplicate` döner ve hiçbir şey değişmez. Aynı fatura başka olay kimliğiyle gelirse `ignored`.
- **Yeniden deneme:** site işlemi (bench) başarısız olursa olay kimliği serbest bırakılır ve HTTP 500 döner; sağlayıcının tekrar denemesi yeniden işlenir.
- **İmza:** HMAC-SHA256 üzerinde `<zaman damgası>.<gövde>`, sabit zamanlı karşılaştırma, ±5 dakika zaman damgası toleransi (tekrar saldırısını sınırlar). Sır yalnızca dosyadan okunur (`CADRO_WEBHOOK_SECRET_FILE`).
- **Tenant tutarlılığı:** `tenant_id`, `site_name` ile eşleşmiyorsa istek reddedilir (400); bilinmeyen site 404; gövde 64 KB ile sınırlı.

```bash
CADRO_WEBHOOK_SECRET_FILE=/run/secrets/webhook_secret \
    python -m cadro.saas.control_plane serve --host 127.0.0.1 --port 8090   # POST /webhooks/generic, GET /healthz
python -m cadro.saas.control_plane sweep                                       # saatlik zamanlanmış görev
```

Servis düz HTTP konuşur; önüne TLS sonlandıran bir ters vekil konmalıdır. Askiya alma/yeniden etkinleştirme `bench` çalıştırdığından servis bench ile aynı makinede/konteynerde çalışır. Kayıt defteri eski sürümden gelirse `payment_failed_since` sütunu otomatik eklenir.

**Henüz yapılmayanlar:** somut sağlayıcı adaptörü (Stripe/İyzico/PayTR — seçim ve sözleşme gerekir; her biri kendi imza biçimiyle `normalize_*` yazacak), tutarın fiyat listesiyle mutabakatı (fatura sistemi gerekir), servisin compose'a eklenmesi (imajında `cadro/` ve bench erişimi gerekir), `require_active_subscription` için sorgu API'si.

## Kontrol düzlemi için sonraki adımlar (bu fazda kapatılmaz)

1. Kontrol düzlemi servisini üretim için sertleştir (PostgreSQL, compose servisi, TLS, süreç yönetimi)
2. Tenant veritabanını PostgreSQL'e taşı (bugün SQLite)
3. Ödeme sağlayıcı adaptörü ekle (Stripe/Iyzico/PayTR) — imza doğrulama ve idempotency çerçevesi hazır
4. ~~Webhook idempotency + imza doğrulama~~ (tamam, yukarıya bakın)
5. ~~Gerçek `tenant_from_site()` implementasyonu~~ (tamam)
6. KVKK/GDPR veri işleme sözleşmeleri
7. Self-service kayıt ve trial başlatma
8. Müşteri veri export ve hesap kapatma akışı

## Değişen dosyalar

```
cadro/saas/tenant.py           - yeni: tenant modeli
cadro/saas/subscription.py     - yeni: abonelik ve entitlement
cadro/saas/provision_site.py   - yeni: otomatik provisioning
cadro/saas/manage_tenant.py    - yeni: tenant yaşam döngüsü
cadro/saas/webhook.py          - ödeme webhook işleyicisi, imza doğrulama, gecikmiş ödeme taraması
cadro/saas/control_plane.py    - yeni: HTTP webhook alıcı + sweep komutu
cadro/saas/db.py               - webhook olay tablosu, payment_failed_since
docs/governance/phase-5-gate.md - bu dosya
```

## Sonraki adım

Faz 6 — Kontrollü gelir ve lansman.  
Öncelik: Pilot müşteri seçimi, sözleşmeler, destek/SLA, Türkçe eğitim ve dokümantasyon.