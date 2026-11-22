# Sürüm ve bağımlılık manifestosu

Durum: Faz 0 değerlendirme tabanı. **Kararlı veya onaylı üretim sürümü değildir.**
Gözlem tarihi: 20 Kasım 2026.

Makine okunur kanıt: `cadro.baseline.json`.
Doğrulama: `python scripts/validate_cadro_baseline.py` ve `python scripts/check_upstream_baseline.py`.

## Amaç

`develop` dallarının her kurulumda başka bir ürün getirmesini engellemek. Bir manifestodaki commit kimlikleri tekrarlanabilirlik için teklif edilen pin'lerdir; bağımlılıkların birlikte çalıştığı, güvenli olduğu veya üretim için desteklendiği anlamına gelmez.

## Faz 0 uygulama pinleri

| Uygulama | Kaynak/ref | Sabit commit | Üretim durumu |
| --- | --- | --- | --- |
| ERPNext | `frappe/erpnext`, `develop` | `920f1d5b3d18142cf3c4cc6edf59e53950a7832b` | Değerlendirme; 17-dev |
| Frappe | `frappe/frappe`, `develop` | `96c27e16ed5cfcfaf27d1db2f40c5c7acf871bbd` | Değerlendirme; eşleşme testi bekliyor |
| payments | `frappe/payments`, `develop` | `d6df15a6ce91e508d58fe34ba53e27f3b63d344e` | Değerlendirme; eşleşme testi bekliyor |

Üç SHA da ilgili GitHub commit uçlarında 20 Kasım 2026 tarihinde doğrulanmıştır. Repo için seçilen ERPNext SHA yerel kaynak ile aynıdır.

Bu üç uygulama aynı Bench'te yeniden derlenmeli; `install.sh` ve CI bunlara dinamik `develop` adıyla değil doğrulanmış manifest commit'iyle erişmelidir. CI değişikliği henüz yapılmamıştır, aşağıdaki kapatılacak iş kapsamındadır.

## Mevcut bildirimsel sürümler

| Alan | Doğrulanmış bilgi | Tekrarlanabilirlik sınırı |
| --- | --- | --- |
| ERPNext paketi | `erpnext/__init__.py`: `17.0.0-dev` | Semantik sürüm tek commit belirtmez; manifest gerekir |
| Python | `pyproject.toml`: `>=3.14`; CI Python 3.14 | Alt sürüm ve base imaj henüz sabit değil |
| Node | Bankacılık/test CI: Node 24 | Alt sürüm ve yerel ortam sabit değil |
| Yarn | Yarn Classic lockfile'ları ve `yarn.lock` | CI/yerel araç sürümü sabit değil |
| Bankacılık | `banking/package.json`, `banking/yarn.lock` | Transitive çözümler lockfile'a bağlı |
| Islands | `islands/package.json`, `islands/yarn.lock` | `frappe-ui=1.1.0`; integrity lockfile'da |
| Framework UI | `@framework/ui: link:../../frappe/ui` | Registry sürümü değil; seçilen Frappe commit'inin `ui/` kaynağıdır |
| Frappe UI ek paketi | `frappe-ui=1.1.0` | `@framework/ui` ile aynı şey değildir |
| Root frontend | `package.json`, `yarn.lock` | CAD/Three.js ve bağımlılıklar lockfile'a bağlı |
| CI imajları | Python/Node/veritabanı sürüm içeren tag'ler | Tag yerine digest pinleme ve imaj uyumluluğu gerekli |
| payments | Ayrı Bench uygulaması | Dinamik `develop` indirilmesi kaldırılacak |

## Üretim hattı kararı

Kaynak, `develop` üzerinde ERPNext `17.0.0-dev`'dir. `SECURITY.md` 15.x/16.x desteklenir derken v17 için CADRO üretim desteği ilan edilemez.

Analiz adayı ERPNext `v16.23.0`, commit `b1ca423e119e14c8edb54138c3be4b493b71834e`'dir. Bu seçim **taşıma kararı veya sürüm yükseltme/düşürme işlemi değildir**. Aynı hat için uygun Frappe ve payments eşleşmesi doğrulanmalıdır.

| Karar | Sonraki kanıt |
| --- | --- |
| v16'ya geriye taşımak veya v17'de kalmak | Bankacılık import/PDF ve CAD/BOM bağımlılık farkı; migration ve test maliyeti |
| Desteklenen Frappe/payments eşleşmesi | Upstream uyumluluk kaynağı, build ve MariaDB/PostgreSQL testleri |
| Ürün sürüm şeması | Teknik upstream sürümünden ayrı CADRO ürün release kararı; bu aşamada numara atanmaz |
| Destek aralığı | CADRO SECURITY/release politikası ve sorumlu onayı |

## Bağımlılık güncelleme ve doğrulama protokolü

1. `cadro.baseline.json` içindeki uygulama commit'lerini bilinçli PR ile değiştirin; değişmeyen alanları boş bırakmayın.
2. `python scripts/validate_cadro_baseline.py` ile şema, tam SHA ve işaretli lockfile bütünlük kayıtlarını doğrulayın.
3. `python scripts/check_upstream_baseline.py` ile ERPNext tabanının ilgili upstream deposuna ait olduğunu ve fork farkını doğrulayın. Bu yardımcı dış API gerektirir; release build'i için ağ zorunluluğu oluşturmaz.
4. `yarn.lock`, `banking/yarn.lock`, `islands/yarn.lock` değişikliklerini ilgili manifest ile birlikte gözden geçirin; bağımlılıkları elle lisanslı/güvenli ilan etmeyin.
5. CI kurulumunu manifest pinlerine taşıyın; installer/açık `FRAPPE_BRANCH` override'ı manifestle çelişiyorsa işi durdurun.
6. Kurulan Bench'in `apps/*/HEAD` kayıtlarını, imaj digestlerini ve runtime sürümlerini release raporuna ekleyin.
7. Build, MariaDB/PostgreSQL ve migration testlerini çalıştırın; yalnız SHA geçerliliğiyle üretim oluru vermeyin.
8. Tam direkt/transitive Python, NPM ve sistem bağımlılıkları için SBOM, lisans matrisi ve üçüncü taraf bildirimlerini üretin.

## Faz 0 kapanması için açık teknik işler

- [ ] CI installer, Frappe ve payments için manifest commit'lerini zorunlu kullanır.
- [ ] CI ve üretim imajları tag değil immutable digest ile seçilir.
- [ ] Yerel ve CI Python/Node/Yarn patch sürümleri tek politika olarak kayıtlıdır.
- [ ] SBOM ve üçüncü taraf lisans envanteri çıkarılmıştır.
- [ ] v16 geriye taşıma analizi yapılmış, eşleşen Frappe/payments hattı seçilmiştir.
- [ ] CADRO desteklenen sürüm ve güvenlik bildirim politikası onaylanmıştır.
- [ ] CI ürün dağıtımında upstream repo/hesaplarına yayın yapan otomasyon için CADRO guard'ları vardır.

Bu kontroller tamamlanmadan pinli kaynak “reprodüksiyon kaydı” olarak kalır; ticari destek taahhüdü oluşturulmaz.
