# Muhasebe / General Ledger Modernizasyonu

Durum: Faz 1–2 uygulanıyor.

## Model

CADRO, Microsoft Dynamics 365 Finance/Business Central muhasebe modelinden sonra GL posting
mapping ve account structure katmanlarını kademeli biçimde merkezileştirir.

- Company: tüzel şirket ve muhasebe varsayılanları
- Ledger: `Company` içindeki hesap planı ve GL Entry kayıtları
- Chart of Accounts: `Account` ağacı
- Fiscal Calendar: `Fiscal Year` ve `Accounting Period`
- Subledger: Sales/Purchase Invoice, Payment Entry, Bank Transaction
- GL: `GL Entry`, `Payment Ledger Entry`
- Accounting Dimensions: Cost Center, Project, Department, özel boyutlar
- Posting Profile: belge/cari/kalem/tür/para birimi için borç/alacak hesap çözümü

## Faz 1 — Feature flag + dry-run

Eklenen ayarlar:

- `enable_cadro_posting_profile`
- `cadro_posting_profile_strict_mode`
- `cadro_posting_profile_dry_run`

Varsayılan davranış geriye dönük uyumlu: bayrak kapalıyken mevcut ERPNext posting yapılır.

## Faz 2 — GL Posting Profile

Yeni DocType'lar:

- `GL Posting Profile`
- `GL Posting Profile Rule`

Rule çözümleme sırası:

```text
Document Type
→ Party Type / Party / Party Group
→ Item / Item Group
→ Transaction Type / Tax Category / Currency / Cost Center
→ profile default account
→ strict mode missing-account rejection
```

## Canlı doğrulama

27 Kasım 2026:

- Pilotta DocType'lar migrate edildi ve kayıtları bulundu.
- CADRO Teknoloji A.Ş. dry-run raporu şirket default hesaplarını, 0 party account, 0 item default ve 0 profile olarak verdi.
- Profile DocType testleri 2/2 geçti.
- Önceki denemede test ve canlı DocType klasörleri yanlış nested kopyalanınca ImportError bulundu ve düzeltildi.

## Henüz değişmeyenler

- Sales/Purchase/Payment GL composer'ları eski davranışı sürdürür.
- Strict mode ve dry-run sadece veri modeli ve rapor olarak hazırdır.
- Hesap yapılandırması ve segment doğrulaması ilerideki fazlarda gelir.
