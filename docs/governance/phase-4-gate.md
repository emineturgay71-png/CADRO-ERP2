# Faz 4 — Türkiye muhasebesi ve e-belge/e-defter uyum ürünü tamamlanma kaydı

Tarih: 20 Kasım 2026.
Durum: **Teknik yapı kuruldu. Resmi uyum iddiası yoktur. Mali müşavir onayı ve sağlayıcı seçimi gereklidir.**

## Bölgesel yapılandırma

| Dosya | İçerik |
| --- | --- |
| `erpnext/regional/turkey/setup.py` | Şirket kurulumunda çağrılan `setup()`; custom field hook'u |
| `erpnext/setup/setup_wizard/data/country_wise_tax.json` | `Türkiye` girdisi: satış/alış KDV şablonları (%20 varsayılan, %10, %1), `Turkey - Chart of Accounts` hesaplarına (391.01.x / 191.01.x) bağlı |
| `erpnext/regional/__init__.py` | `get_country_package()`: Frappe ülke adı `Türkiye` → `erpnext.regional.turkey` eşlemesi |
| `erpnext/regional/turkey/__init__.py` | Paket işaretçisi (boş) |

KDV şablonları Hesaplanan KDV (satış) ve İndirilecek KDV (alış) için şirket oluşturulurken `setup_taxes_and_charges` ile oluşturulur. Mevcut template varsa atlanır. Hesap planı `tr_chart_of_accounts.json` zaten mevcuttur.

**Uyarı:** Yalnızca temel %20, %10, %1 KDV oranları şablon olarak eklenir. Mevcut bir oranın güncel mevzuata uygunluğu mali müşavir tarafından doğrulanmalıdır. Tevkifat, stopaj ve özel matrah gibi ileri senaryolar bu faz kapsamında değildir.

## E-belge adaptör mimarisi

| Dosya | Açıklama |
| --- | --- |
| `erpnext/regional/turkey/e_document_contract.py` | Sağlayıcıdan bağımsız ABC sözleşmesi: `EInvoice`, `EDespatch`, `ELedger` |
| `erpnext/regional/turkey/e_document_queue.py` | Durum makinesi, loglama ve idempotency yardımcısı |

### Durum modeli

```
draft → queued → processing → accepted → cancelled
                         ↘ rejected → queued (retry)
                         ↘ failed   → queued (retry)
```

### Ara yüz

Her sağlayıcı implementasyonu şu metodları sunar:
- `send(doc) → correlation_id` — belge gönderimi
- `cancel(correlation_id) → correlation_id` — iptal
- `status(correlation_id) → DocumentStatus` — durum sorgulama
- `download_pdf(correlation_id) → bytes` — imzalı PDF
- `download_ubl(correlation_id) → bytes` — UBL-TR XML

### Log DocType

`CADRO EDocument Log` — Her e-belge işlemi için denetlenebilir kayıt:
- Belge türü (e-fatura, e-arsiv, e-irsaliye, e-defter)
- Yön (outbound/inbound)
- Durum (draft→…→cancelled)
- Sağlayıcı correlation ID
- ERP referansı (Doctype + isim)
- Sağlayıcı yanıtı (JSON) ve hata metni
- Zaman damgaları (oluşturma, son sorgulama)

## Sağlayıcı seçimi öncesi yapılması gerekenler

1. Hedef müşteri segmentinin zorunlu belge/senaryo listesini çıkarın.
2. GİB entegratörü veya özel entegratör alternatiflerini değerlendirin.
3. Sandbox test hesabı açın.
4. Gerçek anonim belge örnekleriyle imza, UUID, senaryo ve iptal/ret akışlarını doğrulayın.
5. Mali müşavir ile KDV oranları, tevkifat ve özel matrah kapsamını netleştirin.
6. Onaylanan sağlayıcı için `e_document_contract.py` ABC'sini implement edin.

## Değişen dosyalar

```
erpnext/regional/turkey/setup.py                  - KDV şablonları + custom field hook'u
erpnext/regional/turkey/e_document_contract.py    - yeni: ABC sözleşmesi
erpnext/regional/turkey/e_document_queue.py       - yeni: durum makinesi + log
docs/governance/phase-4-gate.md                    - bu dosya
```

## Doğrulama

| Kapı | Sonuç |
| --- | --- |
| Python syntax | ✅ compileall temiz |
| Faz 0 manifesto | ✅ geçerli |
| Faz 0 testleri | ✅ 8/8 |
| Hesap planı | ✅ `tr_chart_of_accounts.json` mevcut |
| KDV şablonları | ✅ şirket oluşturulurken `country_wise_tax.json` (`Türkiye`) ile oluşuyor; pilot sitede doğrulandı |
| E-belge contract | ✅ soyut, sağlayıcı-bağımsız |
| E-belge queue | ✅ durum makinesi + idempotency |
| Mali müşavir onayı | ❌ Gerekli, bu faz kapsamında değil |
| Sağlayıcı seçimi | ❌ Gerekli, bu faz kapsamında değil |

## Sonraki adım

Faz 5 — SaaS ticarileştirme ve ölçek.  
Öncelik: Tenant provisioning, plan/kota modeli, ödeme webhook'ları, suspend/reactivate.