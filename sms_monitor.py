"""Read-only, private SMS aggregate statistics via original IVAS portal session or official API.

Never serves individual phone numbers, messages, login cookies, or OTP codes.
"""
import hmac
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import requests
from flask import Blueprint, jsonify, request, send_from_directory
from portal_summary import PortalSummaryError, fetch_portal_summary

sms_bp = Blueprint("sms_monitor", __name__)
ALLOWED_HOSTS = frozenset(("ivasms.com", "www.ivasms.com", "api.ivasms.com"))
DISALLOWED_PATH_PARTS = ("received", "messages", "getsms", "otp", "number", "session", "login")
MAX_RESPONSE_BYTES = 65536


def _private_auth():
    expected = os.environ.get("IVAS_PRIVATE_API_KEY", "").strip()
    if not expected:
        return jsonify(success=False, code="private_key_not_configured",
                       message="IVAS_PRIVATE_API_KEY Render-də təyin edilməyib."), 503
    supplied = request.headers.get("X-API-Key", "").strip()
    authorization = request.headers.get("Authorization", "")
    if not supplied and authorization.startswith("Bearer "):
        supplied = authorization[7:].strip()
    if not hmac.compare_digest(supplied, expected):
        return jsonify(success=False, code="unauthorized", message="Şəxsi API açarı qəbul edilmədi."), 401
    return None


def _valid_official_endpoint(raw_url):
    try:
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and host in ALLOWED_HOSTS
                and parsed.port in (None, 443)
                and not parsed.username and not parsed.password
                and not parsed.fragment
                and not any(part in parsed.path.lower() for part in DISALLOWED_PATH_PARTS))
    except ValueError:
        return False


def _aggregate_response(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False or payload.get("status") == "error":
        return None
    wrappers = (payload, payload.get("sms_stats"), payload.get("stats"), payload.get("summary"),
                payload.get("data"), payload.get("result"))
    candidates = list(wrappers)
    for wrapper in wrappers:
        if isinstance(wrapper, dict):
            candidates.extend((wrapper.get("stats"), wrapper.get("sms_stats"), wrapper.get("summary")))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        total = _count(candidate, ("count_sms", "total_sms", "sms_count", "received_count"))
        paid = _count(candidate, ("paid_sms", "paid_count"))
        unpaid = _count(candidate, ("unpaid_sms", "unpaid_count"))
        revenue = _money(candidate, ("revenue", "total_revenue", "earnings"))
        if any(value is not None for value in (total, paid, unpaid, revenue)):
            return {"total_sms": total, "paid_sms": paid, "unpaid_sms": unpaid, "revenue": revenue}
    return None


def _count(item, names):
    for name in names:
        value = item.get(name)
        if type(value) is int and 0 <= value <= 100000000:
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]{1,9}", value.strip()):
            return int(value.strip())
    return None


def _money(item, names):
    for name in names:
        value = item.get(name)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            continue
        text = str(value).strip()
        if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,4})?", text):
            continue
        try:
            amount = Decimal(text)
            if amount.is_finite() and amount >= 0:
                return str(amount)
        except InvalidOperation:
            continue
    return None


@sms_bp.get("/sms-dashboard")
def sms_dashboard():
    return send_from_directory(str(Path(__file__).resolve().parent / "public"), "sms.html")


@sms_bp.get("/api/v1/sms/status")
def sms_status():
    error = _private_auth()
    if error is not None:
        return error
    portal_configured = bool(os.environ.get("COOKIES_JSON", "").strip())
    return jsonify(success=True, provider="IVAS SMS", monitor="read_only_aggregates",
                   source="ivas_portal_session" if portal_configured else "official_api" if os.environ.get("IVAS_SMS_STATS_URL") else "not_configured",
                   portal_session_configured=portal_configured,
                   upstream_api_configured=bool(os.environ.get("IVAS_OFFICIAL_API_TOKEN")),
                   stats_endpoint_configured=bool(os.environ.get("IVAS_SMS_STATS_URL")),
                   availability_endpoint_configured=bool(os.environ.get("IVAS_AVAILABILITY_URL")),
                   checked_at=datetime.now(timezone.utc).isoformat())


@sms_bp.get("/api/v1/sms/stats")
def sms_stats():
    error = _private_auth()
    if error is not None:
        return error
    # The user's original project uses COOKIES_JSON -> authenticated portal
    # -> CSRF form -> aggregate HTML statistics, not an official Bearer API.
    # No login bypasses and no SMS/OTP records are returned.
    if os.environ.get("COOKIES_JSON", "").strip():
        try:
            summary = fetch_portal_summary(request.args.get("date"))
            return jsonify(success=True, stats=summary["stats"], date=summary["date"],
                           checked_at=datetime.now(timezone.utc).isoformat(),
                           source=summary["source"])
        except PortalSummaryError as exc:
            status = 400 if exc.code == "invalid_date" else 502
            return jsonify(success=False, code=exc.code, message=exc.message), status

    upstream_url = os.environ.get("IVAS_SMS_STATS_URL", "").strip()
    token = os.environ.get("IVAS_OFFICIAL_API_TOKEN", "").strip()
    if not token and not upstream_url:
        return jsonify(success=False, code="portal_cookie_not_configured",
                       message="Göndərdiyin IVAS kodu üçün Render-də COOKIES_JSON sessiyası tələb olunur."), 503
    if not token or not upstream_url:
        return jsonify(success=False, code="stats_not_configured",
                       message="IVAS_SMS_STATS_URL və IVAS_OFFICIAL_API_TOKEN tələb olunur."), 503
    if not _valid_official_endpoint(upstream_url):
        return jsonify(success=False, code="invalid_stats_url",
                       message="Yalnız rəsmi IVAS HTTPS statistika endpoint-i qəbul edilir."), 400
    try:
        with requests.get(upstream_url,
                          headers={"Authorization": "Bearer " + token,
                                   "Accept": "application/json"},
                          stream=True, allow_redirects=False, timeout=8) as response:
            if response.status_code in (401, 403):
                return jsonify(success=False, code="upstream_auth_failed",
                               message="Rəsmi API girişə icazə vermədi."), 502
            if response.status_code == 429:
                return jsonify(success=False, code="upstream_rate_limited",
                               message="Rəsmi API sorğu limiti."), 429
            if response.status_code != 200:
                return jsonify(success=False, code="upstream_http_error",
                               upstream_status=response.status_code,
                               message="Rəsmi API xəta qaytardı."), 502
            if "application/json" not in response.headers.get("Content-Type", "").lower():
                return jsonify(success=False, code="upstream_non_json",
                               message="Rəsmi statistika API-si JSON qaytarmadı."), 502
            body = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    return jsonify(success=False, code="upstream_response_too_large",
                                   message="Statistika cavabı həddən böyükdür."), 502
        payload = json.loads(body)
        stats = _aggregate_response(payload)
        if stats is None:
            return jsonify(success=False, code="stats_format_unrecognized",
                           message="API-də ümumi SMS statistikası tapılmadı."), 502
        return jsonify(success=True, stats=stats,
                       checked_at=datetime.now(timezone.utc).isoformat(),
                       source="official_aggregate_api")
    except (requests.RequestException, ValueError, TypeError):
        return jsonify(success=False, code="upstream_connection_failed",
                       message="Rəsmi statistika API-sindən cavab alınmadı."), 502
