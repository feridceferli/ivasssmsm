"""Independent, safe IVAS SMS dashboard (no messages, numbers or OTP exposure)."""
import os
import ipaddress
from urllib.parse import urlparse
import requests
import hmac
from datetime import datetime, timezone
from flask import Flask, jsonify, Response, request
from sms_monitor import sms_bp

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.register_blueprint(sms_bp)

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/api/status")
def status():
    return jsonify(
        online=True,
        separate=True,
        provider="IVAS SMS",
        official_api_configured=bool(os.environ.get("IVAS_OFFICIAL_API_TOKEN")),
        availability_endpoint_configured=bool(os.environ.get("IVAS_AVAILABILITY_URL")),
        sms_content_enabled=False,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )

@app.get("/api/availability")
def availability():
    """Only country/range aggregates from an explicitly configured official JSON API."""
    token = os.environ.get("IVAS_OFFICIAL_API_TOKEN", "").strip()
    url = os.environ.get("IVAS_AVAILABILITY_URL", "").strip()
    if not token or not url:
        return jsonify(success=False, code="not_configured",
                       message="Rəsmi IVAS mövcudluq API ünvanı və açarı təyin edilməyib.", ranges=[]), 503
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or host not in ("ivasms.com", "www.ivasms.com", "api.ivasms.com") or parsed.port not in (None, 443):
        return jsonify(success=False, code="invalid_endpoint",
                       message="Yalnız rəsmi IVAS HTTPS API ünvanı qəbul edilir.", ranges=[]), 400
    try:
        response = requests.get(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                                timeout=8, allow_redirects=False)
        if response.status_code in (401, 403):
            return jsonify(success=False, code="authentication_failed",
                           message="API girişi rədd edildi.", ranges=[]), 502
        if response.status_code == 429:
            return jsonify(success=False, code="rate_limited", message="API sorğu limiti.", ranges=[]), 429
        if response.status_code != 200:
            return jsonify(success=False, code="upstream_error",
                           message="API xəta statusu qaytardı.", ranges=[]), 502
        if "application/json" not in response.headers.get("Content-Type", ""):
            return jsonify(success=False, code="non_json", message="API JSON qaytarmadı.", ranges=[]), 502
        payload = response.json()
        candidates = [payload, payload.get("ranges") if isinstance(payload, dict) else None,
                      payload.get("data") if isinstance(payload, dict) else None]
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            candidates.append(payload["data"].get("ranges"))
        items = next((v for v in candidates if isinstance(v, list)), None)
        if items is None:
            return jsonify(success=False, code="unexpected_response",
                           message="Diapazon formatı tanınmadı.", ranges=[]), 502
        ranges = []
        for item in items[:500]:
            if not isinstance(item, dict):
                continue
            # Do not expose phone numbers or arbitrary upstream records.
            country = str(item.get("country_name") or item.get("country") or "").strip()[:80]
            service = str(item.get("service_name") or item.get("service") or "").strip()[:80]
            count = item.get("available_count")
            count = count if type(count) is int and 0 <= count <= 10000000 else None
            if country or service:
                ranges.append({"country": country, "service": service, "available_count": count})
        return jsonify(success=True, ranges=ranges, count=len(ranges))
    except (requests.RequestException, ValueError):
        return jsonify(success=False, code="connection_error",
                       message="Rəsmi API-dən etibarlı cavab alınmadı.", ranges=[]), 502

def authorize_private_api():
    """Use a separate API key, never browser cookies or upstream credentials."""
    expected = os.environ.get("IVAS_PRIVATE_API_KEY", "").strip()
    if not expected:
        return jsonify(success=False, error="private_api_not_configured"), 503
    supplied = request.headers.get("X-API-Key", "").strip()
    authorization = request.headers.get("Authorization", "")
    if not supplied and authorization.startswith("Bearer "):
        supplied = authorization[7:].strip()
    if not hmac.compare_digest(supplied, expected):
        return jsonify(success=False, error="unauthorized"), 401
    return None


@app.get("/api/v1/status")
def private_status():
    failure = authorize_private_api()
    if failure is not None:
        return failure
    return jsonify(success=True, provider="IVAS SMS", api_version="v1",
                   online=True, official_api_configured=bool(os.environ.get("IVAS_OFFICIAL_API_TOKEN")),
                   availability_endpoint_configured=bool(os.environ.get("IVAS_AVAILABILITY_URL")),
                   checked_at=datetime.now(timezone.utc).isoformat())


@app.get("/api/v1/ranges")
def private_ranges():
    failure = authorize_private_api()
    if failure is not None:
        return failure
    return availability()


@app.get("/api/v1")
def private_api_docs():
    return jsonify(name="IVAS private API", version="v1",
                   auth="X-API-Key header or Authorization: Bearer <private-key>",
                   routes={"GET /api/v1/status": "Status metadata (key required)",
                           "GET /api/v1/ranges": "Country/service availability metadata (key required)",
                           "GET /api/v1/sms/status": "Official SMS stats integration status (key required)",
                           "GET /api/v1/sms/stats": "Aggregate SMS counts only (key required)"},
                   note="Does not expose individual phone numbers, SMS messages, OTPs or cookies.")


@app.get("/")
def home():
    return Response("""<!DOCTYPE html>
<html lang="az"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>IVAS SMS — Veb panel</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#0a1220;color:#ecf3ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#17365c,#0a1220 65%);min-height:100vh}
main{max-width:950px;margin:0 auto;padding:34px 16px}.brand{display:flex;align-items:center;gap:12px;font-weight:800}
.logo{background:#216ef0;padding:13px;border-radius:14px}h1{font-size:clamp(25px,5vw,38px);margin-top:30px}
p{color:#b3c4da;line-height:1.65}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.card{background:#13223a;border:1px solid #2b4568;border-radius:18px;padding:23px}.card h2{font-size:16px}
strong{font-size:22px;display:block;padding-top:8px}.note{margin:18px 0;padding:17px;border:1px solid #4f6381;background:#182f4c;border-radius:12px}
button{background:#397aff;color:white;border:0;padding:12px 20px;border-radius:10px;font-weight:bold;cursor:pointer}
@media(max-width:580px){.grid{grid-template-columns:1fr}}</style></head><body>
<main><div class="brand"><div class="logo">📡</div><div>IVAS SMS<small style="display:block;color:#93accb;font-weight:normal">Ayrıca veb idarəetmə paneli</small></div></div>
<h1>İdarə paneli</h1><p><a href="/sms-dashboard" style="display:inline-block;background:#2870ee;color:white;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:bold">📨 SMS İDARƏETMƏSİ →</a></p><p><a href="/api/v1" style="color:#94bdff">🔗 Şəxsi API sənədləri</a></p><p>Bu sayt Telegram botundan və əvvəlki LAMIX layihəsindən ayrıdır.</p>
<div class="grid"><section class="card"><h2>🌐 Server</h2><strong id="server">Yoxlanılır…</strong></section>
<section class="card"><h2>🔐 Rəsmi API konfiqurasiyası</h2><strong id="api">Yoxlanılır…</strong></section></div>
<div class="note">Təhlükəsizlik səbəbindən bu panel SMS mətnlərini, OTP kodlarını və üçüncü tərəf sessiya kukilərini göstərmir. Rəsmi API dokumentasiyası olmadan nömrə mövcudluğu barədə məlumat uydurulmur.</div>
<section class="card" style="margin-top:20px"><h2>🌍 Mövcud ölkə və xidmətlər</h2><p id="availabilityStatus">API yoxlanılır…</p><div id="availabilityList"></div></section><button id="refresh" style="margin-top:20px">Yenilə</button><p id="message" role="status"></p></main>
<script>async function refresh(){document.getElementById('message').textContent='Yoxlanılır…';try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error('Server cavab vermir');const d=await r.json();document.getElementById('server').textContent=d.online?'✅ Aktiv':'⚠️ Bağlı';document.getElementById('api').textContent=d.official_api_configured?'Açar mövcuddur':'Rəsmi API açarı yoxdur';document.getElementById('message').textContent='Status yeniləndi.';await showAvailability()}catch(e){document.getElementById('server').textContent='Xəta';document.getElementById('message').textContent='Bağlantı alınmadı.'}}async function showAvailability(){const state=document.getElementById('availabilityStatus'),list=document.getElementById('availabilityList');list.replaceChildren();try{const r=await fetch('/api/availability',{cache:'no-store'}),d=await r.json();if(!r.ok||!d.success){state.textContent=d.message||'Məlumat alınmadı';return}state.textContent=d.ranges.length?d.ranges.length+' xidmət/ölkə qeydi tapıldı.':'API boş mövcudluq siyahısı qaytardı.';for(const x of d.ranges){const row=document.createElement('p');row.textContent=(x.country||'Ölkə göstərilməyib')+' — '+(x.service||'Xidmət göstərilməyib')+(x.available_count===null?'':' · Mövcud: '+x.available_count);list.appendChild(row)}}catch{state.textContent='Mövcudluq yoxlanışı uğursuz oldu.'}}document.getElementById('refresh').addEventListener('click',refresh);refresh()</script>
</body></html>""", mimetype="text/html")

if __name__ == "__main__":
    # Render start command is python safe_app.py; hand off to production WSGI.
    os.execvp("gunicorn", ["gunicorn", "--bind", "0.0.0.0:" + os.environ.get("PORT", "10000"),
                           "--workers", "2", "--threads", "2", "--timeout", "40", "safe_app:app"])
