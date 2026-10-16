"""Configuration boundaries and local HTTP access; no live game input."""

import copy
import http.client
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import config
import settings_validation as validation
import telemetry_server
from test_api import ApiTestCase


class SettingsSecurityTest(ApiTestCase):
    def test_skill_patch_cannot_change_identity_or_capture_binding(self):
        before = copy.deepcopy(self.cfg["skills"][0])
        self.api.update_skill("m2", {"id": "s2", "region": [1, 1, 50, 50],
                                     "auto_sampling": True, "window_region": {}, "key": "1"})
        expected = {**before, "key": "1"}
        self.assertEqual(self.cfg["skills"][0], expected)

    def test_invalid_patch_is_atomic_and_does_not_save(self):
        before = copy.deepcopy(self.cfg["skills"][0])
        self.assertFalse(self.api.update_skill("m2", {"key": "1", "threshold": float("nan")}))
        self.assertEqual(before, self.cfg["skills"][0])
        self.assertEqual(self.saves, [])

    def test_nested_invalid_number_does_not_break_existing_routine(self):
        before = copy.deepcopy(self.cfg["autoclick"])
        self.assertFalse(self.api.update_settings({"autoclick": {"cps": -20}}))
        self.assertEqual(before, self.cfg["autoclick"])

    def test_settings_patch_cannot_choose_handle_or_input_mode(self):
        before = copy.deepcopy(self.cfg)
        self.api.update_settings({"selected_window": {"hwnd": 100}, "input_mode": "messages"})
        self.assertEqual(before, self.cfg)

    def test_dialog_patch_cannot_supply_external_template(self):
        self.api.update_dialog("claim", {"template": "../../other.png", "action": "key"})
        self.assertEqual(self.cfg["claim"]["template"], "")
        self.assertEqual(self.cfg["claim"]["action"], "key")

    def test_invalid_calibration_state_is_rejected(self):
        with mock.patch("calibration.sample_scores") as sample:
            self.assertFalse(self.api.calibrate_skill("m2", "unknown"))
            sample.assert_not_called()

    def test_logs_without_consumer_remain_bounded(self):
        for index in range(5000):
            self.api.log(str(index))
        self.assertLessEqual(len(self.api._pending_logs), 400)
        self.assertTrue(self.api._drain_logs()[-1].endswith("4999"))


class ValidationTest(unittest.TestCase):
    def test_non_finite_boolean_and_wrong_type_numbers_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, True, "20", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validation.settings({"autoclick": {"cps": value}})

    def test_invalid_patch_types_are_rejected(self):
        for value in (None, [], "settings"):
            with self.assertRaises(ValueError):
                validation.settings(value)

    def test_valid_values_and_key_aliases_keep_working(self):
        self.assertEqual(validation.patch({"key": " MOUSE_RIGHT ", "threshold": 0.98}, validation.SKILL),
                         {"key": "mouse_right", "threshold": 0.98})


class ConfigurationSecurityTest(unittest.TestCase):
    def test_malformed_root_or_section_does_not_crash_load(self):
        for raw in ([], None, {"features": None, "secondary": [], "skills": "invalid"}):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "config.json"
                path.write_text(json.dumps(raw))
                with mock.patch.object(config, "CONFIG_PATH", str(path)), mock.patch.object(config, "TEMPLATE_DIR", folder):
                    cfg = config.load()
                self.assertIsInstance(cfg["features"], dict)
                self.assertEqual(len(cfg["skills"]), 3)

    def test_non_finite_saved_numbers_use_valid_defaults(self):
        result = config._merge(config.DEFAULTS, {"scan_interval": float("nan"), "potion": {"interval": "bad"}})
        self.assertEqual(result["scan_interval"], config.DEFAULTS["scan_interval"])
        self.assertEqual(result["potion"]["interval"], config.DEFAULTS["potion"]["interval"])

    def test_relative_template_cannot_escape_templates_directory(self):
        self.assertEqual(config.resolve_template("../config.json"), "")


class LocalServerSecurityTest(unittest.TestCase):
    def setUp(self):
        self.provider = mock.Mock(return_value={"ok": True})
        self.url, self.token, self.server = telemetry_server.start({"state": self.provider})
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.client = http.client.HTTPConnection(self.url.removeprefix("http://"), timeout=5)
        self.addCleanup(self.client.close)

    def get(self, token=None, headers=None):
        token = self.token if token is None else token
        self.client.request("GET", f"/state?t={token}", headers=headers or {})
        response = self.client.getresponse()
        body = response.read().decode()
        return response.status, dict(response.getheaders()), body

    def test_valid_local_ui_origin_is_allowed_and_echoed(self):
        origin = "http://127.0.0.1:12345"
        status, headers, body = self.get(headers={"Origin": origin})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(json.loads(body), {"ok": True})

    def test_foreign_origin_is_rejected_even_with_token(self):
        status, _, _ = self.get(headers={"Origin": "https://example.com"})
        self.assertEqual(status, 403)
        self.provider.assert_not_called()

    def test_dns_rebinding_host_is_rejected(self):
        status, _, _ = self.get(headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        self.provider.assert_not_called()

    def test_duplicate_or_wrong_token_cannot_invoke_provider(self):
        for token in ("wrong", f"{self.token}&t={self.token}", "%C3%A1"):
            self.assertEqual(self.get(token)[0], 403)
        self.provider.assert_not_called()

    def test_internal_exception_details_are_not_sent_to_client(self):
        self.provider.side_effect = ValueError("secret-private-path")
        with self.assertLogs("telemetry_server", "ERROR"):
            status, _, body = self.get()
        self.assertEqual(status, 500)
        self.assertNotIn("secret-private-path", body)

    def test_wrong_method_cannot_invoke_provider(self):
        self.client.request("POST", f"/state?t={self.token}")
        response = self.client.getresponse()
        response.read()
        self.assertEqual(response.status, 501)
        self.provider.assert_not_called()
