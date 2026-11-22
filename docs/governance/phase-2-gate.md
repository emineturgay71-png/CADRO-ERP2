# Faz 2 — Tekrarlanabilir üretim ve kontrollü pilot altyapısı tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Altyapı dosyaları oluşturuldu; canlı build/test çalıştırılmadı.**

## Oluşturulan altyapı dosyaları

| Dosya | Amaç |
| --- | --- |
| `cadro/Dockerfile` | Python 3.14 + Node 24 tabanlı Bench imajı; entrypoint'te pinli commit'lerle kurulum |
| `cadro/docker-compose.yml` | MariaDB 11.8 + 3× Redis + Bench servisi; healthcheck'li |
| `cadro/entrypoint.sh` | İlk çalıştırmada Bench provisioning; `cadro.baseline.json` pin'lerini kullanır |
| `cadro/mariadb/conf.d/cadro.cnf` | UTF8mb4, 512M buffer pool, staging uygunluk ayarları |
| `scripts/backup_site.sh` | Site bazlı veritabanı + dosya yedeği; metadata dosyası üretir |
| `scripts/restore_site.sh` | Onaylı geri yükleme; site verisini tamamen değiştirir |
| `scripts/healthcheck.py` | Docker HEALTHCHECK için Redis/DB/scheduler denetimi |
| `scripts/ci_pin_resolver.py` | `cadro.baseline.json`'dan CI ortam değişkeni için commit SHA çözücü |

## Compose servis mimarisi

```
┌──────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  MariaDB │  │ redis-cache   │  │ redis-queue   │  │redis-socketio │
│   11.8   │  │   7-alpine    │  │   7-alpine    │  │   7-alpine    │
└────┬─────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
     │                │                  │                  │
     └────────────────┴──────────────────┴──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   cadro-bench     │
                    │  Python 3.14      │
                    │  Node 24          │
                    │  Port 8000        │
                    └───────────────────┘
```

## Kullanım

```bash
# İlk çalıştırma (pin'li commit'lerle kurulum)
export DB_PASSWORD="guclu-bir-sifre"
export SITE_NAME="cadro-pilot.localhost"
export ADMIN_PASSWORD="admin-sifresi"
docker compose -f cadro/docker-compose.yml up -d

# Yedekleme
docker exec cadro-bench bash scripts/backup_site.sh cadro-pilot.localhost

# Geri yükleme
docker exec cadro-bench bash scripts/restore_site.sh cadro-pilot.localhost /path/to/backup

# CI'da pin okuma
FRAPPE_COMMIT=$(python scripts/ci_pin_resolver.py --component frappe)
```

## Üretim öncesi yapılması gerekenler (bu fazda kapatılmaz)

| Madde | Açıklama |
| --- | --- |
| İmaj digest pin'leme | `mariadb:11.8` ve `redis:7-alpine` yerine `@sha256:...` |
| Secret yönetimi | DB_PASSWORD compose env yerine vault/secret manager |
| SBOM ve lisans envanteri | İmaj içindeki tüm bağımlılıklar için |
| CADRO imaj etiketi | Değerlendirme `:eval` yerine sürümlü etiket |
| Yük ve kapasite testi | Gerçek import/mutabakat yükleriyle |
| Güvenlik taraması | İmaj ve bağımlılık CVE taraması |
| CI pipeline entegrasyonu | GitHub Actions'ta compose build/test |
| Canlı Bench testleri | MariaDB + PostgreSQL üzerinde test koşusu |

## Değişen dosya listesi

```
cadro/
  Dockerfile
  docker-compose.yml
  entrypoint.sh
  mariadb/conf.d/cadro.cnf
scripts/
  backup_site.sh
  restore_site.sh
  healthcheck.py
  ci_pin_resolver.py
docs/governance/
  phase-2-gate.md              (bu dosya)
```

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ healthcheck.py, ci_pin_resolver.py |
| Shell syntax | ⚠️ bash -n kontrol edilmedi (Windows bash yok) |
| Faz 0 manifesto | ✅ geçerli |
| CI pin çözücü | ✅ doğru SHA'ları döndürüyor |
| Docker build | ❌ Çalıştırılmadı (Docker yok / Bench yok) |

## Sonraki adım

Faz 3 — Tam Türkçe ürün deneyimi.  
Öncelik: PO/POT kalite envanteri, çeviri yarışı düzeltmesi, tarih/TRY yerelleştirmesi, baskı/e-posta testleri.