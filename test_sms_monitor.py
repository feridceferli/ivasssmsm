"""Offline tests: do not send real API requests or use real secrets."""
import json
import os
import unittest
from unittest.mock import patch

from safe_app import app
from sms_monitor import _aggregate_response, _valid_official_endpoint


class FakeResponse:
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload, code=200):
        self.payload = payload
        self.status_code = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size=8192):
        yield json.dumps(self.payload).encode("utf-8")


class SmsMonitorTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.dict(os.environ, {
            "IVAS_PRIVATE_API_KEY": "test-only-key-please-change",
            "IVAS_OFFICIAL_API_TOKEN": "upstream-test-only",
            "IVAS_SMS_STATS_URL": "https://api.ivasms.com/api/v1/stats"
        })
        self.config.start()
        self.addCleanup(self.config.stop)
        self.client = app.test_client()

    def test_rejects_missing_key(self):
        r = self.client.get("/api/v1/sms/stats")
        self.assertEqual(r.status_code, 401)

    def test_rejects_wrong_key(self):
        r = self.client.get("/api/v1/sms/status", headers={"X-API-Key": "invalid"})
        self.assertEqual(r.status_code, 401)

    def test_successful_status(self):
        r = self.client.get("/api/v1/sms/status", headers={"X-API-Key": "test-only-key-please-change"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["success"])

    def test_statistics_only_no_messages(self):
        payload = {
            "sms_stats": {"count_sms": "7", "paid_sms": "5", "unpaid_sms": "2", "revenue": "0.25"},
            "otp_messages": [{"phone_number": "+1234567890", "otp_message": "123456"}],
        }
        with patch("sms_monitor.requests.get", return_value=FakeResponse(payload)):
            r = self.client.get("/api/v1/sms/stats", headers={"X-API-Key": "test-only-key-please-change"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["stats"]["total_sms"], 7)
        self.assertEqual(r.json["stats"]["paid_sms"], 5)
        self.assertNotIn("123456", r.get_data(as_text=True))
        self.assertNotIn("+1234567890", r.get_data(as_text=True))

    def test_unexpected_statistics_not_faked_as_zero(self):
        with patch("sms_monitor.requests.get", return_value=FakeResponse({"messages": [{"text": "test"}]})):
            r = self.client.get("/api/v1/sms/stats", headers={"X-API-Key": "test-only-key-please-change"})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json["code"], "stats_format_unrecognized")

    def test_disallow_sms_message_endpoint(self):
        self.assertFalse(_valid_official_endpoint("https://www.ivasms.com/portal/sms/received/getsms"))
        self.assertFalse(_valid_official_endpoint("https://evil.example.com/api/v1/stats"))
        self.assertTrue(_valid_official_endpoint("https://api.ivasms.com/api/v1/stats"))

    def test_private_panel_renders(self):
        r = self.client.get("/sms-dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn("SMS idarəetməsi", r.get_data(as_text=True))

    def test_legacy_cookie_route_absent(self):
        self.assertNotIn("/sms", [rule.rule for rule in app.url_map.iter_rules()])


class HtmlReply:
    def __init__(self, html, status=200):
        self.content = html.encode("utf-8")
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}


class CookieJarStub:
    def set(self, name, value, domain=None, path=None):
        pass


class PortalSessionStub:
    def __init__(self, page, stats):
        self.cookies = CookieJarStub()
        self.page = page
        self.stats = stats
        self.post_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        assert url == "https://www.ivasms.com/portal/sms/received"
        assert kwargs["allow_redirects"] is False
        return self.page

    def post(self, url, **kwargs):
        assert url == "https://www.ivasms.com/portal/sms/received/getsms"
        assert kwargs["data"]["_token"] == "csrf-test"
        assert kwargs["allow_redirects"] is False
        self.post_calls += 1
        return self.stats


class OriginalPortalTests(unittest.TestCase):
    def setUp(self):
        self.patch_env = patch.dict(os.environ, {
            "IVAS_PRIVATE_API_KEY": "test-only-key-please-change",
            "COOKIES_JSON": '{"laravel_session":"demo-session-only"}',
        })
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)
        self.client = app.test_client()
        self.headers = {"X-API-Key": "test-only-key-please-change"}

    def test_original_cookie_flow_exposes_aggregate_only(self):
        page = HtmlReply('<html><input name="_token" value="csrf-test"></html>')
        upstream = HtmlReply(
            '<div id="CountSMS">7</div><div id="PaidSMS">5</div>'
            '<div id="UnpaidSMS">2</div><div id="RevenueSMS">0.25 USD</div>'
            '<div class="item">+123456789  Code 998877</div>'
        )
        stub = PortalSessionStub(page, upstream)
        with patch("portal_summary.requests.Session", return_value=stub):
            result = self.client.get("/api/v1/sms/stats?date=09%2F10%2F2026", headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "ivas_portal_aggregates")
        self.assertEqual(result.json["stats"]["total_sms"], 7)
        self.assertEqual(result.json["stats"]["paid_sms"], 5)
        self.assertEqual(result.json["stats"]["unpaid_sms"], 2)
        self.assertEqual(result.json["stats"]["revenue"], "0.25")
        self.assertEqual(stub.post_calls, 1)
        self.assertNotIn("998877", result.get_data(as_text=True))
        self.assertNotIn("+123456789", result.get_data(as_text=True))
        self.assertNotIn("csrf-test", result.get_data(as_text=True))
        self.assertNotIn("laravel_session", result.get_data(as_text=True))

    def test_session_challenge_is_not_bypassed(self):
        stub = PortalSessionStub(HtmlReply("<html>Forbidden</html>", 403), HtmlReply(""))
        with patch("portal_summary.requests.Session", return_value=stub):
            result = self.client.get("/api/v1/sms/stats", headers=self.headers)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json["code"], "upstream_challenge")
        self.assertEqual(stub.post_calls, 0)

    def test_missing_csrf_requires_fresh_session(self):
        stub = PortalSessionStub(HtmlReply("<html>Please sign in</html>"), HtmlReply(""))
        with patch("portal_summary.requests.Session", return_value=stub):
            result = self.client.get("/api/v1/sms/stats", headers=self.headers)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json["code"], "portal_session_expired")
        self.assertEqual(stub.post_calls, 0)

    def test_bad_cookie_config_is_rejected(self):
        with patch.dict(os.environ, {"COOKIES_JSON": "{invalid"}):
            result = self.client.get("/api/v1/sms/stats", headers=self.headers)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json["code"], "invalid_cookie_json")

    def test_private_key_still_required(self):
        result = self.client.get("/api/v1/sms/stats")
        self.assertEqual(result.status_code, 401)

    def test_day_format_validation(self):
        with patch("portal_summary.requests.Session") as session:
            result = self.client.get("/api/v1/sms/stats?date=2026-10-09", headers=self.headers)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json["code"], "invalid_date")
        session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
