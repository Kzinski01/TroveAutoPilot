"""Regressions discovered in the open-source audit; no live game input."""

import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

import config
import deps
import hotkeys
import vision
from test_api import ApiTestCase


class SavedConfigurationTest(unittest.TestCase):
    def load(self, changes):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg.update(changes)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with mock.patch.object(config, "CONFIG_PATH", str(path)), \
                    mock.patch.object(config, "TEMPLATE_DIR", folder):
                return config.load()

    def test_negative_scan_delays_cannot_kill_workers(self):
        cfg = self.load({"scan_interval": -1, "dialog_interval": -500})
        self.assertEqual(cfg["scan_interval"], config.DEFAULTS["scan_interval"])
        self.assertEqual(cfg["dialog_interval"], config.DEFAULTS["dialog_interval"])

    def test_malformed_skill_identity_is_ignored(self):
        cfg = self.load({"skills": [{"id": [], "threshold": -1}]})
        self.assertEqual(cfg["skills"], config.DEFAULT_SKILLS)

    def test_bad_capture_binding_is_reset(self):
        cfg = self.load({"skills": [{"id": "m2", "window_region": {"relative": "bad"},
                                    "region": [1, 2, 32, 32], "ready_score": 0.7}]})
        self.assertIsNone(cfg["skills"][0]["region"])
        self.assertEqual(cfg["skills"][0]["ready_score"], 0)
        self.assertNotIn("window_region", cfg["skills"][0])

    def test_invalid_mouse_button_cannot_reach_win32(self):
        cfg = self.load({"autoclick": {"button": "unknown", "cps": -1}})
        self.assertEqual(cfg["autoclick"]["button"], "left")
        self.assertEqual(cfg["autoclick"]["cps"], 12)

    def test_existing_external_template_is_confined_to_local_templates(self):
        with tempfile.TemporaryDirectory() as folder:
            external = Path(folder) / "outside.png"
            external.write_bytes(b"private")
            self.assertEqual(config.resolve_template(str(external)),
                             str(Path(config.TEMPLATE_DIR) / "outside.png"))


class BridgeRegressionTest(ApiTestCase):
    def test_text_false_cannot_activate_automation(self):
        self.bot.master = False
        self.cfg["features"]["holdkey"] = False
        self.assertFalse(self.api.set_master("false"))
        self.assertFalse(self.api.set_feature("holdkey", "false"))
        self.assertFalse(self.api.set_secondary_enabled("false"))
        self.assertFalse(self.api.set_auto_slots("false"))
        self.assertFalse(self.bot.master)
        self.assertFalse(self.cfg["features"]["holdkey"])

    def test_capture_operations_never_overlap(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def first():
            calls.append("first")
            entered.set()
            self.assertTrue(release.wait(2))

        with mock.patch.object(self.api, "_SETTLE", 0):
            one = threading.Thread(target=lambda: self.api._offscreen(first))
            two = threading.Thread(target=lambda: self.api._offscreen(lambda: calls.append("second")))
            one.start()
            try:
                self.assertTrue(entered.wait(2))
                two.start()
                time.sleep(0.05)
                self.assertEqual(calls, ["first"])
            finally:
                release.set()
                one.join(2)
                if two.ident is not None:
                    two.join(2)
        self.assertEqual(calls, ["first", "second"])

    def test_duplicate_binding_cannot_replace_panic(self):
        self.cfg["hotkeys"]["skills"] = "f12"
        self.api.apply_hotkeys()
        self.bot.master = True
        self.hotkeys._bindings["f12"]()
        self.assertFalse(self.bot.master)

    def test_capture_rejects_duplicate_and_unknown_hotkeys(self):
        before = dict(self.cfg["hotkeys"])
        self.api._finish_capture("skills", "f12")
        self.assertFalse(self.api.capture_hotkey("unknown"))
        self.assertFalse(self.api.clear_hotkey("unknown"))
        self.assertEqual(self.cfg["hotkeys"], before)


class InputAndCaptureRegressionTest(unittest.TestCase):
    def test_repeated_keydown_fires_once_until_keyup(self):
        manager = hotkeys.HotkeyManager()
        fired = mock.Mock()
        manager.set_bindings({"f5": fired})
        with mock.patch.object(hotkeys.threading, "Thread") as thread:
            for _ in range(100):
                manager._on_press(hotkeys.keyboard.Key.f5)
            self.assertEqual(thread.call_count, 1)
            manager._on_release(hotkeys.keyboard.Key.f5)
            manager._on_press(hotkeys.keyboard.Key.f5)
            self.assertEqual(thread.call_count, 2)

    def test_capture_initialization_failure_completes_request_and_can_retry(self):
        failed, retried = vision._Pedido(lambda sct: "ok"), vision._Pedido(lambda sct: "ok")
        with mock.patch.object(vision, "_pedidos") as queue, \
                mock.patch.object(vision.mss, "MSS", side_effect=[OSError("capture unavailable"), object()]):
            queue.get.side_effect = [failed, retried, SystemExit]
            with self.assertRaises(SystemExit):
                vision._servir_capturas()
        self.assertTrue(failed.pronto.is_set())
        self.assertIsInstance(failed.erro, OSError)
        self.assertTrue(retried.pronto.is_set())
        self.assertEqual(retried.valor, "ok")

    def test_missing_webview_is_detected_before_main_imports_it(self):
        with mock.patch.object(deps, "is_frozen", return_value=False), \
                mock.patch.object(deps.importlib.util, "find_spec", side_effect=lambda name: None if name == "webview" else object()):
            self.assertEqual(deps.missing(), ["pywebview"])
