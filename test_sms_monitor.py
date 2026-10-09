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


if __name__ == "__main__":
    unittest.main()
