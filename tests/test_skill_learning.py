"""Temporal cooldown regressions using generated pixels; no live game input."""

import copy
from pathlib import Path
import threading
import unittest
from unittest import mock

import numpy as np
import cv2

from skill_learning import SkillMonitor, VisualCycle
from slot_detection import SlotDetector


ICON = np.random.default_rng(42).integers(55, 230, (32, 32, 3), dtype=np.uint8)
DARK = (ICON * 0.20).astype(np.uint8)
TARGET = {"hwnd": 1, "pid": 2, "process_created": "first"}
SKILL = {"id": "s1", "key": "1", "window_region": {"relative": [0, 0, 32, 32]}}


class VisualCycleTest(unittest.TestCase):
    def setUp(self):
        self.model = VisualCycle()
        self.now = 10.0

    def feed(self, frame, count=6):
        value = None
        for _ in range(count):
            self.now += 0.11
            value = self.model.observe(frame, self.now)
        return value

    def learn(self):
        self.feed(ICON)
        self.feed(DARK)
        self.feed(ICON)
        self.assertTrue(self.model.calibrated)
        self.assertTrue(self.model.ready)

    def test_static_ready_or_dark_image_cannot_fabricate_calibration(self):
        for image in (ICON, DARK):
            self.model = VisualCycle()
            self.assertIsNone(self.feed(image, 60))
            self.assertFalse(self.model.ready)
            self.assertFalse(self.model.calibrated)

    def test_learning_requires_a_complete_visual_cycle(self):
        self.learn()
        self.assertAlmostEqual(self.feed(ICON), 1.0)

    def test_initial_attempt_does_not_claim_calibration(self):
        self.feed(ICON)
        self.assertTrue(self.model.can_attempt(self.now))
        self.assertFalse(self.model.ready)
        self.assertFalse(self.model.calibrated)

    def test_unanswered_attempt_waits_two_seconds_and_fresh_stable_samples(self):
        self.feed(ICON)
        self.model.sent(self.now)
        self.feed(ICON, 12)
        self.assertFalse(self.model.can_attempt(self.now))
        self.assertIn("Sem resposta visual", self.model.message())
        self.feed(ICON, 8)
        self.assertTrue(self.model.can_attempt(self.now))
        self.assertFalse(self.model.can_attempt(self.now + 1))
        self.assertFalse(self.model.ready)

    def test_visible_cooldown_blocks_learning_attempts(self):
        self.feed(ICON)
        self.model.sent(self.now)
        self.feed(DARK, 30)
        self.assertFalse(self.model.can_attempt(self.now))

    def test_real_numeric_overlay_can_teach_without_large_brightness_drop(self):
        root = Path(__file__).resolve().parents[1]
        reference = cv2.imread(str(root / "assets/skill-bar-reference.png"))
        cooldown = cv2.imread(str(root / "tests/fixtures/skill-bar-cooldown.png"))
        detector = SlotDetector(reference)
        frames = []
        for bar in (reference, cooldown):
            frame = np.zeros((500, 800, 3), dtype=np.uint8)
            frame[400:400 + bar.shape[0], 100:100 + bar.shape[1]] = bar
            match = detector.find(frame)
            self.assertIsNotNone(match)
            frames.append({name: frame[y:y+h, x:x+w].copy()
                           for name, (x, y, w, h) in match.regions().items()})
        for name in ("m2", "s1", "s2"):
            with self.subTest(skill=name):
                self.model = VisualCycle()
                self.feed(frames[0][name])
                self.model.sent(self.now)
                self.feed(frames[1][name], 25)
                self.assertTrue(self.model.low_seen)
                self.assertFalse(self.model.can_attempt(self.now))
                self.feed(frames[0][name])
                self.assertTrue(self.model.ready)

    def test_starting_in_cooldown_does_not_learn_dark_as_ready(self):
        self.feed(DARK)
        self.feed(ICON)
        self.assertFalse(self.model.calibrated)
        self.feed(DARK)
        self.feed(ICON)
        self.assertTrue(self.model.ready)

    def test_brightness_pulses_do_not_count_as_a_cooldown_cycle(self):
        for _ in range(20):
            self.feed(ICON, 4)
            self.feed((ICON * 0.91).astype(np.uint8), 4)
        self.assertFalse(self.model.calibrated)

    def test_potion_can_end_the_next_cooldown_earlier(self):
        self.learn()
        self.model.sent(self.now)
        self.feed(DARK, 35)
        self.feed(ICON)
        previous = self.model.last_cooldown
        self.model.sent(self.now)
        self.feed(DARK, 2)
        self.feed(ICON, 4)
        self.assertTrue(self.model.ready)
        self.assertLess(self.model.last_cooldown, previous)

    def test_elapsed_previous_cooldown_never_arms_a_dark_icon(self):
        self.learn()
        self.model.sent(self.now)
        self.feed(DARK, 150)
        self.assertFalse(self.model.ready)

    def test_flash_during_cooldown_does_not_arm_the_skill(self):
        self.learn()
        self.model.sent(self.now)
        self.feed(DARK)
        self.feed(ICON, 1)
        self.assertFalse(self.model.ready)
        self.feed(DARK)
        self.assertFalse(self.model.ready)

    def test_brightness_of_partial_return_is_insufficient(self):
        self.learn()
        self.feed(DARK)
        self.feed((ICON * 0.80).astype(np.uint8), 12)
        self.assertFalse(self.model.ready)

    def test_unanswered_command_cannot_report_ready(self):
        self.learn()
        self.model.sent(self.now)
        self.feed(ICON, 100)
        self.assertFalse(self.model.ready)
        self.assertEqual(self.model.status, "confirming")
        self.feed(DARK)
        self.feed(ICON)
        self.assertTrue(self.model.ready)

    def test_covered_intervals_cannot_complete_initial_learning(self):
        self.feed(ICON)
        self.feed(DARK)
        self.model.pause()
        self.feed(ICON)
        self.assertFalse(self.model.calibrated)

    def test_brief_label_detection_failure_does_not_erase_observed_cycle(self):
        self.feed(ICON)
        self.feed(DARK)
        self.model.pause(preserve_cycle=True)
        self.assertFalse(self.model.ready)
        self.feed(ICON)
        self.assertTrue(self.model.calibrated)

    def test_long_label_detection_failure_discards_incomplete_cycle(self):
        self.feed(ICON)
        self.feed(DARK)
        self.model.pause(preserve_cycle=True)
        self.now += 2
        self.feed(ICON)
        self.assertFalse(self.model.calibrated)

    def test_stale_sample_gap_requires_fresh_frames(self):
        self.learn()
        self.now += 5
        self.feed(ICON, 1)
        self.assertFalse(self.model.ready)
        self.feed(ICON, 4)
        self.assertTrue(self.model.ready)

    def test_changed_class_icon_requires_learning_again(self):
        self.learn()
        changed = np.flip(ICON, axis=1).copy()
        self.feed(changed, 20)
        self.assertFalse(self.model.calibrated)
        self.assertFalse(self.model.ready)

    def test_long_cooldown_cannot_reduce_the_ready_baseline(self):
        self.learn()
        baseline = self.model.baseline
        self.feed(DARK, 120)
        self.assertEqual(baseline, self.model.baseline)


class SkillMonitorTest(unittest.TestCase):
    def setUp(self):
        self.monitor = SkillMonitor(threading.RLock())
        self.skill = copy.deepcopy(SKILL)
        self.now = 10

    def feed(self, image, target=TARGET):
        for _ in range(6):
            self.now += 0.11
            with mock.patch("skill_learning.time.monotonic", return_value=self.now):
                self.monitor.observe(self.skill, target, image)

    def learn(self):
        for image in (ICON, DARK, ICON):
            self.feed(image)
        self.assertTrue(self.monitor.ready(self.skill, TARGET))

    def test_other_window_cannot_reuse_a_learned_cycle(self):
        self.learn()
        other = {**TARGET, "pid": 99}
        self.assertFalse(self.monitor.ready(self.skill, other))
        self.feed(ICON, target=other)
        self.assertFalse(self.monitor.ready(self.skill, other))

    def test_attempt_cannot_reuse_another_window_key_or_binding(self):
        self.feed(ICON)
        with mock.patch("skill_learning.time.monotonic", return_value=self.now):
            self.assertTrue(self.monitor.can_attempt(self.skill, TARGET))
            self.assertFalse(self.monitor.can_attempt(self.skill, {**TARGET, "pid": 9}))
            for changes in ({"key": "2"}, {"window_region": {"relative": [1, 0, 32, 32]}}):
                self.assertFalse(self.monitor.can_attempt({**self.skill, **changes}, TARGET))

    def test_changed_binding_or_key_invalidates_a_ready_result(self):
        self.learn()
        self.skill["key"] = "2"
        self.assertFalse(self.monitor.ready(self.skill, TARGET))
        self.feed(ICON)
        self.assertFalse(self.monitor.ready(self.skill, TARGET))

    def test_pause_blocks_until_fresh_visible_samples(self):
        self.learn()
        self.monitor.pause(self.skill, "ícone encoberto")
        self.assertFalse(self.monitor.ready(self.skill, TARGET))
        self.assertEqual(self.monitor.state()["s1"]["status"], "blocked")
        self.feed(ICON)
        self.assertTrue(self.monitor.ready(self.skill, TARGET))

    def test_blank_icon_does_not_teach_or_arm(self):
        self.learn()
        self.feed(np.zeros_like(ICON))
        self.assertFalse(self.monitor.ready(self.skill, TARGET))

    def test_snapshots_cannot_mutate_learning_state(self):
        self.learn()
        self.monitor.state()["s1"]["ready"] = False
        self.assertTrue(self.monitor.ready(self.skill, TARGET))

    def test_reset_removes_previous_session_learning(self):
        self.learn()
        self.monitor.reset()
        self.assertEqual(self.monitor.state(), {})
        self.assertFalse(self.monitor.ready(self.skill, TARGET))


if __name__ == "__main__":
    unittest.main()
