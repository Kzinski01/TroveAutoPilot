"""Slot detection and window isolation; never send live keyboard/mouse input."""

import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api
import auto_slots
import bot
import config
import input_sender
import targeted_input
from slot_detection import SlotDetector
from test_targeted_input import TwinWindows


REFERENCE = cv2.imread(str(Path(__file__).resolve().parents[1] / "assets/skill-bar-reference.png"))


def screen(width=800, height=600, x=150, y=540, scale=1.0):
    frame = np.zeros((height, width, 3), np.uint8)
    bar = cv2.resize(REFERENCE, None, fx=scale, fy=scale)
    frame[y:y + bar.shape[0], x:x + bar.shape[1]] = bar
    return frame


class DetectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = SlotDetector(REFERENCE)

    def test_locates_all_three_slots_across_scales(self):
        for scale in (0.65, 0.75, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 2.0):
            with self.subTest(scale=scale):
                match = self.detector.find(screen(1000, 700, 100, 570, scale))
                self.assertIsNotNone(match)
                self.assertAlmostEqual(match.x, 100 + round(10 * scale), delta=2)
                self.assertAlmostEqual(match.y, 570 + round(4 * scale), delta=2)
                regions = match.regions()
                self.assertEqual(set(regions), {"m2", "s1", "s2"})
                self.assertLess(regions["m2"][0], regions["s1"][0])
                self.assertLess(regions["s1"][0], regions["s2"][0])

    def test_blank_and_random_images_are_rejected(self):
        self.assertIsNone(self.detector.find(np.zeros((600, 800, 3), np.uint8)))
        rng = np.random.default_rng(7654)
        self.assertIsNone(self.detector.find(rng.integers(0, 256, (600, 800, 3), dtype=np.uint8)))

    def test_single_label_does_not_count_as_a_bar(self):
        frame = screen()
        frame[540:, 205:] = 0
        self.assertIsNone(self.detector.find(frame))

    def test_wrong_order_is_rejected(self):
        frame = screen()
        first = frame[540:593, 210:255].copy()
        frame[540:593, 210:255] = frame[540:593, 260:305]
        frame[540:593, 260:305] = first
        self.assertIsNone(self.detector.find(frame))

    def test_two_bars_are_ambiguous(self):
        frame = screen()
        frame[350:403, 100:463] = REFERENCE
        self.assertIsNone(self.detector.find(frame))

    def test_bar_above_hud_search_area_is_rejected(self):
        self.assertIsNone(self.detector.find(screen(y=100)))

    def test_class_icon_contents_are_not_the_identifier(self):
        frame = screen()
        for x in (160, 210, 260):
            frame[560:584, x:x + 45] = (170, 0, 40)
        self.assertIsNotNone(self.detector.find(frame))

    def test_unavailable_reference_fails_explicitly(self):
        with self.assertRaises(ValueError):
            SlotDetector(None)

    def test_local_validation_uses_previous_match(self):
        frame = screen()
        match = self.detector.find(frame)
        validated = self.detector.find(frame, match)
        self.assertEqual(match.regions(), validated.regions())

    def test_real_small_bar_is_recognized_with_cooldown_numbers(self):
        bar = cv2.imread(str(Path(__file__).parent / "fixtures/skill-bar-cooldown.png"))
        frame = np.zeros((1000, 958, 3), np.uint8)
        frame[950:999, 330:470] = bar
        match = self.detector.find(frame)
        self.assertIsNotNone(match)
        self.assertAlmostEqual(match.x, 337, delta=2)
        self.assertAlmostEqual(match.y, 958, delta=2)


class AutomaticSlotsTest(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.cfg["input_mode"] = "messages"
        self.cfg["auto_slots"]["enabled"] = True
        self.windows = TwinWindows()
        patcher = mock.patch.object(targeted_input, "windows", self.windows)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.logs = []
        self.sender = targeted_input.TargetedInput(self.cfg, self.logs.append)
        self.sender.select(self.windows.account2)
        self.engine = bot.Bot(self.cfg, log=self.logs.append, sender=self.sender)
        self.locator = self.engine.slot_locator
        self.frame = screen()
        patcher = mock.patch.object(auto_slots.vision, "grab", side_effect=lambda region: self.frame.copy())
        self.grab = patcher.start()
        self.addCleanup(patcher.stop)
        self.safety = []
        for obj, name in [(input_sender.user32, "SendInput"), (input_sender.user32, "PostMessageW"),
                          (input_sender, "move_to"), (input_sender, "key_down"), (input_sender, "mouse_down")]:
            patcher = mock.patch.object(obj, name)
            self.safety.append(patcher.start())
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for method in self.safety:
            method.assert_not_called()

    def locate(self):
        self.assertTrue(self.locator.update(force=True))

    def test_first_detection_binds_selected_window_without_fabricating_calibration(self):
        for skill in self.cfg["skills"]:
            skill.update(ready_score=0.5, cooldown_score=0.3)
        self.locate()
        for skill in self.cfg["skills"]:
            self.assertTrue(self.locator.ready_for(skill))
            self.assertEqual(skill["window_region"]["client_size"], [800, 600])
            self.assertEqual(skill["ready_score"], 0.0)
            self.assertEqual(skill["cooldown_score"], 0.0)
            self.assertIsNone(self.engine._skill_ratio(skill))

    def test_reopen_relocates_without_losing_saved_ready_score(self):
        self.locate()
        for skill in self.cfg["skills"]:
            skill["ready_score"] = 0.45
        self.locator.invalidate()
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))
        self.locate()
        self.assertTrue(all(skill["ready_score"] == 0.45 for skill in self.cfg["skills"]))

    def test_resize_blocks_old_area_then_relocates_and_preserves_attack_settings(self):
        self.locate()
        for skill in self.cfg["skills"]:
            skill.update(ready_score=0.45, cooldown_score=0.2)
        settings = [(skill["key"], skill["threshold"], skill["min_interval"]) for skill in self.cfg["skills"]]
        self.windows.region = (100, 100, 600, 400)
        self.frame = screen(600, 400, 80, 340, 0.8)
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))
        self.assertTrue(self.locator.update())  # Resizing bypasses the retry interval.
        for skill in self.cfg["skills"]:
            self.assertEqual(skill["window_region"]["client_size"], [600, 400])
            self.assertEqual(skill["ready_score"], 0.45)
        self.assertEqual(settings, [(s["key"], s["threshold"], s["min_interval"]) for s in self.cfg["skills"]])

    def test_window_move_updates_screen_coordinates(self):
        self.locate()
        previous = self.cfg["skills"][0]["region"].copy()
        self.windows.region = (300, 150, 800, 600)
        self.locate()
        self.assertEqual(self.cfg["skills"][0]["region"][:2], [previous[0] + 200, previous[1] + 50])

    def test_same_title_other_instance_cannot_supply_slots(self):
        self.windows.hit = 100
        self.assertFalse(self.locator.update(force=True))
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))

    def test_overlay_pauses_previously_located_slots(self):
        self.locate()
        self.windows.hit = 100
        self.assertFalse(self.locator.update(force=True))
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))

    def test_no_focus_is_supported_in_messages_mode(self):
        self.windows.focus = 100
        self.locate()

    def test_foreground_backend_still_requires_selected_focus(self):
        self.cfg["input_mode"] = "foreground"
        self.windows.focus = 100
        self.assertFalse(self.locator.update(force=True))

    def test_minimizing_blocks_old_detection(self):
        self.locate()
        self.windows.minimized = True
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))
        self.assertFalse(self.locator.update())
        self.assertIn("minimizada", self.locator.state()["status"])

    def test_calibration_suspension_does_not_discard_located_area(self):
        self.locate()
        self.sender.suspend(True)
        self.assertFalse(self.locator.update())
        self.assertTrue(self.locator.ready_for(self.cfg["skills"][0]))
        self.sender.suspend(False)

    def test_visibility_lost_on_second_frame_does_not_commit(self):
        count = 0
        def overlay(region):
            nonlocal count
            count += 1
            if count == 2:
                self.windows.hit = 100
            return self.frame
        self.grab.side_effect = overlay
        self.assertFalse(self.locator.update(force=True))
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))
        self.assertIn("encoberta", self.locator.state()["status"])

    def test_closed_window_cannot_reuse_old_detection(self):
        self.locate()
        self.windows.current.pop(200)
        self.assertFalse(self.locator.ready_for(self.cfg["skills"][0]))
        self.assertFalse(self.locator.update(force=True))

    def test_changed_pixels_on_confirmation_do_not_apply(self):
        self.grab.side_effect = [self.frame, np.zeros_like(self.frame)]
        self.assertFalse(self.locator.update(force=True))
        self.assertTrue(all(skill["region"] is None for skill in self.cfg["skills"]))

    def test_geometry_change_during_capture_cannot_apply_stale_coordinates(self):
        def move(region):
            self.windows.region = (200, 100, 800, 600)
            return self.frame
        self.grab.side_effect = move
        self.assertFalse(self.locator.update(force=True))
        self.assertTrue(all(skill["region"] is None for skill in self.cfg["skills"]))

    def test_target_change_during_capture_cannot_apply_previous_pixels(self):
        def change(region):
            self.sender.select(self.windows.account1)
            return self.frame
        self.grab.side_effect = change
        self.assertFalse(self.locator.update(force=True))

    def test_invalidating_during_capture_cannot_commit_old_scan(self):
        def invalidate(region):
            self.locator.invalidate()
            return self.frame
        self.grab.side_effect = invalidate
        self.assertFalse(self.locator.update(force=True))
        self.assertTrue(all(skill["region"] is None for skill in self.cfg["skills"]))

    def test_reference_failure_pauses_instead_of_guessing(self):
        with mock.patch.object(self.locator, "_get_detector", side_effect=ValueError("missing")):
            self.assertFalse(self.locator.update(force=True))
        self.assertIn("missing", self.locator.state()["status"])

    def test_manual_mode_preserves_existing_behavior(self):
        self.locator.set_enabled(False)
        self.assertFalse(self.locator.update(force=True))
        self.assertTrue(self.locator.ready_for(self.cfg["skills"][0]))
        self.grab.assert_not_called()

    def test_relocation_inside_same_window_falls_back_to_full_search(self):
        self.locate()
        self.frame = screen(x=230, y=510)
        self.locate()
        self.assertEqual(self.cfg["skills"][0]["region"][0], 344)

    def test_invalid_detection_cannot_reuse_saved_area_or_measure_ratio(self):
        self.locate()
        self.frame[:] = 0
        self.assertFalse(self.locator.update(force=True))
        with mock.patch.object(bot.vision, "skill_ratio") as ratio:
            self.assertIsNone(self.engine._skill_ratio(self.cfg["skills"][0]))
            ratio.assert_not_called()

    def test_periodic_key_configuration_is_unchanged(self):
        before = copy.deepcopy(self.cfg["secondary"])
        self.locate()
        self.assertEqual(before, self.cfg["secondary"])

    def test_api_switch_is_persisted_and_poll_exposes_locations(self):
        bridge = api.Api(self.cfg, self.engine, mock.Mock())
        with mock.patch.object(config, "save") as save:
            self.assertTrue(bridge.set_auto_slots(False))
            self.assertFalse(self.cfg["auto_slots"]["enabled"])
            save.assert_called_once()
        self.locator.set_enabled(True)
        self.locate()
        self.assertEqual(bridge.get_state()["autoSlots"]["skills"][0]["region"], self.cfg["skills"][0]["region"])


if __name__ == "__main__":
    unittest.main()
