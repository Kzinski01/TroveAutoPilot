"""Runtime-only package, privacy defaults and diagnostics without game workers."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

import build_release
import build
import main


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.app = self.root / "application"
        self.app.mkdir()
        (self.app / "TroveAutoBot.exe").write_bytes(b"test-payload")
        build.copy_runtime_config(self.app)
        files = ["ui/out/index.html", "assets/skill-bar-reference.png",
                 f"python{sys.version_info.major}{sys.version_info.minor}.dll"]
        for name in files:
            path = self.app / "_internal" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"bundled-test-dependency")
        self.destination = self.root / "Build Final"

    def test_clean_defaults_never_carry_window_or_calibration(self):
        cfg = build_release.distribution_config()
        self.assertIsNone(cfg["selected_window"])
        self.assertIsNone(cfg["secondary"]["selected_window"])
        self.assertFalse(cfg["secondary"]["enabled"])
        self.assertFalse(any(cfg["features"].values()))
        self.assertTrue(cfg["auto_slots"]["enabled"])
        self.assertTrue(all(s["region"] is None and s["ready_score"] == 0 for s in cfg["skills"]))

    def test_package_and_zip_contain_only_allowlisted_runtime_payload(self):
        build_release.prepare_distribution(self.app, self.destination)
        archive = self.root / "Build Final.zip"
        digest = build_release.create_archive(self.destination, archive)
        self.assertEqual(len(digest), 64)
        with ZipFile(archive) as zipped:
            self.assertIsNone(zipped.testzip())
            top = {name.split("/")[1] for name in zipped.namelist()}
            self.assertEqual(top, {"TroveAutoBot.exe", "_internal", "config.json", build.RUNTIME_CONFIG})
            saved = json.loads(zipped.read("Build Final/config.json"))
            self.assertEqual(saved, build_release.distribution_config())

    def test_local_files_in_pyinstaller_output_are_rejected(self):
        (self.app / "crash.log").write_text("private")
        with self.assertRaises(ValueError):
            build_release.prepare_distribution(self.app, self.destination)
        self.assertFalse(self.destination.exists())

    def test_preexisting_destination_is_not_overwritten(self):
        self.destination.mkdir()
        private = self.destination / "existing.txt"
        private.write_text("preserve")
        with self.assertRaises(FileExistsError):
            build_release.prepare_distribution(self.app, self.destination)
        self.assertEqual(private.read_text(), "preserve")

    def test_missing_runtime_dependency_is_detected(self):
        build_release.prepare_distribution(self.app, self.destination)
        (self.destination / "_internal/ui/out/index.html").unlink()
        with self.assertRaises(ValueError):
            build_release.verify_distribution(self.destination)

    def test_missing_clr_config_is_rejected_before_distribution(self):
        (self.app / build.RUNTIME_CONFIG).unlink()
        with self.assertRaises(ValueError):
            build_release.prepare_distribution(self.app, self.destination)
        self.assertFalse(self.destination.exists())

    def test_modified_clr_config_is_rejected(self):
        build_release.prepare_distribution(self.app, self.destination)
        (self.destination / build.RUNTIME_CONFIG).write_text("<configuration />")
        with self.assertRaisesRegex(ValueError, "Configuração CLR"):
            build_release.verify_distribution(self.destination)


class DiagnosticSafetyTest(unittest.TestCase):
    def test_selftest_does_not_start_game_workers_or_claim_normal_bot_mutex(self):
        core = mock.Mock()
        fake_webview = mock.Mock()
        with mock.patch.object(sys, "argv", ["main.py", "--selftest", "--no-elevate"]), \
             mock.patch.dict(sys.modules, {"webview": fake_webview}), \
             mock.patch.object(main, "_claim_single_instance") as claim, \
             mock.patch.object(main, "_dependencies_ready", return_value=True), \
             mock.patch.object(main, "_handed_over_to_elevated") as elevate, \
             mock.patch.object(main, "_locate_ui", return_value="ui/out/index.html"), \
             mock.patch.object(main, "_Core", return_value=core), \
             mock.patch.object(main, "_open_window"), \
             mock.patch.object(main, "_selftest"), \
             mock.patch("input_sender.set_dpi_aware"), \
             mock.patch("crash_log.install"), mock.patch("crash_log.note"):
            main.main()
        core.start.assert_not_called()
        claim.assert_not_called()
        elevate.assert_not_called()
        fake_webview.start.assert_called_once()
