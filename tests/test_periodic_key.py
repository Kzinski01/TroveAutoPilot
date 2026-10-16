"""Two real input sessions with mocked Windows transport; no live input."""

import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api
import bot
import config
import input_sender
import periodic_key
import targeted_input
from test_targeted_input import TwinWindows


class PeriodicKeyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.cfg["input_mode"] = "messages"
        self.windows = TwinWindows()
        patches = [mock.patch.object(targeted_input, "windows", self.windows),
                   mock.patch.object(targeted_input.time, "sleep")]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.global_calls = []
        for name in ("key_down", "key_up", "mouse_down", "mouse_up", "move_to"):
            patcher = mock.patch.object(input_sender, name, return_value=True)
            self.global_calls.append(patcher.start())
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(input_sender.user32, "SendInput")
        self.sendinput = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(input_sender.user32, "PostMessageW", return_value=True)
        self.post = patcher.start()
        self.addCleanup(patcher.stop)
        self.engine = bot.Bot(self.cfg)
        self.addCleanup(self.engine.shutdown)
        self.logs = []
        self.engine.set_logger(self.logs.append)
        self.engine.input.select(self.windows.account2)  # Jogo 1: attack process
        self.periodic = self.engine.secondary
        self.assertTrue(self.periodic.select(self.windows.account1))  # Jogo 2: E
        self.bridge = api.Api(self.cfg, self.engine, mock.Mock())

    def enable(self, now=100):
        with mock.patch.object(periodic_key.time, "monotonic", return_value=now):
            self.assertTrue(self.periodic.set_enabled(True))

    def assert_no_global(self):
        self.sendinput.assert_not_called()
        for call in self.global_calls:
            call.assert_not_called()

    def test_default_is_e_every_twenty_seconds(self):
        self.assertEqual(self.periodic.cfg["key"], "e")
        self.assertEqual(self.periodic.cfg["interval"], 20)
        self.assertFalse(self.periodic.cfg["enabled"])

    def test_first_send_waits_full_interval_and_repeats(self):
        self.enable()
        self.assertFalse(self.periodic._tick(119.99))
        self.assertTrue(self.periodic._tick(120))
        self.assertFalse(self.periodic._tick(139.99))
        self.assertTrue(self.periodic._tick(140))
        self.assertEqual([call.args[0] for call in self.post.call_args_list], [100] * 4)
        self.assertEqual([call.args[2] for call in self.post.call_args_list], [0x45] * 4)
        self.assert_no_global()

    def test_two_routines_send_different_keys_to_different_processes(self):
        self.enable()
        self.assertTrue(self.engine.input.tap("1", hold=0))
        self.assertTrue(self.periodic._tick(120))
        self.assertEqual([(call.args[0], call.args[2]) for call in self.post.call_args_list],
                         [(200, 0x31), (200, 0x31), (100, 0x45), (100, 0x45)])
        self.assert_no_global()

    def test_secondary_does_not_share_pressed_keys_with_primary(self):
        self.engine.input.key_down("e")
        self.enable()
        self.assertTrue(self.periodic._tick(120))
        self.assertIn(("key", "e"), self.engine.input._pressed)
        self.assertEqual(self.periodic.input._pressed, {})
        self.engine.input.key_up("e")
        self.assert_no_global()

    def test_e_continues_with_primary_master_off(self):
        self.enable()
        self.engine.set_master(False)
        self.assertTrue(self.periodic._tick(120))
        self.assert_no_global()

    def test_disabled_secondary_sends_nothing(self):
        self.assertFalse(self.periodic._tick(999))
        self.post.assert_not_called()

    def test_enabling_without_window_is_rejected(self):
        sender = periodic_key.PeriodicKey(copy.deepcopy(config.SECONDARY_DEFAULTS), self.engine.input)
        self.assertFalse(sender.set_enabled(True))
        self.assertFalse(sender._tick(999))
        self.post.assert_not_called()

    def test_same_primary_process_cannot_be_selected(self):
        self.assertFalse(self.periodic.select(self.windows.account2))
        self.assertEqual(self.periodic.selected()["hwnd"], 100)

    def test_different_hwnd_in_same_process_is_also_rejected(self):
        candidate = {**self.windows.account1, "pid": 20}
        self.assertFalse(self.periodic.select(candidate))

    def test_primary_selection_cannot_steal_secondary_process(self):
        with mock.patch.object(self.bridge, "list_windows", return_value=[self.windows.account1]):
            self.assertFalse(self.bridge.select_window(self.windows.account1))
        self.assertEqual(self.engine.input.selected()["hwnd"], 200)

    def test_closed_secondary_is_never_replaced_with_primary(self):
        self.enable()
        del self.windows.current[100]
        self.assertFalse(self.periodic._tick(120))
        self.post.assert_not_called()
        self.assertEqual(self.periodic.selected()["hwnd"], 100)
        self.assert_no_global()

    def test_reused_handle_is_blocked(self):
        self.enable()
        self.windows.current[100] = {**self.windows.account1, "pid": 99}
        self.assertFalse(self.periodic._tick(120))
        self.post.assert_not_called()

    def test_minimized_target_pauses_without_catchup_burst(self):
        self.enable()
        self.windows.minimized = True
        self.assertFalse(self.periodic._tick(120))
        self.windows.minimized = False
        self.assertTrue(self.periodic._tick(500))
        self.assertFalse(self.periodic._tick(500))
        self.assertEqual(self.post.call_count, 2)

    def test_failed_postmessage_never_uses_global_fallback(self):
        self.enable()
        self.post.return_value = False
        self.assertFalse(self.periodic._tick(120))
        self.assert_no_global()

    def test_interval_update_restarts_countdown(self):
        self.enable()
        with mock.patch.object(periodic_key.time, "monotonic", return_value=110):
            self.assertTrue(self.periodic.update({"interval": 5}))
        self.assertFalse(self.periodic._tick(114.99))
        self.assertTrue(self.periodic._tick(115))
        self.assertFalse(self.periodic._tick(119.99))
        self.assertTrue(self.periodic._tick(120))

    def test_key_is_configurable_without_touching_primary(self):
        self.assertTrue(self.periodic.update({"key": " q "}))
        self.enable()
        self.periodic._tick(120)
        self.assertEqual(self.post.call_args_list[0].args[2], 0x51)
        self.assertEqual(self.cfg["potion"]["key"], "q")
        self.assertEqual(self.cfg["skills"][1]["key"], "1")
        self.assert_no_global()

    def test_invalid_interval_does_not_change_settings(self):
        for value in (0, -1, "bad", float("nan"), float("inf"), 86401):
            self.assertFalse(self.periodic.update({"interval": value}))
        self.assertEqual(self.periodic.cfg["interval"], 20)

    def test_invalid_key_is_rejected(self):
        self.assertFalse(self.periodic.update({"key": "not-a-key"}))
        self.assertEqual(self.periodic.cfg["key"], "e")

    def test_disabled_and_reenabled_timer_starts_fresh(self):
        self.enable()
        self.periodic.set_enabled(False)
        self.assertFalse(self.periodic._tick(120))
        self.enable(now=150)
        self.assertFalse(self.periodic._tick(169))
        self.assertTrue(self.periodic._tick(170))

    def test_panic_stops_both_roles(self):
        self.enable()
        self.engine.set_master(True)
        self.engine.panic()
        self.assertFalse(self.engine.master)
        self.assertFalse(self.periodic.cfg["enabled"])
        self.assertFalse(self.periodic._tick(120))
        self.post.assert_not_called()

    def test_shutdown_stops_secondary_worker(self):
        # Real worker needs a deadline relative to the real monotonic clock.
        self.assertTrue(self.periodic.set_enabled(True))
        self.engine.start()
        self.assertTrue(self.periodic._thread.is_alive())
        self.engine.shutdown()
        self.assertIsNone(self.periodic._thread)
        self.assertFalse(self.periodic._tick(999))
        self.post.assert_not_called()

    def test_saved_enabled_and_foreground_mode_are_not_automatically_armed(self):
        saved = {**config.SECONDARY_DEFAULTS, "enabled": True, "input_mode": "foreground",
                 "selected_window": self.windows.account1}
        routine = periodic_key.PeriodicKey(saved, self.engine.input)
        self.assertFalse(routine.cfg["enabled"])
        self.assertEqual(routine.cfg["input_mode"], "messages")
        self.assertIsNone(routine.selected())

    def test_state_has_live_countdown(self):
        self.enable()
        with mock.patch.object(periodic_key.time, "monotonic", return_value=105):
            state = self.periodic.state()
        self.assertEqual(state["remaining"], 15)
        self.assertEqual(state["selectedWindow"]["hwnd"], 100)

    def test_api_telemetry_contains_secondary_status(self):
        self.assertEqual(self.bridge.get_state()["secondary"]["key"], "e")
        self.assertEqual(self.bridge.poll()["secondary"]["selectedWindow"]["hwnd"], 100)

    def test_api_update_saves_only_secondary_settings(self):
        with mock.patch.object(config, "save") as save:
            self.assertTrue(self.bridge.update_secondary({"interval": 3}))
        self.assertEqual(self.cfg["secondary"]["interval"], 3)
        self.assertEqual(self.cfg["potion"]["interval"], 10)
        save.assert_called_once()

    def test_api_rejects_stale_secondary_window_row(self):
        stale = {**self.windows.account1, "process_created": "old"}
        with mock.patch.object(self.bridge, "list_windows", return_value=[self.windows.account1]):
            self.assertFalse(self.bridge.select_secondary_window(stale))

    def test_selecting_second_window_does_not_stop_primary_attack(self):
        self.engine.master = True
        with mock.patch.object(self.bridge, "list_windows", return_value=[self.windows.account1]), mock.patch.object(config, "save"):
            self.assertTrue(self.bridge.select_secondary_window(self.windows.account1))
        self.assertTrue(self.engine.master)


if __name__ == "__main__":
    unittest.main()
