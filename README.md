# IVAS SMS — şəxsi API və veb idarəetmə

Bu layihə istifadəçinin göndərdiyi **orijinal IVAS portal mexanizmi** ilə uyğunlaşdırılıb. Şəxsi API və veb-panel botdan ayrı işləyir.

## İki fərqli açar anlayışı

1. `IVAS_PRIVATE_API_KEY` — **sənin yaratdığın API-yə daxil olmaq** üçün açardır. Bunu IVAS veb-panelində yazırsan. Bu açar IVAS saytına daxil olmur.
2. `COOKIES_JSON` — **sənin IVAS portal hesabının aktiv giriş sessiyasıdır**. Orijinal `app.py` bununla portal səhifəsini açır və formun CSRF tokenindən istifadə edirdi. Yeni, məxfi server adapteri də həmin axının yalnız ümumi statistikalar hissəsini tətbiq edir.

`IVAS_OFFICIAL_API_TOKEN` və `IVAS_SMS_STATS_URL` orijinal cookie əsaslı kodunun parametrləri deyil. **COOKIES_JSON olduqda SMS statistikası üçün bunlar tələb olunmur.** Rəsmi provayder API-sini ayrıca istifadə etmək istəsən, onlar ehtiyat variant kimi qalır.

## Render Environment

| Dəyişən | Tələb olunur? | Məqsəd |
| --- | --- | --- |
| `IVAS_PRIVATE_API_KEY` | Bəli | Öz API-nin giriş açarı |
| `COOKIES_JSON` | Portal statistikasını görmək üçün bəli | Öz IVAS hesabının aktiv sessiya kukiləri (JSON obyekt və ya brauzer cookie siyahısı) |
| `IVAS_OFFICIAL_API_TOKEN` | Xeyr | Yalnız ayrıca sənədləşdirilmiş rəsmi API variantı |
| `IVAS_SMS_STATS_URL` | Xeyr | Yalnız ayrıca sənədləşdirilmiş rəsmi statistika variantı |
| `IVAS_AVAILABILITY_URL` | Xeyr | Ölkə/xidmət mövcudluğunu rəsmi API-dən göstərmək istəsən |

`COOKIES_JSON` nümunəsi (saxta dəyərlərlə):

```json
{"laravel_session":"YENI_SESSIYA_KUKISI","XSRF-TOKEN":"YENI_CSRF_KUKISI"}
```

Bu nümunə **işlək giriş məlumatı deyil**. Real sessiya kukilərini yalnız Render Environment-də saxla; GitHub-a, mesajlara, ekran görüntülərinə və ya `cookies.json` faylına yerləşdirmə. Köhnə repository tarixində kukilər açıq paylaşılmış ola bilər, həmin sessiyaları ləğv et və yenilə.

## Endpoint-lər

- `/`: əsas sayt.
- `/sms-dashboard`: şəxsi API açarı ilə giriş; gün üzrə SMS sayı, ödənilmiş və ödənilməmiş saylar, gəlir.
- `/api/v1/sms/status`: API və portal sessiyası üçün konfiqurasiya statusu.
- `/api/v1/sms/stats`: orijinal IVAS portalından ümumi SMS statistikası.
- `/api/v1/sms/stats?date=09%2F10%2F2026`: seçilən gün üzrə statistika.
- `/api/v1/status`, `/api/v1/ranges`: əvvəlki təhlükəsiz meta-endpoint-lər.
- `/health`: server sağlamlığı.

Məxfi endpoint-lər üçün `X-API-Key` göndər:

```bash
curl 'https://ivasssmsm-web.onrender.com/api/v1/sms/stats' \
  -H 'X-API-Key: OZ_SEXSI_API_ACARIN'
```

### Nələr *göstərilmir*?

Fərdi telefon nömrələri, mesaj göndərənləri, SMS mətnləri, təsdiqləmə/OTP kodları, kukilər və CSRF tokenləri API cavabına daxil edilmir. Orijinal tətbiq bu məlumatları təqdim edirdi; yeni versiya yalnız ümumi statistikaları götürür.

### Giriş xətaları

- `portal_cookie_not_configured`: `COOKIES_JSON` əlavə edilməyib.
- `portal_session_expired`: portal sessiyası vaxtı keçib və ya giriş səhifəsi açılıb.
- `upstream_challenge`: IVAS 403/blok cavabı qaytarır; təhlükəsizlik yoxlaması keçilmir.
- `portal_stats_not_found`: statistik göstəricilərin HTML formatı dəyişib.
- `portal_connection_error`: IVAS serverinə qoşulmaq mümkün olmayıb.

Bu inteqrasiya orijinal istifadəçinin qeyd etdiyi cookie/CSRF formasına əsaslanır. Sessiyanın hələ etibarlı olduğu canlı provayderdə təsdiqlənməyib; provayder yeni giriş yoxlaması tələb edərsə, sessiyanı rəsmi üsulla yenilə.

## Lokal yoxlama

```bash
pip install -r requirements.txt
python -m unittest -v test_sms_monitor
python safe_app.py
```

Render Build: `pip install -r requirements.txt` və Start: `python safe_app.py` (Gunicorn işə düşür).
