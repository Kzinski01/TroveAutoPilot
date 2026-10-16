"""Testes das regras do bot: config, visao, calibracao, atalhos e rotinas."""

import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from fake_target import FakeTargetMixin
import bot as bot_module
import calibration
import config
import deps
import hotkeys
import vision


def make_icon(brightness, size=32):
    """Icone sintetico: cor uniforme com o brilho pedido."""
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = (brightness, brightness // 2, brightness // 3)
    return image


def make_patch(size=20, seed=7):
    """Recorte com textura, como um template real (o liso nao serve)."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (size, size, 3), dtype=np.uint8)


class ConfigTest(unittest.TestCase):
    def test_defaults_have_every_section(self):
        cfg = config.DEFAULTS
        for key in ("features", "autoclick", "skills", "potion", "claim",
                    "invite", "hotkeys"):
            self.assertIn(key, cfg)
        self.assertEqual(len(cfg["skills"]), 3)

    def test_load_merges_new_keys_into_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path), \
                 mock.patch.object(config, "TEMPLATE_DIR",
                                   os.path.join(folder, "templates")):
                cfg = config.load()
                cfg["potion"]["interval"] = 42.0
                del cfg["autoclick"]["cps"]        # simula config antigo
                config.save(cfg)

                reloaded = config.load()
                self.assertEqual(reloaded["potion"]["interval"], 42.0)
                self.assertIn("cps", reloaded["autoclick"])   # veio do default

    def test_load_keeps_skill_calibration_by_id(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path), \
                 mock.patch.object(config, "TEMPLATE_DIR", folder):
                cfg = config.load()
                cfg["skills"][1]["ready_score"] = 0.5
                cfg["skills"][1]["region"] = [1, 2, 3, 4]
                config.save(cfg)

                skill = config.load()["skills"][1]
                self.assertEqual(skill["id"], "s1")
                self.assertEqual(skill["ready_score"], 0.5)
                self.assertEqual(skill["region"], [1, 2, 3, 4])

    def test_resolve_template_handles_relative_and_moved_paths(self):
        self.assertEqual(config.resolve_template(""), "")
        self.assertEqual(config.resolve_template("claim.png"),
                         os.path.join(config.TEMPLATE_DIR, "claim.png"))
        # caminho absoluto de outra maquina: cai para a pasta local
        self.assertEqual(config.resolve_template(r"D:\antigo\templates\claim.png"),
                         os.path.join(config.TEMPLATE_DIR, "claim.png"))


class WindowTitleTest(unittest.TestCase):
    """O jogo troca o titulo da janela; mais de um nome pode valer."""

    def _cfg(self, principal="Trove", extras=""):
        return {"target_window": principal, "extra_windows": extras}

    def test_only_the_main_title_by_default(self):
        self.assertEqual(config.window_titles(self._cfg()), ["Trove"])

    def test_extras_are_split_by_comma_semicolon_and_newline(self):
        cfg = self._cfg(extras="Glyph, Carregando; Login" + chr(10) + "Launcher")
        self.assertEqual(config.window_titles(cfg),
                         ["Trove", "Glyph", "Carregando", "Login", "Launcher"])

    def test_blank_entries_and_duplicates_are_dropped(self):
        cfg = self._cfg(extras=" , trove ,, TROVE , Glyph ")
        self.assertEqual(config.window_titles(cfg), ["Trove", "Glyph"])

    def test_matching_accepts_any_of_the_titles(self):
        cfg = self._cfg(extras="Glyph")
        self.assertTrue(config.matches_window(cfg, "Trove"))
        self.assertTrue(config.matches_window(cfg, "Glyph Client"))
        self.assertFalse(config.matches_window(cfg, "Bloco de Notas"))

    def test_matching_ignores_case_and_empty_titles(self):
        cfg = self._cfg()
        self.assertTrue(config.matches_window(cfg, "TROVE - servidor"))
        self.assertFalse(config.matches_window(cfg, ""))
        self.assertFalse(config.matches_window(cfg, None))

    def test_bot_accepts_an_extra_title_as_the_game(self):
        cfg = _fresh_config()
        cfg["extra_windows"] = "Glyph"
        fake = FakeInput(window="Glyph Client")
        with mock.patch.object(bot_module, "TargetedInput", side_effect=lambda cfg, log: fake.configure(cfg)):
            bot = bot_module.Bot(cfg)
            bot.set_master(True)
            self.assertIsNone(bot.blocked_reason("autoclick"))

    def test_bot_still_blocks_an_unrelated_window(self):
        cfg = _fresh_config()
        cfg["extra_windows"] = "Glyph"
        fake = FakeInput(window="Bloco de Notas")
        with mock.patch.object(bot_module, "TargetedInput", side_effect=lambda cfg, log: fake.configure(cfg)):
            bot = bot_module.Bot(cfg)
            bot.set_master(True)
            self.assertIn("sem foco", bot.blocked_reason("autoclick"))


class VisionTest(unittest.TestCase):
    def test_icon_score_grows_with_brightness(self):
        dark = vision.icon_score(make_icon(40))
        bright = vision.icon_score(make_icon(220))
        self.assertLess(dark, bright)

    def test_icon_score_is_bounded(self):
        self.assertGreaterEqual(vision.icon_score(make_icon(0)), 0.0)
        self.assertLessEqual(vision.icon_score(make_icon(255)), 1.0)

    def test_icon_score_of_empty_image(self):
        self.assertEqual(vision.icon_score(None), 0.0)

    def test_auto_threshold_sits_between_the_two_states(self):
        threshold = vision.auto_threshold(0.52, 0.30)
        self.assertIsNotNone(threshold)
        self.assertLess(0.30 / 0.52, threshold)
        self.assertLess(threshold, 1.0)

    def test_auto_threshold_rejects_bad_calibration(self):
        self.assertIsNone(vision.auto_threshold(0.30, 0.52))   # invertido
        self.assertIsNone(vision.auto_threshold(0.52, 0.0))    # sem cooldown
        self.assertIsNone(vision.auto_threshold(0.0, 0.0))

    def test_skill_ratio_needs_region_and_calibration(self):
        self.assertIsNone(vision.skill_ratio({"region": None, "ready_score": 0.5}))
        self.assertIsNone(vision.skill_ratio({"region": [0, 0, 4, 4],
                                              "ready_score": 0.0}))

    def test_skill_ratio_compares_against_ready_score(self):
        skill = {"region": [0, 0, 32, 32], "ready_score": 0.5}
        with mock.patch.object(vision, "grab", return_value=make_icon(200)):
            expected = vision.icon_score(make_icon(200)) / 0.5
            self.assertAlmostEqual(vision.skill_ratio(skill), expected, places=6)

    def test_find_template_locates_a_known_patch(self):
        screen = np.zeros((200, 300, 3), dtype=np.uint8)
        patch = make_patch()
        screen[50:70, 100:120] = patch
        with mock.patch.object(vision, "grab_screen", return_value=(screen, 0, 0)):
            hit = vision.find_template(patch, confidence=0.9)
        self.assertIsNotNone(hit)
        x, y, score = hit
        self.assertEqual((x, y), (110, 60))
        self.assertGreater(score, 0.9)

    def test_find_template_applies_the_region_offset(self):
        screen = np.zeros((100, 100, 3), dtype=np.uint8)
        patch = make_patch(size=10)
        screen[20:30, 40:50] = patch
        with mock.patch.object(vision, "grab", return_value=screen):
            hit = vision.find_template(patch, confidence=0.9, region=(500, 300, 100, 100))
        self.assertEqual(hit[:2], (545, 325))

    def test_find_template_returns_none_when_absent(self):
        screen = np.zeros((200, 300, 3), dtype=np.uint8)
        with mock.patch.object(vision, "grab_screen", return_value=(screen, 0, 0)):
            self.assertIsNone(vision.find_template(make_patch(), confidence=0.95))
        self.assertIsNone(vision.find_template(None))

    def test_flat_template_is_rejected(self):
        self.assertFalse(vision.has_texture(make_icon(120)))
        self.assertTrue(vision.has_texture(make_patch()))
        self.assertFalse(vision.has_texture(None))


class CaptureThreadTest(unittest.TestCase):
    """O mss precisa viver numa thread so: e o que evitou o STATUS_BREAKPOINT.

    Se uma captura voltar a rodar na thread de quem pediu, o objeto do mss fica
    orfao quando essa thread morre e o coletor de lixo o finaliza em qualquer
    outra, corrompendo a heap.
    """

    def test_every_capture_runs_on_the_capture_thread(self):
        vistas = []

        def espiao(sct):
            vistas.append(threading.current_thread().name)
            return "pronto"

        chamadores = []

        def pedir():
            chamadores.append(threading.current_thread().name)
            vision._no_capturador(espiao)

        threads = [threading.Thread(target=pedir, name=f"chamador-{i}")
                   for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)

        self.assertEqual(len(vistas), 5)
        self.assertEqual(set(vistas), {"captura"})
        self.assertNotIn("captura", chamadores)

    def test_only_one_capture_thread_ever_exists(self):
        for _ in range(3):
            vision._no_capturador(lambda sct: None)
        vivas = [t for t in threading.enumerate() if t.name == "captura"]
        self.assertEqual(len(vivas), 1)

    def test_failures_reach_whoever_asked(self):
        def explode(sct):
            raise ValueError("tela sumiu")

        with self.assertRaises(ValueError):
            vision._no_capturador(explode)
        # a thread sobrevive ao erro e continua atendendo
        self.assertEqual(vision._no_capturador(lambda sct: 42), 42)


class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self.skill = {"id": "s1", "name": "1", "ready_score": 0.0,
                      "cooldown_score": 0.0, "threshold": 0.98}

    def test_ready_sample_uses_the_lowest_reading(self):
        calibration.apply_skill_sample(self.skill, calibration.READY,
                                       [0.60, 0.52, 0.58])
        self.assertAlmostEqual(self.skill["ready_score"], 0.52)

    def test_cooldown_sample_uses_the_highest_reading(self):
        calibration.apply_skill_sample(self.skill, calibration.COOLDOWN,
                                       [0.28, 0.34, 0.30])
        self.assertAlmostEqual(self.skill["cooldown_score"], 0.34)

    def test_calibration_never_touches_the_threshold(self):
        """O limite e do usuario: a calibracao mede e sugere, nunca aplica."""
        self.skill["threshold"] = 0.85
        calibration.apply_skill_sample(self.skill, calibration.READY, [0.52])
        calibration.apply_skill_sample(self.skill, calibration.COOLDOWN, [0.30])
        self.assertEqual(self.skill["threshold"], 0.85)

    def test_both_states_produce_a_suggestion_in_the_log(self):
        calibration.apply_skill_sample(self.skill, calibration.READY, [0.52])
        linhas = calibration.apply_skill_sample(self.skill, calibration.COOLDOWN,
                                                [0.30])
        texto = chr(10).join(linhas)
        self.assertIn("sugestao de limite", texto)
        # a sugestao separa os dois estados, mesmo sem ser aplicada
        sugestao = vision.auto_threshold(self.skill["ready_score"],
                                         self.skill["cooldown_score"])
        self.assertGreaterEqual(0.52 / self.skill["ready_score"], sugestao)
        self.assertLess(0.30 / self.skill["ready_score"], sugestao)

    def test_ready_alone_is_enough_to_measure(self):
        """So o estado pronto ja da o ratio; o cooldown e opcional."""
        linhas = calibration.apply_skill_sample(self.skill, calibration.READY,
                                                [0.52])
        self.assertEqual(self.skill["ready_score"], 0.52)
        self.assertIn("opcional", chr(10).join(linhas))

    def test_inverted_calibration_is_reported(self):
        calibration.apply_skill_sample(self.skill, calibration.READY, [0.30])
        lines = calibration.apply_skill_sample(self.skill, calibration.COOLDOWN,
                                               [0.52])
        self.assertTrue(any("não ficou mais escuro" in line for line in lines))

    def test_click_offset_is_relative_to_the_template_center(self):
        self.assertEqual(calibration.click_offset([100, 200, 50, 20], (145, 205)),
                         [20, -5])


class HotkeyTest(unittest.TestCase):
    def setUp(self):
        self.manager = hotkeys.HotkeyManager()

    def test_normalize_orders_modifiers(self):
        self.assertEqual(self.manager.normalize("Shift+CTRL+F5"), "ctrl+shift+f5")
        self.assertEqual(self.manager.normalize("f12"), "f12")
        self.assertEqual(self.manager.normalize(" ALT + q "), "alt+q")

    def test_registered_hotkey_runs_its_callback(self):
        fired = []
        self.manager.set_bindings({"f5": lambda: fired.append(True)})
        self.manager._on_press(hotkeys.keyboard.Key.f5)
        for _ in range(50):
            if fired:
                break
            time.sleep(0.01)
        self.assertEqual(fired, [True])

    def test_capture_intercepts_the_next_combo(self):
        captured = []
        self.manager.capture_next(captured.append)
        self.manager._on_press(hotkeys.keyboard.Key.ctrl_l)
        self.manager._on_press(hotkeys.keyboard.Key.f7)
        self.assertEqual(captured, ["ctrl+f7"])

    def test_capture_does_not_fire_existing_bindings(self):
        fired = []
        self.manager.set_bindings({"f5": lambda: fired.append(True)})
        self.manager.capture_next(lambda _combo: None)
        self.manager._on_press(hotkeys.keyboard.Key.f5)
        time.sleep(0.05)
        self.assertEqual(fired, [])

    def test_modifiers_are_released(self):
        self.manager._on_press(hotkeys.keyboard.Key.shift)
        self.assertIn("shift", self.manager._active_modifiers)
        self.manager._on_release(hotkeys.keyboard.Key.shift)
        self.assertNotIn("shift", self.manager._active_modifiers)


class FakeInput(FakeTargetMixin):
    """Substitui o input_sender para os testes registrarem o que foi enviado."""

    def __init__(self, window="Trove"):
        self.window = window
        self.taps = []
        self.clicks = []
        self.clicks_at = []
        self.down = []
        self.up = []
        self.keys_down = []
        self.keys_up = []

    def foreground_window_title(self):
        return self.window

    def tap(self, key, hold=0.0):
        self.taps.append(key)
        return True

    def key_down(self, key):
        if key not in ("t", "1", "2", "q", "l", "shift"):
            return False
        self.keys_down.append(key)
        return True

    def key_up(self, key):
        self.keys_up.append(key)
        return True

    def click(self, button="left", hold=0.0):
        self.clicks.append(button)

    def click_at(self, x, y, button="left", restore=True):
        self.clicks_at.append((x, y))

    def mouse_down(self, button="left"):
        self.down.append(button)

    def mouse_up(self, button="left"):
        self.up.append(button)


class BotRulesTest(unittest.TestCase):
    def setUp(self):
        self.cfg = _fresh_config()
        self.fake = FakeInput()
        patcher = mock.patch.object(bot_module, "TargetedInput", side_effect=lambda cfg, log: self.fake.configure(cfg))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bot = bot_module.Bot(self.cfg)

    # ---- portoes
    def test_blocked_while_master_is_off(self):
        self.assertEqual(self.bot.blocked_reason("autoclick"), "master off")

    def test_blocked_when_feature_is_off(self):
        self.bot.set_master(True)
        self.bot.set_feature("skills", False)
        self.assertEqual(self.bot.blocked_reason("skills"), "off")

    def test_blocked_when_game_is_not_focused(self):
        self.bot.set_master(True)
        self.fake.window = "Bloco de Notas"
        self.assertIn("sem foco", self.bot.blocked_reason("autoclick"))

    def test_runs_when_focused(self):
        self.bot.set_master(True)
        self.assertIsNone(self.bot.blocked_reason("autoclick"))

    def test_focus_filter_cannot_be_disabled(self):
        self.bot.set_master(True)
        self.fake.window = "Outra coisa"
        self.cfg["only_when_focused"] = False
        self.assertIn("sem foco", self.bot.blocked_reason("autoclick"))

    # ---- skills
    def test_skill_fires_when_ratio_reaches_threshold(self):
        skill = self._ready_skill(threshold=0.8)
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=0.95):
            self.assertTrue(self.bot._try_skill(skill))
        self.assertEqual(self.fake.taps, ["1"])

    def test_skill_holds_while_on_cooldown(self):
        skill = self._ready_skill(threshold=0.8)
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=0.62):
            self.assertFalse(self.bot._try_skill(skill))
        self.assertEqual(self.fake.taps, [])

    def test_skill_respects_min_interval(self):
        skill = self._ready_skill(threshold=0.8, min_interval=5.0)
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=0.95):
            self.assertTrue(self.bot._try_skill(skill))
            self.assertFalse(self.bot._try_skill(skill))   # cedo demais
        self.assertEqual(self.fake.taps, ["1"])

    def test_disabled_skill_never_fires(self):
        skill = self._ready_skill(threshold=0.8)
        skill["enabled"] = False
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=0.99):
            self.assertFalse(self.bot._try_skill(skill))

    def test_uncalibrated_skill_reports_status(self):
        skill = self._ready_skill(threshold=0.8)
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=None):
            self.assertFalse(self.bot._try_skill(skill))
        self.assertEqual(self.bot.status["s1"], "sem calibração")

    def test_mouse_skill_clicks_instead_of_typing(self):
        skill = self._ready_skill(threshold=0.8, key="mouse_right")
        with mock.patch.object(bot_module.vision, "skill_ratio", return_value=0.95):
            self.bot._try_skill(skill)
        self.assertEqual(self.fake.clicks, ["right"])
        self.assertEqual(self.fake.taps, [])

    # ---- auto clique
    def test_hold_mode_presses_once_and_releases_once(self):
        self.bot._hold_mouse("left")
        self.bot._hold_mouse("left")
        self.assertEqual(self.fake.down, ["left"])
        self.bot._release_mouse()
        self.bot._release_mouse()
        self.assertEqual(self.fake.up, ["left"])

    def test_failure_to_release_the_button_is_reported(self):
        avisos = []
        self.bot.set_logger(avisos.append)
        self.bot._hold_mouse("left")
        self.fake.mouse_up = mock.Mock(side_effect=OSError("SendInput falhou"))

        self.bot._release_mouse()

        self.assertFalse(self.bot._mouse_held)
        self.assertTrue(any("ATENCAO" in linha for linha in avisos), avisos)

    def test_turning_master_off_releases_the_button(self):
        self.bot._hold_mouse("left")
        self.bot.set_master(False)
        self.assertEqual(self.fake.up, ["left"])

    def test_spam_click_respects_the_cps_cap(self):
        self.bot._spam_click("left", cps=1000)      # muito acima do teto
        self.assertEqual(self.fake.clicks, ["left"])
        self.assertEqual(self.bot.status["autoclick"],
                         f"{bot_module.MAX_CPS:.0f} cps")

    def test_spam_click_keeps_a_valid_rate_when_cps_is_absurdly_low(self):
        self.bot._spam_click("left", cps=0)
        self.assertEqual(self.bot.status["autoclick"], "1 cps")

    # ---- janelas
    def test_dialog_with_key_action_presses_the_key(self):
        cfg = {"enabled": True, "action": "key", "key": "l", "cooldown": 1.5,
               "template": "claim.png"}
        with mock.patch.object(self.bot, "_find_dialog", return_value=vision.Match(500, 300, 0.93)):
            self.bot._handle_dialog("claim", cfg)
        self.assertEqual(self.fake.taps, ["l"])
        self.assertEqual(self.fake.clicks_at, [])

    def test_dialog_with_click_action_uses_the_offset(self):
        cfg = {"enabled": True, "action": "click", "click_offset": [240, -7],
               "cooldown": 1.5, "template": "claim.png"}
        with mock.patch.object(self.bot, "_find_dialog", return_value=vision.Match(500, 300, 0.93)):
            self.bot._handle_dialog("claim", cfg)
        self.assertEqual(self.fake.clicks_at, [(740, 293)])

    def test_dialog_pauses_the_autoclick(self):
        cfg = {"enabled": True, "action": "key", "key": "l", "cooldown": 1.5,
               "template": "claim.png"}
        self.assertFalse(self.bot._blocked_by_dialog())
        with mock.patch.object(self.bot, "_find_dialog", return_value=vision.Match(1, 1, 0.9)):
            self.bot._handle_dialog("claim", cfg)
        self.assertTrue(self.bot._blocked_by_dialog())

    def test_disabled_dialog_is_skipped(self):
        cfg = {"enabled": False, "action": "key", "key": "l"}
        with mock.patch.object(self.bot, "_find_dialog") as finder:
            self.bot._handle_dialog("claim", cfg)
        finder.assert_not_called()

    def test_missing_template_reports_status(self):
        self.cfg["claim"]["template"] = ""
        self.assertIsNone(self.bot._find_dialog("claim", self.cfg["claim"]))
        self.assertEqual(self.bot.status["claim"], "sem template")

    # ---- pocao
    def test_potion_key_is_sent(self):
        self.bot._press(self.cfg["potion"]["key"])
        self.assertEqual(self.fake.taps, ["q"])

    def test_empty_key_sends_nothing(self):
        self.bot._press("")
        self.assertEqual(self.fake.taps, [])
        self.assertEqual(self.fake.clicks, [])

    # ---- ciclo de vida
    def test_threads_start_and_stop(self):
        self.bot.start()
        # uma thread por rotina: clique, skills, pocao, janelas, tecla
        self.assertEqual(len(self.bot._threads), 5)
        self.bot.shutdown()
        self.assertEqual(self.bot._threads, [])

    def test_shutdown_does_not_block_the_ui_thread(self):
        """Quem chama shutdown e a thread da janela: nao pode demorar."""
        self.bot.start()
        time.sleep(0.3)
        inicio = time.time()
        self.bot.shutdown()
        gasto = time.time() - inicio
        limite = len(bot_module.DIALOG_NAMES) + bot_module.JOIN_TIMEOUT * 5
        self.assertLess(gasto, limite, f"shutdown levou {gasto:.2f}s")

    def test_panic_turns_everything_off(self):
        self.bot.set_master(True)
        self.bot.panic()
        self.assertFalse(self.bot.master)

    def test_toggle_feature_flips_the_flag(self):
        before = self.bot.features["potion"]
        self.bot.toggle_feature("potion")
        self.assertNotEqual(before, self.bot.features["potion"])

    def _ready_skill(self, threshold, key="1", min_interval=0.0):
        return {"id": "s1", "name": "1", "key": key, "enabled": True,
                "region": [0, 0, 10, 10], "ready_score": 0.5,
                "cooldown_score": 0.3, "threshold": threshold,
                "min_interval": min_interval}


class HoldKeyTest(unittest.TestCase):
    """Rotina que segura uma tecla por N segundos e repete."""

    def setUp(self):
        self.cfg = _fresh_config()
        self.cfg["holdkey"] = {"key": "t", "duration": 0.2}
        self.fake = FakeInput()
        patcher = mock.patch.object(bot_module, "TargetedInput", side_effect=lambda cfg, log: self.fake.configure(cfg))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bot = bot_module.Bot(self.cfg)
        self.bot.set_master(True)
        self.bot.set_feature("holdkey", True)

    def test_one_cycle_presses_and_releases(self):
        self.bot._hold_key_once("t", 0.15)
        self.assertEqual(self.fake.keys_down, ["t"])
        self.assertEqual(self.fake.keys_up, ["t"])

    def test_hold_lasts_about_the_configured_time(self):
        started = time.time()
        self.bot._hold_key_once("t", 0.30)
        elapsed = time.time() - started
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertLess(elapsed, 0.9)

    def test_runs_with_the_master_switch_off(self):
        """A rotina e independente: basta o switch dela."""
        self.bot.set_master(False)
        self.assertIsNone(self.bot.blocked_reason("holdkey"))

    def test_the_other_routines_still_need_the_master(self):
        self.bot.set_master(False)
        for rotina in ("autoclick", "skills", "potion", "dialogs"):
            self.bot.set_feature(rotina, True)
            self.assertEqual(self.bot.blocked_reason(rotina), "master off")

    def test_master_off_does_not_release_the_key(self):
        """Desligar o master nao pode interromper uma rotina independente."""
        self.bot._held_key = "t"
        self.bot.set_master(False)
        self.assertEqual(self.fake.keys_up, [])
        self.assertEqual(self.bot._held_key, "t")

    def test_key_is_released_when_the_routine_is_turned_off_mid_hold(self):
        """O ponto critico: a tecla nao pode ficar presa no jogo."""
        def desligar():
            time.sleep(0.1)
            self.bot.set_feature("holdkey", False)

        threading.Thread(target=desligar, daemon=True).start()
        started = time.time()
        self.bot._hold_key_once("t", 10.0)      # prazo longo de proposito
        elapsed = time.time() - started

        self.assertLess(elapsed, 2.0)           # cortou bem antes dos 10s
        self.assertEqual(self.fake.keys_up, ["t"])
        self.assertIsNone(self.bot._held_key)

    def test_panic_stops_the_independent_routine_too(self):
        self.bot._held_key = "t"
        self.bot.panic()
        self.assertFalse(self.bot.features["holdkey"])
        self.assertEqual(self.fake.keys_up, ["t"])

    def test_key_is_released_when_focus_is_lost_mid_hold(self):
        def sair_do_jogo():
            time.sleep(0.1)
            self.fake.window = "Bloco de Notas"

        threading.Thread(target=sair_do_jogo, daemon=True).start()
        self.bot._hold_key_once("t", 10.0)
        self.assertEqual(self.fake.keys_up, ["t"])

    def test_shutdown_releases_a_held_key(self):
        self.fake.keys_down.append("marcador")
        self.bot._held_key = "t"
        self.bot.shutdown()
        self.assertIn("t", self.fake.keys_up)
        self.assertIsNone(self.bot._held_key)

    def test_turning_the_feature_off_releases_the_key(self):
        self.bot._held_key = "t"
        self.bot.set_feature("holdkey", False)
        self.assertEqual(self.fake.keys_up, ["t"])

    def test_failure_to_release_is_reported_not_swallowed(self):
        """Falhar ao soltar significa tecla presa no jogo: nao pode ser mudo."""
        avisos = []
        self.bot.set_logger(avisos.append)
        self.bot._held_key = "t"
        self.fake.key_up = mock.Mock(side_effect=OSError("SendInput falhou"))

        self.bot._release_held_key()

        self.assertIsNone(self.bot._held_key)      # estado limpo mesmo assim
        self.assertTrue(any("ATENCAO" in linha for linha in avisos), avisos)

    def test_release_is_idempotent(self):
        self.bot._held_key = "t"
        self.bot._release_held_key()
        self.bot._release_held_key()
        self.assertEqual(self.fake.keys_up, ["t"])

    def test_invalid_key_does_not_pretend_to_hold(self):
        self.bot._hold_key_once("tecla_inexistente", 0.2)
        self.assertEqual(self.fake.keys_down, [])
        self.assertIsNone(self.bot._held_key)
        self.assertIn("invalida", self.bot.status["holdkey"])

    def test_duration_is_clamped(self):
        # sem teto, um valor absurdo seguraria a tecla por horas
        self.assertEqual(bot_module.clamp_hold(9999), bot_module.MAX_HOLD)
        self.assertEqual(bot_module.clamp_hold(0), 0.1)
        self.assertEqual(bot_module.clamp_hold(3.0), 3.0)

    def test_duration_survives_a_broken_value(self):
        self.assertEqual(bot_module.clamp_hold("abc"), 3.0)
        self.assertEqual(bot_module.clamp_hold(None), 3.0)

    def test_feature_starts_disabled_by_default(self):
        self.assertFalse(config.DEFAULTS["features"]["holdkey"])


class DialogCooldownTest(unittest.TestCase):
    """Depois de agir sobre uma janela, o bot espera ela responder."""

    def setUp(self):
        self.cfg = _fresh_config()
        self.fake = FakeInput()
        patcher = mock.patch.object(bot_module, "TargetedInput", side_effect=lambda cfg, log: self.fake.configure(cfg))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bot = bot_module.Bot(self.cfg)
        self.bot.set_master(True)
        self.bot.set_feature("dialogs", True)

    def test_dialogs_routine_needs_the_master(self):
        self.bot.set_master(False)
        self.assertEqual(self.bot.blocked_reason("dialogs"), "master off")

    def test_clicking_uses_the_detected_position(self):
        cfg = dict(self.cfg["invite"], template="invite.png")
        with mock.patch.object(self.bot, "_find_dialog",
                               return_value=vision.Match(640, 480, 0.95)):
            self.bot._handle_dialog("invite", cfg)
        self.assertEqual(self.fake.clicks_at, [(640, 480)])

    def test_cooldown_stops_the_bot_from_hammering_the_button(self):
        cfg = dict(self.cfg["invite"], template="invite.png", cooldown=5.0)
        with mock.patch.object(self.bot, "_find_dialog",
                               return_value=vision.Match(10, 20, 0.99)):
            self.bot._handle_dialog("invite", cfg)     # age
            self.bot._handle_dialog("invite", cfg)     # ainda no cooldown
            self.bot._handle_dialog("invite", cfg)
        self.assertEqual(len(self.fake.clicks_at), 1)

    def test_cooldown_expires_and_it_tries_again(self):
        cfg = dict(self.cfg["invite"], template="invite.png", cooldown=0.05)
        with mock.patch.object(self.bot, "_find_dialog",
                               return_value=vision.Match(10, 20, 0.99)):
            self.bot._handle_dialog("invite", cfg)
            time.sleep(0.1)
            self.bot._handle_dialog("invite", cfg)
        self.assertEqual(len(self.fake.clicks_at), 2)

    def test_each_dialog_has_its_own_cooldown(self):
        with mock.patch.object(self.bot, "_find_dialog",
                               return_value=vision.Match(1, 2, 0.99)):
            self.bot._handle_dialog("invite", dict(self.cfg["invite"],
                                                   template="i.png", cooldown=9))
            # o cooldown do convite nao pode calar a janela de claim
            self.bot._handle_dialog("claim", dict(self.cfg["claim"],
                                                  template="c.png",
                                                  action="key", key="l"))
        self.assertEqual(self.fake.taps, ["l"])

    def test_watch_dialogs_covers_every_feature(self):
        for feature, names in bot_module.DIALOGS_BY_FEATURE.items():
            for name in names:
                self.assertIn(name, self.cfg, f"falta a secao {name} na config")


class ObsoleteConfigTest(unittest.TestCase):
    """Quem ja usava o bot tem o retry gravado no config.json."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.caminho = os.path.join(self.dir, "config.json")
        patch_path = mock.patch.object(config, "CONFIG_PATH", self.caminho)
        patch_dir = mock.patch.object(config, "TEMPLATE_DIR",
                                      os.path.join(self.dir, "templates"))
        patch_path.start()
        patch_dir.start()
        self.addCleanup(patch_path.stop)
        self.addCleanup(patch_dir.stop)

    def _gravar(self, dados):
        import json
        with open(self.caminho, "w", encoding="utf-8") as fh:
            json.dump(dados, fh)

    def test_the_removed_routine_is_swept_from_an_old_file(self):
        self._gravar({
            "features": {"autoclick": True, "retry": True},
            "hotkeys": {"master": "f5", "retry": "f11"},
            "retry": {"enabled": True, "cooldown": 3.0},
        })
        cfg = config.load()
        self.assertNotIn("retry", cfg["features"])
        self.assertNotIn("retry", cfg["hotkeys"])
        self.assertNotIn("retry", cfg)

    def test_the_settings_that_still_exist_survive(self):
        self._gravar({
            "features": {"autoclick": False, "retry": True},
            "hotkeys": {"master": "f4", "retry": "f11"},
            "target_window": "Trove Meu Servidor",
        })
        cfg = config.load()
        self.assertFalse(cfg["features"]["autoclick"])
        self.assertEqual(cfg["hotkeys"]["master"], "f4")
        self.assertEqual(cfg["target_window"], "Trove Meu Servidor")
        # e o que nao foi salvo continua vindo do padrao
        self.assertEqual(cfg["hotkeys"]["panic"],
                         config.DEFAULTS["hotkeys"]["panic"])


class RetryIsGoneTest(unittest.TestCase):
    """O auto retry foi removido a pedido; nao pode voltar por descuido."""

    def test_no_retry_routine_anywhere(self):
        self.assertNotIn("retry", bot_module.DIALOGS_BY_FEATURE)
        self.assertNotIn("retry", bot_module.DIALOG_NAMES)
        self.assertNotIn("retry", config.DEFAULTS["features"])
        self.assertNotIn("retry", config.DEFAULTS["hotkeys"])
        self.assertNotIn("retry", config.DEFAULTS)


class WindowFocusIsGoneTest(unittest.TestCase):
    """A troca de foco por EnumWindows saiu: o app passou a cair depois dela."""

    def test_input_sender_no_longer_forces_focus(self):
        import input_sender
        self.assertFalse(hasattr(input_sender, "focus_window"))
        self.assertFalse(hasattr(input_sender, "find_window"))
        self.assertFalse(hasattr(input_sender, "_ENUM_PROC"))

    def test_reading_the_active_window_still_works(self):
        # essa parte fica: e como o bot sabe se o jogo esta em foco
        import input_sender
        self.assertIsInstance(input_sender.foreground_window_title(), str)


class DepsTest(unittest.TestCase):
    def test_required_packages_are_installed(self):
        self.assertEqual(deps.missing(), [])

    def test_frozen_build_reports_nothing_missing(self):
        with mock.patch.object(deps, "is_frozen", return_value=True):
            self.assertEqual(deps.missing(), [])

    def test_install_is_a_noop_when_frozen(self):
        lines = []
        with mock.patch.object(deps, "is_frozen", return_value=True):
            self.assertEqual(deps.install(lines.append), 0)
        self.assertTrue(lines)


def _fresh_config():
    import copy
    cfg = copy.deepcopy(config.DEFAULTS)
    cfg["skills"] = copy.deepcopy(config.DEFAULT_SKILLS)
    return cfg


if __name__ == "__main__":
    unittest.main(verbosity=2)
