"""Authenticated IVAS portal adapter for aggregate statistics only.

Uses the session-cookie + CSRF login flow present in the user-supplied app.py.
It never returns individual phone numbers, SMS bodies, OTP codes or cookies.
It does not bypass login challenges or restrictions; upstream errors are surfaced.
"""
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

PORTAL = "https://www.ivasms.com"
PAGE = "/portal/sms/received"
SUMMARY = "/portal/sms/received/getsms"
MAX_COOKIE_JSON = 32000
MAX_HTML_BYTES = 2_000_000


class PortalSummaryError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(code)


def parse_env_cookies(raw):
    """Parse only user-supplied Render COOKIES_JSON; never read committed files."""
    if not raw:
        raise PortalSummaryError(
            "portal_cookie_not_configured",
            "Render Environment-də COOKIES_JSON təyin edilməyib.",
        )
    if len(raw) > MAX_COOKIE_JSON:
        raise PortalSummaryError("invalid_cookie_json", "COOKIES_JSON formatı düzgün deyil.")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        raise PortalSummaryError("invalid_cookie_json", "COOKIES_JSON düzgün JSON deyil.") from None
    cookies = {}
    if isinstance(payload, dict):
        entries = [{"name": key, "value": val} for key, val in payload.items()]
    elif isinstance(payload, list):
        entries = payload
    else:
        raise PortalSummaryError("invalid_cookie_json", "Kuki siyahısının formatı düzgün deyil.")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        domain = str(entry.get("domain", "www.ivasms.com")).lstrip(".").lower()
        if domain not in ("ivasms.com", "www.ivasms.com"):
            continue
        name = entry.get("name")
        value = entry.get("value")
        if (isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_\-]{1,120}", name)
                and isinstance(value, str) and 0 < len(value) <= 4096):
            cookies[name] = value
    if not cookies:
        raise PortalSummaryError("invalid_cookie_json", "Etibarlı IVAS sessiya kukisi tapılmadı.")
    return cookies


def _portal_response(response):
    status = response.status_code
    if status in (401, 302, 303, 307, 308):
        raise PortalSummaryError("portal_session_expired", "IVAS sessiyası etibarsızdır və ya müddəti bitib.")
    if status == 403:
        raise PortalSummaryError(
            "upstream_challenge",
            "IVAS girişi rədd etdi (HTTP 403). Saytın giriş yoxlamasını keçmək üçün cəhd edilmir.",
        )
    if status == 429:
        raise PortalSummaryError("upstream_rate_limited", "IVAS sorğu limitinə çatılıb.")
    if status != 200:
        raise PortalSummaryError("portal_http_error", "IVAS sorğusu uğursuz oldu.")
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "html" not in content_type:
        raise PortalSummaryError("unexpected_portal_content", "IVAS HTML cavabı qaytarmadı.")
    if len(response.content) > MAX_HTML_BYTES:
        raise PortalSummaryError("portal_response_too_large", "IVAS cavabı həddən artıq böyükdür.")
    return BeautifulSoup(response.content, "html.parser")


def _int_stat(soup, css_selector):
    node = soup.select_one(css_selector)
    if node is None:
        return None
    text = node.get_text(" ", strip=True).replace(",", "").replace(" ", "")
    if not re.fullmatch(r"[0-9]{1,10}", text):
        return None
    result = int(text)
    return result if result <= 100000000 else None


def _money_stat(soup, css_selector):
    node = soup.select_one(css_selector)
    if node is None:
        return None
    raw = node.get_text(" ", strip=True).replace(",", "").strip()
    text = re.sub(r"\s*(USD|US\$|\$)\s*$", "", raw, flags=re.IGNORECASE).strip()
    return text if re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,4})?", text) else None


def fetch_portal_summary(date_text=None):
    cookies = parse_env_cookies(os.getenv("COOKIES_JSON", ""))
    if date_text:
        try:
            dt = datetime.strptime(date_text, "%d/%m/%Y")
        except ValueError:
            raise PortalSummaryError("invalid_date", "Tarix DD/MM/YYYY formatında olmalıdır.") from None
        if dt.strftime("%d/%m/%Y") != date_text:
            raise PortalSummaryError("invalid_date", "Tarix DD/MM/YYYY formatında olmalıdır.")
        day = date_text
    else:
        day = datetime.now(ZoneInfo("Asia/Baku")).strftime("%d/%m/%Y")

    with requests.Session() as session:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain="www.ivasms.com", path="/")
        try:
            login = session.get(
                PORTAL + PAGE,
                headers={"Accept": "text/html"},
                timeout=9,
                allow_redirects=False,
            )
            login_soup = _portal_response(login)
            csrf_input = login_soup.select_one('input[name="_token"]')
            csrf = csrf_input.get("value") if csrf_input else None
            if not csrf:
                raise PortalSummaryError(
                    "portal_session_expired",
                    "IVAS portalında təsdiqlənmiş giriş tapılmadı. Yeni sessiya kukisi tələb olunur.",
                )
            response = session.post(
                PORTAL + SUMMARY,
                data={"from": day, "to": "", "_token": csrf},
                headers={
                    "Accept": "text/html, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": PORTAL,
                    "Referer": PORTAL + PAGE,
                },
                timeout=9,
                allow_redirects=False,
            )
            # The upstream HTML can contain sensitive rows. Parse only aggregate IDs;
            # do not save, return, print, or log the full HTML or its sensitive fields.
            summary_soup = _portal_response(response)
        except requests.RequestException:
            raise PortalSummaryError("portal_connection_error", "IVAS serverindən cavab alınmadı.") from None

    stats = {
        "total_sms": _int_stat(summary_soup, "#CountSMS"),
        "paid_sms": _int_stat(summary_soup, "#PaidSMS"),
        "unpaid_sms": _int_stat(summary_soup, "#UnpaidSMS"),
        "revenue": _money_stat(summary_soup, "#RevenueSMS"),
    }
    if all(val is None for val in stats.values()):
        raise PortalSummaryError(
            "portal_stats_not_found",
            "IVAS cavabında ümumi SMS statistikası tapılmadı; HTML strukturu dəyişmiş ola bilər.",
        )
    return {"stats": stats, "date": day, "source": "ivas_portal_aggregates"}
