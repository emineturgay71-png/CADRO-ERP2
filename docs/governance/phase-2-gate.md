# Faz 2 — Tekrarlanabilir üretim ve kontrollü pilot altyapısı tamamlanma kaydı

Tarih: 20 Kasım 2026 (sertleştirme: 23 Kasım 2026).
Durum: **Altyapı kuruldu ve pilot üzerinde çalışıyor. Üretim sertleştirmesinin büyük kısmı yapıldı; üretim onayı verilmedi.**

## Oluşturulan altyapı dosyaları

| Dosya | Amaç |
| --- | --- |
| `cadro/Dockerfile` | Python 3.14 + Node 24 tabanlı Bench imajı; entrypoint'te pinli commit'lerle kurulum |
| `cadro/docker-compose.yml` | MariaDB 11.8 + 3× Redis + bench (gunicorn) + socketio + worker + scheduler + nginx; digest pin'li, secret'lı, healthcheck'li |
| `cadro/nginx/cadro.conf` | Statik dosya, uygulama ve socket.io vekili; giriş hız sınırı |
| `scripts/image_security_scan.py` | Trivy ile CycloneDX SBOM ve zafiyet özeti |
| `.github/workflows/cadro-image.yml` | Baseline, compose/entrypoint denetimi, imaj build, SBOM |
| `cadro/entrypoint.sh` | İlk çalıştırmada Bench provisioning; `cadro.baseline.json` pin'lerini kullanır |
| `cadro/mariadb/conf.d/cadro.cnf` | UTF8mb4, 512M buffer pool, staging uygunluk ayarları |
| `scripts/backup_site.sh` | Site bazlı veritabanı + dosya yedeği; metadata dosyası üretir |
| `scripts/restore_site.sh` | Onaylı geri yükleme; site verisini tamamen değiştirir |
| `scripts/healthcheck.py` | Docker HEALTHCHECK için Redis/DB/scheduler denetimi |
| `scripts/ci_pin_resolver.py` | `cadro.baseline.json`'dan CI ortam değişkeni için commit SHA çözücü |

## Compose servis mimarisi (23 Kasım 2026)

```
                 :8001
              ┌─────────┐   /assets, /files (bench volume, salt okunur)
 tarayıcı ──► │  nginx  │──┬─► bench      gunicorn (gthread), :8000
              └─────────┘  └─► socketio   node, :9000  (/socket.io)

 worker (bench worker)   scheduler (bench schedule)   ← aynı imaj, aynı bench volume'u
 ┌──────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
 │ MariaDB  │  │ redis-cache   │  │ redis-queue   │  │redis-socketio │
 │  11.8    │  │   7-alpine    │  │   7-alpine    │  │   7-alpine    │
 └──────────┘  └───────────────┘  └───────────────┘  └───────────────┘
```

- `bench` servisi (`cadro-web`) bench'i kurar/günceller, hazır işaretçisini yazar ve gunicorn ile sunar. `socketio`, `worker` ve `scheduler` servisleri işaretçiyi bekleyip başlar.
- Yalnızca nginx dışarı açılır (`8001`). Uygulama ve gerçek zamanlı portu ağ içindedir.
- `bench start` (Werkzeug geliştirme sunucusu, `DEV_SERVER=1`) artık yalnızca tek konteynerli geliştirme modudur (imajın varsayılan CMD'si).
- Giriş uç noktası nginx'te hız sınırlıdır (dakikada 10 istek, 10 burst; sonrası `429`).
- Parolalar Docker secret olarak verilir (`cadro/secrets/*`, git dışı; `*_FILE` ortam değişkenleri).

## Kullanım

```bash
# Sırlar (bir kez üretilir, git'e girmez)
mkdir -p cadro/secrets
printf '%s' "guclu-bir-sifre"  > cadro/secrets/db_password
printf '%s' "admin-sifresi"    > cadro/secrets/admin_password
echo "SITE_NAME=cadro-pilot.localhost" > cadro/.env

# İlk çalıştırma (pin'li commit'lerle kurulum), depo kökünden
docker compose -p cadro --project-directory . --env-file cadro/.env \
  -f cadro/docker-compose.yml up -d --build

# Yedekleme
docker exec cadro-bench bash scripts/backup_site.sh cadro-pilot.localhost

# Geri yükleme
docker exec cadro-bench bash scripts/restore_site.sh cadro-pilot.localhost /path/to/backup

# CI'da pin okuma
FRAPPE_COMMIT=$(python scripts/ci_pin_resolver.py --component frappe)
```

## Sertleştirme durumu (23 Kasım 2026)

| Madde | Durum |
| --- | --- |
| İmaj digest pin'leme | ✅ `mariadb:11.8`, `redis:7-alpine`, `nginx:1.27-alpine` ve taban `python:3.14-slim` `@sha256` ile sabit |
| Secret yönetimi | ✅ Docker secret + `*_FILE` desteği (compose'ta parola ortam değişkeni yok). Vault/secret manager üretimde ayrıca gerekir |
| Üretim web sunucusu | ✅ gunicorn + nginx; geliştirme sunucusu yalnızca geliştirme modunda |
| Giriş hız sınırı | ✅ nginx `limit_req` (DDoS koruması için önde WAF/CDN gerekir) |
| SBOM | ✅ `docs/governance/sbom/cadro-bench.cdx.json` (CycloneDX, Trivy 0.76.2, ~1.6 bin bileşen); `scripts/image_security_scan.py` ile yenilenir. Lisans envanteri ayrıca çıkarılmadı |
| CVE taraması | ✅ Aşağıya bakın |
| CI entegrasyonu | ✅ `.github/workflows/cadro-image.yml` (baseline doğrulama, compose/entrypoint denetimi, imaj build, SBOM) — GitHub'da henüz çalıştırılmadı |
| Canlı Bench testleri | ✅ MariaDB + PostgreSQL (bkz. Faz 1) |
| CADRO imaj etiketi | ✅ Etiket `CADRO_IMAGE_TAG` ile verilir (varsayılan `eval`); örnek: `CADRO_IMAGE_TAG=$(git rev-parse --short HEAD)`. Kayıt defterine gönderme ve sürüm numaralandırma kararı bekliyor |
| Yük ve kapasite testi | ⚠️ Duman düzeyinde taban değerler çıkarıldı (aşağıda); gerçek veriyle yük testi yapılmadı |
| Yedekleme/geri yükleme tatbikatı | ✅ 23 Kasım 2026, ayrıntılar aşağıda |
| Zamanlanmış yedek ve site dışı kopya | ✅ `backup` servisi: günde bir, son 14 yedek, ana makine dizinine (`cadro/backups`, bench volume'u dışında). Makine dışına kopyalama (nesne depolama, başka disk) hâlâ yok |
| TLS / harici ters vekil, izleme/alarm | ⏳ Yapılmadı |

### Zafiyet taraması (Trivy, `cadro-bench:eval`)

| | `apt upgrade` öncesi | sonrası |
| --- | --- | --- |
| CRITICAL | 1 | 1 |
| HIGH | 235 | 160 |
| MEDIUM | 834 | 679 |
| HIGH, düzeltmesi yayımlanmış | 86 | 11 |

- Dockerfile artık `apt-get upgrade` çalıştırır; Debian'ın yayımladığı düzeltmeler uygulandı. Kalan OS zafiyetlerinin Debian'da henüz düzeltmesi yok (ör. `libxml2` CRITICAL, `curl`, `openssl`, `git`, `systemd`); izlenmeli.
- Düzeltmesi yayımlanmış kalan 11 HIGH bench sanal ortamındaki Python paketleri (`urllib3`, `setuptools`, `msgpack`) ve Node/npm içindeki paketlerdir (`undici`, `brace-expansion`). Python paketleri Frappe'nin kendi bağımlılıklarıdır, Frappe pin'i güncellenerek çözülür.
- Bu bir değerlendirme taramasıdır; üretim onayı için risk kabulü ve düzenli yeniden tarama gerekir (`dependency-audit.yml` upstream'e aittir).

### Yedekleme/geri yükleme tatbikatı (23 Kasım 2026)

Pilot site yedeklendi, ayrı bir tatbikat sitesine (`cadro-drill.localhost`) geri yüklendi ve karşılaştırıldı. Pilota dokunulmadı.

| Ölçüt | Sonuç |
| --- | --- |
| Yedekleme süresi / boyut | 5 sn / 1,4 MB (veritabanı 1,1 MB, özel dosyalar 0,2 MB) |
| Geri yükleme süresi | 107 sn (çoğu `migrate`); bu küçük bir pilot veri kümesidir, büyük veride artar |
| Tablo ve satır sayısı | 807 tablo, 26.856 satır; kaynak ve geri yüklenen arasında **0 fark** |
| Yönetici girişi | ✅ geri yüklenen sitede parola ile giriş çalışıyor |
| Şifreli alan | ✅ kaynakta saklanan değer (Türkçe karakterli) tatbikat sitesinde doğru çözüldü; geri yükleme `encryption_key`'i de yeniden uyguluyor |
| Bozulmuş yedek | ✅ sağlama toplamı uyuşmazlığında geri yükleme reddedildi (çıkış kodu 1), hiçbir veri değişmedi |
| Yanlış onay | ✅ `RESTORE-<site>` yazılmazsa iptal (çıkış kodu 2) |

Betikler bu tatbikatta düzeltildi: eski geri yükleme dizini `bench restore`'a veriyordu (dosya bekler), kök parolayı geçmiyordu, site config'i/şifreleme anahtarını geri yüklemiyordu ve betikler imajda yoktu. Yeni sürüm sağlama toplamı manifesti (`SHA256SUMS`), uygulama commit'leri (`backup_metadata.json`) ve onay denetimi içerir; imaja kopyalanır (`docker exec cadro-bench bash scripts/backup_site.sh <site>`).

Sınırlar: Yedekler varsayılan olarak bench volume'unda (`cadro-data/cadro-backups`) durur, yani volume kaybolursa onlar da kaybolur; site dışına (nesne depolama, başka disk) kopyalama otomatik değildir. Tatbikatta işlem kaydı yoktu (GL Entry, fatura vb. 0); büyük ve hareketli veriyle yeniden denenmelidir. Zamanlanmış yedek ve saklama (retention) tanımlı değildir.

Zamanlanmış yedek: `backup` servisi (`cadro-backup` rolü) ilk yedeği başlangıçta, sonra her `CADRO_BACKUP_INTERVAL_HOURS` (24) saatte bir alır ve ana makinedeki `CADRO_BACKUP_DIR` dizinine (varsayılan `cadro/backups`) yazar; son `CADRO_BACKUP_KEEP` (14) yedek tutulur. İlk yedek ana makine dizininde doğrulandı. Linux ana makinede dizin uid 1000 tarafından yazılabilir olmalıdır.

### Yük taban değerleri (duman düzeyi, 23 Kasım 2026)

`scripts/load_smoke.py` ile nginx üzerinden, tek bir Windows makinede (istemci ve sunucu aynı makine), küçük pilot veri kümesiyle, her düzeyde 8 sn. Hata sayısı tüm düzeylerde 0.

| Uç nokta | 20 eşzamanlı | 50 eşzamanlı |
| --- | --- | --- |
| `ping` (herkese açık) | ~880 istek/sn, p95 47 ms | ~840 istek/sn, p95 125 ms |
| `/login` sayfası | ~83 istek/sn, p95 484 ms | ~73 istek/sn, p95 1,3 sn |
| Hesap listesi (kimlikli API) | ~580 istek/sn, p95 63 ms | ~560 istek/sn, p95 188 ms |
| DocType listesi (kimlikli API) | ~390 istek/sn, p95 79 ms | ~390 istek/sn, p95 250 ms |

Gunicorn 3 işçi × 4 iş parçacığı ile çalışır; sayfa oluşturma (`/login`) ilk doyan uç noktadır. İstemci zamanlayıcısı ~15 ms çözünürlüklüdür, düşük gecikmeler yaklaşıktır. Bu değerler gerçek veri, çok kullanıcılı iş akışı veya üretim donanımı için kapasite iddiası oluşturmaz.

Bulunan ve düzeltilen: nginx başlangıçta `bench` adresini bir kez çözüyordu; `bench` konteyneri yeniden oluşturulunca eski IP'ye bağlı kalıp `502` veriyordu. Artık adresler istek anında Docker DNS ile çözülür (`resolver 127.0.0.11`); `bench` yeniden oluşturulduktan sonra `ping` `200` döndü.

| Madde | Açıklama |
| --- | --- |
| Vault / secret manager | Docker secret dosyaları yerine merkezi sır yönetimi |
| Sürüm numaralandırma ve kayıt defteri | Etiket değişkeni hazır; hangi sürüm şemasının ve deponun kullanılacağı kararı |
| Gerçek veriyle yük ve kapasite testi | Gerçek import/mutabakat yükleri ve çok kullanıcılı senaryolar |
| TLS, WAF/CDN, izleme | Dış ters vekil, sertifikalar, alarm |
| Yedeklerin makine dışına kopyalanması | Nesne depolama veya ikinci disk; geri yükleme tatbikatının periyodik tekrarı |
| Kalan zafiyetlerin risk kabulü | Düzeltmesi olmayan OS paketleri |

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
| Python syntax | ✅ healthcheck.py, ci_pin_resolver.py, image_security_scan.py |
| Shell syntax | ✅ `bash -n cadro/entrypoint.sh` |
| Faz 0 manifesto ve testleri | ✅ geçerli, 8/8 |
| CI pin çözücü | ✅ doğru SHA'ları döndürüyor |
| Docker build | ✅ imaj derleniyor (Debian 13, `apt upgrade`, Chromium kütüphaneleri, `postgresql-client`) |
| Pilot yığını | ✅ 9 konteyner sağlıklı; nginx → gunicorn, `/assets`, `/socket.io`, socket.io kökene geri çağrı |
| Duman taraması (yeni topoloji) | ✅ Faz 0, 2, 4: 0 hata sayfası; sonuçlar eski topolojiyle aynı |
| Giriş hız sınırı | ✅ 16 istekte 11 × `401`, 5 × `429` |

## Sonraki adım

Faz 3 — Tam Türkçe ürün deneyimi.  
Öncelik: PO/POT kalite envanteri, çeviri yarışı düzeltmesi, tarih/TRY yerelleştirmesi, baskı/e-posta testleri.