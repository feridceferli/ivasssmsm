# IVAS SMS — müstəqil veb panel və şəxsi API

Telegram botundan ayrılıqda Render-də işləyən Flask/Gunicorn xidməti.

## Ünvanlar

- `/`: əsas veb panel
- `/sms-dashboard`: SMS monitoru və ölkə/xidmət siyahısı
- `/health`: server statusu
- `/api/v1`: API sənədləri
- `/api/v1/status`: qorunan API vəziyyəti
- `/api/v1/ranges`: qorunan ölkə/xidmət diapazon metadatası
- `/api/v1/sms/status`: qorunan monitor və upstream konfiqurasiya statusu
- `/api/v1/sms/stats`: qorunan ümumi SMS sayları və gəlir; fərdi mesajlar çıxarılmır

## Render Environment

| Ad | Məqsəd |
|---|---|
| `IVAS_PRIVATE_API_KEY` | Sayta giriş üçün ayrı, güclü açar; SMS panelinə daxil edilir |
| `IVAS_OFFICIAL_API_TOKEN` | Rəsmi provayderdən alınmış API açarı |
| `IVAS_AVAILABILITY_URL` | Rəsmi provayderin ölkə və xidmət mövcudluq JSON endpoint-i |
| `IVAS_SMS_STATS_URL` | Rəsmi provayderin yalnız **ümumi SMS statistikası** qaytaran JSON endpoint-i |

`IVAS_SMS_STATS_URL`-in mövcud olduğu **təsdiqlənməyib**. Bu sahəyə rəsmi sənədlərdə göstərilmiş, həqiqətən aggregate statistika verən ünvan daxil edilməlidir. Köhnə cookie/CSRF scraping endpoint-lərini istifadə etməyin. Rəsmi API bu funksiyanı dəstəkləmirsə, monitor `stats_not_configured` göstərəcək; məlumat uydurulmayacaq.

Rəsmi API domeni yalnız `ivasms.com`, `www.ivasms.com` və ya `api.ivasms.com` ola bilər. HTTPS tələb olunur. API açarlarını kodda, GitHub-da və söhbətlərdə paylaşmayın.

## Sorğu nümunəsi

```bash
curl https://ivasssmsm-web.onrender.com/api/v1/sms/status \
  -H "X-API-Key: SIZIN_MEXFI_ACARINIZ"
```

```bash
curl https://ivasssmsm-web.onrender.com/api/v1/sms/stats \
  -H "X-API-Key: SIZIN_MEXFI_ACARINIZ"
```

Sistem rəsmi API-nin cavabından yalnız `count_sms`, `paid_sms`, `unpaid_sms` və `revenue` kimi **ümumi statistikaları** götürür. SMS mətnləri, OTP kodları, telefon nömrələri və sessiya kukiləri çıxarılmır. Məlumat mövcud olmayanda `0` deyil, `null` və ya izahedici xəta qaytarılır.

## Quraşdırma və test

```bash
pip install -r requirements.txt
python -m unittest -v test_sms_monitor
python safe_app.py
```

Render üçün Build Command: `pip install -r requirements.txt`. Start Command: `python safe_app.py` (öz-özünə Gunicorn-a keçir).

**Təhlükəsizlik:** Köhnə `cookies.json` Git tarixində qala bilər. Köhnə sessiyaları ləğv edin və rəsmi provayderdəki sessiyanı yeniləyin. Orijinal `/sms` OTP endpoint-i yeni `app.py`-də aktiv deyil.
