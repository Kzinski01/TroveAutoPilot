"""Safety tests: simulated twin windows, never inject into the live desktop."""

import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api
import bot
import config
import game_windows
import input_sender
import targeted_input


class TwinWindows:
    def __init__(self):
        self.account1 = {"hwnd": 100, "pid": 10, "title": "Trove",
                         "process_created": "1000", "exe": "C:/Game/Trove_x64.exe"}
        self.account2 = {"hwnd": 200, "pid": 20, "title": "Trove",
                         "process_created": "2000", "exe": "C:/Game/Trove_x64.exe"}
        self.current = {100: self.account1, 200: self.account2}
        self.focus = 200
        self.region = (100, 100, 800, 600)
        self.hit = 200
        self.minimized = False
        self.user32 = mock.Mock()
        self.user32.IsIconic.side_effect = lambda hwnd: self.minimized

    def window_info(self, hwnd):
        return self.current.get(hwnd)

    def foreground_hwnd(self):
        return self.focus

    def client_region(self, hwnd):
        return self.region

    def point_belongs(self, hwnd, x, y):
        return self.hit == hwnd

    same_identity = staticmethod(game_windows.same_identity)
    contains = staticmethod(game_windows.contains)


class TargetedInputTest(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.windows = TwinWindows()
        patcher = mock.patch.object(targeted_input, "windows", self.windows)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.logs = []
        self.sender = targeted_input.TargetedInput(self.cfg, self.logs.append)
        self.raw = {}
        for name in ("key_down", "key_up", "mouse_down", "mouse_up", "move_to"):
            patcher = mock.patch.object(input_sender, name, return_value=True)
            self.raw[name] = patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(input_sender, "get_cursor_pos", return_value=(400, 300))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(input_sender.user32, "PostMessageW", return_value=True)
        self.post = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(input_sender.user32, "SendInput")
        self.sendinput = patcher.start()
        self.addCleanup(patcher.stop)
        self.select()

    def select(self):
        self.assertTrue(self.sender.select(self.windows.account2))

    def assert_no_global_input(self):
        for method in self.raw.values():
            method.assert_not_called()
        self.sendinput.assert_not_called()

    def test_same_titles_do_not_make_account1_a_valid_target(self):
        self.windows.focus = 100
        self.assertIn("sem foco", self.sender.blocked_reason())
        self.assertFalse(self.sender.tap("e", hold=0))
        self.assertFalse(self.sender.click(hold=0))
        self.assert_no_global_input()

    def test_no_selection_blocks_every_action_even_with_saved_handle(self):
        sender = targeted_input.TargetedInput(self.cfg)
        self.assertFalse(sender.tap("e", hold=0))
        self.assertFalse(sender.key_down("t"))
        self.assertFalse(sender.click(hold=0))
        self.assertFalse(sender.click_at(400, 300))
        self.assert_no_global_input()

    def test_legacy_focus_toggle_does_not_disable_safety(self):
        self.cfg["only_when_focused"] = False
        self.windows.focus = 100
        self.assertFalse(self.sender.key_down("e"))
        self.assert_no_global_input()

    def test_foreground_tap_preserves_down_up(self):
        self.assertTrue(self.sender.tap("1", hold=0))
        self.raw["key_down"].assert_called_once_with("1")
        self.raw["key_up"].assert_called_once_with("1")
        self.post.assert_not_called()

    def test_foreground_mouse_requires_the_selected_window_under_cursor(self):
        self.windows.hit = 100
        self.assertFalse(self.sender.click(hold=0))
        self.assert_no_global_input()

    def test_mouse_outside_client_is_blocked(self):
        with mock.patch.object(input_sender, "get_cursor_pos", return_value=(10, 10)):
            self.assertFalse(self.sender.click(hold=0))
        self.assert_no_global_input()

    def test_dialog_click_outside_target_never_moves_cursor(self):
        self.assertFalse(self.sender.click_at(10, 10))
        self.assert_no_global_input()

    def test_dialog_click_hidden_under_other_window_is_blocked(self):
        self.windows.hit = 100
        self.assertFalse(self.sender.click_at(400, 300))
        self.assert_no_global_input()

    def test_key_release_is_deferred_on_focus_loss(self):
        self.assertTrue(self.sender.key_down("t"))
        self.windows.focus = 100
        self.assertFalse(self.sender.key_up("t"))
        self.raw["key_up"].assert_not_called()
        self.windows.focus = 200
        self.sender.maintain()
        self.raw["key_up"].assert_called_once_with("t")
        self.assertTrue(self.sender.tap("1", hold=0))

    def test_focus_change_during_tap_cannot_send_release_to_account1(self):
        with mock.patch.object(targeted_input.time, "sleep", side_effect=lambda _: setattr(self.windows, "focus", 100)):
            self.assertFalse(self.sender.tap("e", hold=0))
        self.raw["key_up"].assert_not_called()

    def test_mouse_release_is_deferred_on_focus_loss(self):
        self.sender.mouse_down()
        self.windows.focus = 100
        self.sender.mouse_up()
        self.raw["mouse_up"].assert_not_called()
        self.windows.focus = 200
        self.sender.maintain()
        self.raw["mouse_up"].assert_called_once_with("left")

    def test_cannot_switch_instance_with_pending_global_release(self):
        self.sender.key_down("t")
        self.windows.focus = 100
        self.assertFalse(self.sender.select(self.windows.account1))
        self.assertEqual(self.sender.selected()["hwnd"], 200)

    def test_cannot_switch_backend_with_pending_global_release(self):
        self.sender.key_down("t")
        self.windows.focus = 100
        self.assertFalse(self.sender.set_mode("messages"))
        self.assertEqual(self.cfg["input_mode"], "foreground")

    def test_closed_target_blocks_input_without_choosing_account1(self):
        del self.windows.current[200]
        self.assertFalse(self.sender.tap("1", hold=0))
        self.assertEqual(self.sender.selected()["hwnd"], 200)
        self.assert_no_global_input()

    def test_recycled_hwnd_with_other_pid_is_rejected(self):
        self.windows.current[200] = {**self.windows.account2, "pid": 99}
        self.assertFalse(self.sender.tap("1", hold=0))
        self.assert_no_global_input()

    def test_recycled_pid_with_other_process_creation_time_is_rejected(self):
        self.windows.current[200] = {**self.windows.account2, "process_created": "9999"}
        self.assertFalse(self.sender.tap("1", hold=0))
        self.assert_no_global_input()

    def test_title_change_does_not_change_identity(self):
        self.windows.current[200] = {**self.windows.account2, "title": "Loading"}
        self.assertTrue(self.sender.tap("1", hold=0))

    def test_background_keyboard_messages_only_use_account2_hwnd(self):
        self.sender.set_mode("messages")
        self.windows.focus = 100
        self.assertTrue(self.sender.tap("e", hold=0))
        self.assertEqual([call.args[0] for call in self.post.call_args_list], [200, 200])
        self.assertEqual([call.args[1] for call in self.post.call_args_list], [0x100, 0x101])
        self.assert_no_global_input()

    def test_background_mouse_messages_do_not_move_global_cursor(self):
        self.sender.set_mode("messages")
        self.windows.focus = 100
        self.assertTrue(self.sender.click_at(400, 300))
        self.assertEqual([call.args[0] for call in self.post.call_args_list], [200, 200])
        self.assertEqual(self.post.call_args_list[0].args[3], 300 | (200 << 16))
        self.assert_no_global_input()

    def test_failed_postmessage_never_falls_back_to_sendinput(self):
        self.sender.set_mode("messages")
        self.post.return_value = False
        self.assertFalse(self.sender.tap("1", hold=0))
        self.assert_no_global_input()

    def test_failed_sendinput_is_reported_and_does_not_pretend_to_hold(self):
        self.raw["key_down"].side_effect = OSError("blocked")
        self.assertFalse(self.sender.key_down("t"))
        self.assertEqual(self.sender._pressed, {})
        self.assertTrue(any("blocked" in message for message in self.logs))

    def test_failed_release_can_be_retried(self):
        self.sender.key_down("t")
        self.raw["key_up"].side_effect = OSError("blocked")
        self.assertFalse(self.sender.key_up("t"))
        self.raw["key_up"].side_effect = None
        self.sender.maintain()
        self.assertFalse(self.sender._pending)

    def test_suspending_for_calibration_blocks_input(self):
        self.sender.suspend(True)
        self.assertFalse(self.sender.tap("e", hold=0))
        self.assert_no_global_input()

    def test_minimized_target_is_blocked(self):
        self.windows.minimized = True
        self.assertFalse(self.sender.tap("e", hold=0))
        self.assert_no_global_input()

    def test_legacy_absolute_skill_region_requires_recapture(self):
        self.assertIsNone(self.sender.skill_region({"region": [400, 300, 32, 32]}))

    def test_skill_region_tracks_window_movement(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.windows.region = (200, 200, 800, 600)
        self.assertEqual(self.sender.skill_region({"window_region": binding}), [500, 400, 32, 32])

    def test_skill_region_blocks_when_window_is_resized(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.windows.region = (100, 100, 640, 480)
        self.assertIsNone(self.sender.skill_region({"window_region": binding}))

    def test_visible_skills_can_be_read_in_background_in_messages_mode(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.sender.set_mode("messages")
        self.windows.focus = 100
        self.assertEqual(self.sender.skill_region({"window_region": binding}), [400, 300, 32, 32])
        self.assertIsNone(self.sender.client_region(require_focus=True))

    def test_compatibility_still_blocks_skills_when_unfocused(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.windows.focus = 100
        self.assertIsNone(self.sender.skill_region({"window_region": binding}))

    def test_covered_icon_is_blocked_even_in_messages_mode(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.sender.set_mode("messages")
        self.windows.focus = 100
        self.windows.hit = 100
        skill = {"id": "s1", "window_region": binding}
        self.assertIsNone(self.sender.skill_region(skill))
        self.assertIn("encoberto", self.sender.skill_blocked_reason(skill))
        self.assert_no_global_input()

    def test_covering_only_center_of_icon_blocks_the_capture(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.sender.set_mode("messages")
        self.windows.focus = 100
        with mock.patch.object(self.windows, "point_belongs", side_effect=lambda hwnd, x, y: (x, y) != (416, 316)):
            self.assertIsNone(self.sender.skill_region({"window_region": binding}))

    def test_outside_region_is_not_reported_as_an_occluding_window(self):
        self.assertEqual(self.sender.region_issue([890, 300, 32, 32]), "outside")
        self.assertIsNone(self.sender.bind_region([890, 300, 32, 32]))

    def test_visibility_reason_distinguishes_occlusion_from_unavailable_game(self):
        self.windows.hit = 100
        self.assertEqual(self.sender.region_issue([400, 300, 32, 32]), "covered")
        self.windows.minimized = True
        self.assertEqual(self.sender.region_issue([400, 300, 32, 32]), "unavailable")

    def background_skill(self):
        binding = self.sender.bind_region((400, 300, 32, 32))
        self.sender.set_mode("messages")
        self.windows.focus = 100
        return {"id": "s1", "name": "1", "key": "1", "enabled": True,
                "region": [400, 300, 32, 32], "window_region": binding,
                "ready_score": 0.5, "threshold": 0.8, "min_interval": 0.6}

    def test_visible_background_skill_continues_firing_at_configured_interval(self):
        skill = self.background_skill()
        engine = bot.Bot(self.cfg, sender=self.sender)
        engine.master = True
        self.assertIsNone(engine.blocked_reason("skills"))
        with mock.patch.object(bot.vision, "skill_ratio", return_value=0.95), mock.patch.object(bot.time, "time", return_value=100) as now:
            self.assertTrue(engine._try_skill(skill))
            self.assertFalse(engine._try_skill(skill))
            now.return_value = 100.7
            self.assertTrue(engine._try_skill(skill))
        self.assertEqual([call.args[0] for call in self.post.call_args_list], [200] * 4)
        self.assert_no_global_input()

    def test_skill_does_not_fire_if_icon_is_covered_during_capture(self):
        skill = self.background_skill()
        engine = bot.Bot(self.cfg, sender=self.sender)
        def cover_icon(_skill):
            self.windows.hit = 100
            return 0.95
        with mock.patch.object(bot.vision, "skill_ratio", side_effect=cover_icon):
            self.assertFalse(engine._try_skill(skill))
        self.post.assert_not_called()
        self.assertIn("encoberto", engine.status["s1"])

    def test_skill_log_reports_visibility_changes_without_flooding(self):
        skill = self.background_skill()
        self.windows.hit = 100
        self.sender.skill_region(skill)
        log_count = len(self.logs)
        self.sender.skill_region(skill)
        self.assertEqual(len(self.logs), log_count)
        self.windows.hit = 200
        self.assertIsNotNone(self.sender.skill_region(skill))
        self.assertTrue(any("leitura retomada" in message for message in self.logs))

    def test_dialog_search_is_limited_to_selected_client(self):
        engine = bot.Bot(self.cfg, sender=self.sender)
        with mock.patch.object(engine, "_template_for", return_value=object()), mock.patch.object(bot.vision, "find_template", return_value=None) as finder:
            engine._find_dialog("claim", self.cfg["claim"])
        self.assertEqual(finder.call_args.kwargs["region"], self.windows.region)

    def test_lost_focus_debug_log_is_present(self):
        self.sender.blocked_reason()
        self.windows.focus = 100
        self.sender.blocked_reason()
        self.assertIn("[Bot] Janela perdeu foco", self.logs)

    def test_api_rejects_stale_row_before_changing_selection(self):
        engine = bot.Bot(self.cfg, sender=self.sender)
        bridge = api.Api(self.cfg, engine, mock.Mock())
        stale = {**self.windows.account2, "process_created": "expired"}
        with mock.patch.object(bridge, "list_windows", return_value=[self.windows.account2]):
            self.assertFalse(bridge.select_window(stale))
        self.assertEqual(self.sender.selected()["hwnd"], 200)

    def test_api_selection_stops_running_routines_and_saves_identity(self):
        engine = bot.Bot(self.cfg, sender=self.sender)
        engine.master = True
        engine.features["holdkey"] = True
        bridge = api.Api(self.cfg, engine, mock.Mock())
        with mock.patch.object(bridge, "list_windows", return_value=[self.windows.account1]), mock.patch.object(config, "save") as save:
            self.assertTrue(bridge.select_window(self.windows.account1))
        self.assertFalse(engine.master)
        self.assertFalse(engine.features["holdkey"])
        self.assertEqual(self.cfg["selected_window"]["hwnd"], 100)
        save.assert_called_once()


class RawSendInputTest(unittest.TestCase):
    def test_windows_rejection_is_reported(self):
        with mock.patch.object(input_sender.user32, "SendInput", return_value=0):
            with self.assertRaises(OSError):
                input_sender.key_down("1")

    def test_virtual_desktop_coordinates_include_negative_origin(self):
        metrics = {76: -1920, 77: 0, 78: 3840, 79: 1080}
        with mock.patch.object(input_sender.user32, "GetSystemMetrics", side_effect=metrics.get), mock.patch.object(input_sender, "_send", return_value=True) as send:
            input_sender.move_to(-1920, 0)
        event = send.call_args.args[0]
        self.assertEqual(event.mi.dx, 0)
        self.assertTrue(event.mi.dwFlags & 0x4000)


class DiscoveryTest(unittest.TestCase):
    def test_only_game_executables_are_listed_even_with_same_title(self):
        records = {
            100: {"hwnd": 100, "pid": 10, "title": "Trove", "process_created": "100", "exe": "C:/Game/Trove_x64.exe"},
            200: {"hwnd": 200, "pid": 20, "title": "Trove", "process_created": "200", "exe": "C:/Game/Trove_x64.exe"},
            300: {"hwnd": 300, "pid": 30, "title": "Trove Autoclick", "process_created": "300", "exe": "C:/Windows/explorer.exe"},
        }

        def enumerate_windows(callback, parameter):
            for hwnd in records:
                callback(hwnd, parameter)
            return True

        with mock.patch.object(game_windows.user32, "EnumWindows", side_effect=enumerate_windows), mock.patch.object(game_windows.user32, "IsWindowVisible", return_value=True), mock.patch.object(game_windows, "window_info", side_effect=records.get), mock.patch.object(game_windows, "client_region", return_value=(0, 0, 800, 600)):
            listed = game_windows.list_game_windows({"target_window": "Trove"})
        self.assertEqual([item["hwnd"] for item in listed], [100, 200])

    def test_native_discovery_never_changes_foreground_or_cursor(self):
        # Real read-only enumeration; no synthetic input or focus switching.
        with mock.patch.object(input_sender.user32, "SendInput") as send, mock.patch.object(game_windows.user32, "SetForegroundWindow") as focus:
            listed = game_windows.list_game_windows({"target_window": "Trove"})
        send.assert_not_called()
        focus.assert_not_called()
        self.assertTrue(all(os.path.basename(item["exe"]).lower() in game_windows.GAME_EXECUTABLES for item in listed))


if __name__ == "__main__":
    unittest.main()
