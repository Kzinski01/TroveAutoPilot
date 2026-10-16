"""Testes da API exposta a interface React (ponte do pywebview)."""

import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import api as api_module
from fake_target import FakeTargetMixin
import bot as bot_module
import config
import hotkeys


def fresh_config():
    cfg = copy.deepcopy(config.DEFAULTS)
    cfg["skills"] = copy.deepcopy(config.DEFAULT_SKILLS)
    return cfg


class FakeInput(FakeTargetMixin):
    def __init__(self, window="Trove"):
        self.window = window
        self.taps = []
        self.clicks = []
        self.clicks_at = []
        self.focused = []
        self.down = []
        self.up = []

    def foreground_window_title(self):
        return self.window

    def is_admin(self):
        return True

    def tap(self, key, hold=0.0):
        self.taps.append(key)
        return True

    def click(self, button="left", hold=0.0):
        self.clicks.append(button)

    def click_at(self, x, y, button="left", restore=True):
        self.clicks_at.append((x, y))

    def mouse_down(self, button="left"):
        self.down.append(button)

    def mouse_up(self, button="left"):
        self.up.append(button)


class FakeWindow:
    def __init__(self):
        self.minimized = 0
        self.restored = 0

    def minimize(self):
        self.minimized += 1

    def restore(self):
        self.restored += 1


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.cfg = fresh_config()
        self.fake_input = FakeInput()
        for module in (bot_module, api_module):
            patcher = mock.patch.object(module, "input_sender", self.fake_input) \
                if module is api_module else mock.patch.object(module, "TargetedInput",
                    side_effect=lambda cfg, log: self.fake_input.configure(cfg))
            patcher.start()
            self.addCleanup(patcher.stop)

        self.saves = []
        patcher = mock.patch.object(config, "save",
                                    side_effect=lambda c: self.saves.append(c))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.bot = bot_module.Bot(self.cfg)
        self.hotkeys = hotkeys.HotkeyManager()
        self.api = api_module.Api(self.cfg, self.bot, self.hotkeys)
        self.bot.set_logger(self.api.log)
        self.window = FakeWindow()
        self.api.bind_window(self.window)


class BridgeSurfaceTest(ApiTestCase):
    """A ponte so pode expor metodos - nunca objetos internos.

    O pywebview percorre os atributos publicos do js_api e desce nos que nao
    sao chamaveis. Expor a janela fazia ele tocar membros COM do WebView2 fora
    da thread de UI: a ponte nao subia e o app travava em "Conectando ao motor
    do bot", com a janela como "Nao esta respondendo".
    """

    def _publicos(self):
        return [nome for nome in dir(self.api) if not nome.startswith("_")]

    def test_only_methods_are_public(self):
        import inspect
        nao_metodos = [nome for nome in self._publicos()
                       if not inspect.ismethod(getattr(self.api, nome))]
        self.assertEqual(nao_metodos, [], f"atributos publicos vazariam: {nao_metodos}")

    def test_window_is_not_reachable_from_the_bridge(self):
        for nome in self._publicos():
            self.assertIsNot(getattr(self.api, nome), self.window)

    def test_pywebview_would_not_descend_into_anything(self):
        """Replica a regra do get_functions do pywebview."""
        import inspect
        descidas = []
        for nome in self._publicos():
            attr = getattr(self.api, nome)
            if inspect.ismethod(attr) or inspect.isfunction(attr):
                continue
            if isinstance(attr, object) and not callable(attr) and hasattr(attr, "__module__"):
                descidas.append(nome)
        self.assertEqual(descidas, [], f"pywebview desceria em: {descidas}")

    def test_the_methods_the_ui_needs_are_still_exposed(self):
        for metodo in ("get_state", "poll", "set_master", "set_feature",
                       "capture_hotkey", "clear_hotkey", "update_skill",
                       "select_skill_region", "calibrate_skill", "update_dialog",
                       "capture_dialog_template", "set_dialog_click_point",
                       "update_settings", "diagnose", "install_deps"):
            self.assertIn(metodo, self._publicos(), f"{metodo} sumiu da ponte")


class TelemetryChannelTest(ApiTestCase):
    """A leitura de estado nao pode passar pela ponte do pywebview.

    Cada chamada da ponte cria uma thread e delegates .NET (pythonnet). Com a
    interface lendo 4x por segundo, o processo morria durante a coleta de lixo
    com STATUS_BREAKPOINT. A leitura vai por um servidor HTTP local.
    """

    def test_endpoint_is_empty_until_bound(self):
        self.assertEqual(self.api.get_endpoint(), {"url": "", "token": ""})

    def test_endpoint_carries_url_and_token(self):
        self.api.bind_telemetry("http://127.0.0.1:1234", "segredo")
        self.assertEqual(self.api.get_endpoint(),
                         {"url": "http://127.0.0.1:1234", "token": "segredo"})

    def test_endpoint_is_a_copy(self):
        self.api.bind_telemetry("http://127.0.0.1:1234", "segredo")
        self.api.get_endpoint()["token"] = "alterado"
        self.assertEqual(self.api.get_endpoint()["token"], "segredo")

    def test_server_serves_the_same_data_as_the_bridge(self):
        import json
        import urllib.request
        import telemetry_server

        url, token, servidor = telemetry_server.start({
            "poll": self.api.poll,
            "state": self.api.get_state,
        })
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)

        with urllib.request.urlopen(f"{url}/state?t={token}", timeout=5) as r:
            pelo_http = json.loads(r.read())
        self.assertEqual(set(pelo_http), set(self.api.get_state()))

    def test_server_refuses_a_wrong_token(self):
        import urllib.error
        import urllib.request
        import telemetry_server

        url, _token, servidor = telemetry_server.start({"poll": self.api.poll})
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)

        with self.assertRaises(urllib.error.HTTPError) as erro:
            urllib.request.urlopen(f"{url}/poll?t=errado", timeout=5)
        self.assertEqual(erro.exception.code, 403)
        erro.exception.close()

    def test_server_only_listens_on_localhost(self):
        import telemetry_server
        url, _token, servidor = telemetry_server.start({"poll": self.api.poll})
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        self.assertTrue(url.startswith("http://127.0.0.1:"), url)

    def test_one_connection_serves_many_polls(self):
        """Sem keep-alive era uma thread por consulta, 4 por segundo."""
        import http.client
        import telemetry_server

        url, token, servidor = telemetry_server.start({"poll": self.api.poll})
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)

        conexao = http.client.HTTPConnection(url.replace("http://", ""))
        self.addCleanup(conexao.close)
        for _ in range(20):
            conexao.request("GET", f"/poll?t={token}")
            resposta = conexao.getresponse()
            resposta.read()
            self.assertEqual(resposta.status, 200)
            # se o servidor fechasse, a proxima consulta abriria outra conexao
            self.assertNotEqual(resposta.getheader("Connection"), "close")


class StateTest(ApiTestCase):
    def test_get_state_has_every_section(self):
        state = self.api.get_state()
        for key in ("master", "features", "hotkeys", "skills", "dialogs",
                    "settings", "admin", "frozen", "missingDeps"):
            self.assertIn(key, state)

    def test_get_state_is_json_safe(self):
        import json
        json.dumps(self.api.get_state())      # nao pode levantar

    def test_state_exposes_every_feature_flag(self):
        features = self.api.get_state()["features"]
        self.assertEqual(set(features), set(api_module.FEATURE_KEYS))

    def test_settings_mirror_the_config(self):
        self.cfg["target_window"] = "OutroJogo"
        self.cfg["autoclick"]["cps"] = 25.0
        settings = self.api.get_state()["settings"]
        self.assertEqual(settings["target_window"], "OutroJogo")
        self.assertEqual(settings["autoclick"]["cps"], 25.0)

    def test_state_is_a_copy_not_a_live_reference(self):
        state = self.api.get_state()
        state["skills"][0]["name"] = "alterado"
        self.assertNotEqual(self.cfg["skills"][0]["name"], "alterado")


class PollTest(ApiTestCase):
    def test_poll_is_json_safe(self):
        import json
        json.dumps(self.api.poll())

    def test_poll_reports_focus_match(self):
        self.fake_input.window = "Trove"
        self.assertTrue(self.api.poll()["focus"]["matched"])
        self.fake_input.window = "Bloco de Notas"
        self.assertFalse(self.api.poll()["focus"]["matched"])

    def test_focus_still_requires_selected_window_when_filter_is_off(self):
        self.cfg["only_when_focused"] = False
        self.fake_input.window = "Qualquer coisa"
        self.assertFalse(self.api.poll()["focus"]["matched"])

    def test_logs_are_delivered_once(self):
        self.api.log("primeira")
        self.assertEqual(self.api.poll()["logs"][-1][-8:], "primeira")
        self.assertEqual(self.api.poll()["logs"], [])

    def test_log_lines_carry_a_timestamp(self):
        self.api.log("oi")
        line = self.api.poll()["logs"][0]
        self.assertRegex(line, r"^\[\d{2}:\d{2}:\d{2}\] oi$")

    def test_bot_events_reach_the_log(self):
        self.bot.set_master(True)
        self.assertTrue(any("Master" in line for line in self.api.poll()["logs"]))

    def test_poll_never_captures_the_screen(self):
        """Isto derrubava o processo.

        Cada chamada da ponte roda numa thread nova do pywebview. Capturar aqui
        criava um capturador por thread, que so era liberado na coleta de lixo
        - e o processo morria durante ela (STATUS_BREAKPOINT).
        """
        self.cfg["skills"][0].update(region=[0, 0, 10, 10], ready_score=0.5)
        with mock.patch.object(api_module.vision, "grab") as capturou,              mock.patch.object(api_module.vision, "grab_screen") as capturou_tela,              mock.patch.object(api_module.vision, "skill_ratio") as mediu:
            for _ in range(20):
                self.api.poll()
        capturou.assert_not_called()
        capturou_tela.assert_not_called()
        mediu.assert_not_called()

    def test_diagnose_never_captures_the_screen(self):
        with mock.patch.object(api_module.vision, "grab") as capturou,              mock.patch.object(api_module.vision, "skill_ratio") as mediu:
            self.api.diagnose()
        capturou.assert_not_called()
        mediu.assert_not_called()

    def test_ratios_come_from_what_the_bot_measured(self):
        self.bot.status["m2"] = "0.87"
        self.assertAlmostEqual(self.api.poll()["ratios"]["m2"], 0.87)

    def test_ratios_come_from_the_bot_while_running(self):
        self.bot.master = True
        self.bot.status["m2"] = "0.93"
        self.assertAlmostEqual(self.api.poll()["ratios"]["m2"], 0.93)

    def test_first_poll_signals_that_the_ui_is_up(self):
        # e assim que a tela de abertura sai; sem isso ela ficaria presa
        avisos = []
        self.api._on_ui_ready = lambda: avisos.append(True)
        self.api.poll()
        self.assertEqual(avisos, [True])

    def test_ui_ready_fires_only_once(self):
        avisos = []
        self.api._on_ui_ready = lambda: avisos.append(True)
        self.api.poll()
        self.api.poll()
        self.api.poll()
        self.assertEqual(avisos, [True])

    def test_poll_works_without_a_ui_ready_callback(self):
        self.assertIsNone(self.api._on_ui_ready)
        self.api.poll()          # nao pode levantar

    def test_non_numeric_status_becomes_null(self):
        self.bot.master = True
        self.bot.status["m2"] = "sem calibracao"
        self.assertIsNone(self.api.poll()["ratios"]["m2"])


class ControlTest(ApiTestCase):
    def test_set_master_drives_the_bot(self):
        self.api.set_master(True)
        self.assertTrue(self.bot.master)
        self.api.set_master(False)
        self.assertFalse(self.bot.master)

    def test_set_feature_updates_the_flag(self):
        self.api.set_feature("potion", False)
        self.assertFalse(self.bot.features["potion"])

    def test_unknown_feature_is_ignored(self):
        self.api.set_feature("inexistente", True)
        self.assertNotIn("inexistente", self.bot.features)


class HotkeyApiTest(ApiTestCase):
    def test_capture_marks_the_pending_name(self):
        self.api.capture_hotkey("master")
        self.assertEqual(self.api.poll()["capturing"], "master")

    def test_finishing_capture_stores_the_combo(self):
        self.api.capture_hotkey("potion")
        self.hotkeys._on_press(hotkeys.keyboard.Key.f4)
        self.assertEqual(self.cfg["hotkeys"]["potion"], "f4")
        self.assertIsNone(self.api.poll()["capturing"])
        self.assertTrue(self.saves)

    def test_escape_clears_the_hotkey(self):
        self.api.capture_hotkey("potion")
        self.hotkeys._on_press(hotkeys.keyboard.Key.esc)
        self.assertEqual(self.cfg["hotkeys"]["potion"], "")

    def test_clear_hotkey_removes_the_binding(self):
        self.api.clear_hotkey("master")
        self.assertEqual(self.cfg["hotkeys"]["master"], "")

    def test_apply_hotkeys_registers_master_and_features(self):
        self.api.apply_hotkeys()
        combos = set(self.hotkeys._bindings)
        self.assertIn("f5", combos)      # master
        self.assertIn("f6", combos)      # autoclick
        self.assertIn("f12", combos)     # panico

    def test_master_hotkey_toggles_the_bot(self):
        self.api.apply_hotkeys()
        self.hotkeys._bindings["f5"]()
        self.assertTrue(self.bot.master)


class SkillApiTest(ApiTestCase):
    def test_update_skill_writes_and_saves(self):
        self.api.update_skill("s1", {"key": "3", "enabled": False})
        skill = self.cfg["skills"][1]
        self.assertEqual(skill["key"], "3")
        self.assertFalse(skill["enabled"])
        self.assertTrue(self.saves)

    def test_update_unknown_skill_is_ignored(self):
        self.api.update_skill("nao-existe", {"key": "9"})
        self.assertEqual(self.saves, [])

    def test_select_region_hides_the_window_and_resets_calibration(self):
        self.cfg["skills"][0].update(ready_score=0.9, cooldown_score=0.4)
        with mock.patch.object(api_module.region_selector, "select_region",
                               return_value=(1, 2, 3, 4)):
            self.api.select_skill_region("m2")
        skill = self.cfg["skills"][0]
        self.assertEqual(skill["region"], [1, 2, 3, 4])
        self.assertEqual(skill["ready_score"], 0.0)
        self.assertEqual(self.window.minimized, 1)
        self.assertEqual(self.window.restored, 1)

    def test_capture_never_forces_the_focus(self):
        """A troca de foco saiu: o app passou a cair depois dela.

        Agora a captura so esconde a janela do bot; quem deixa o jogo visivel
        e o usuario.
        """
        self.cfg["target_window"] = "Trove"
        with mock.patch.object(api_module.region_selector, "select_region",
                               return_value=(1, 2, 3, 4)):
            self.api.select_skill_region("m2")
        self.assertEqual(self.fake_input.focused, [])

    def test_cancelled_selection_changes_nothing(self):
        with mock.patch.object(api_module.region_selector, "select_region",
                               return_value=None):
            self.api.select_skill_region("m2")
        self.assertIsNone(self.cfg["skills"][0]["region"])

    def test_calibration_needs_a_region(self):
        with mock.patch.object(api_module.calibration, "sample_scores") as sampler:
            self.api.calibrate_skill("m2", "ready")
        sampler.assert_not_called()

    def test_calibration_stores_the_measurements_only(self):
        skill = self.cfg["skills"][0]
        skill["region"] = [0, 0, 10, 10]
        skill["threshold"] = 0.9              # valor escolhido pelo usuario
        with mock.patch.object(api_module.calibration, "sample_scores",
                               return_value=[0.52]):
            self.api.calibrate_skill("m2", "ready")
        with mock.patch.object(api_module.calibration, "sample_scores",
                               return_value=[0.30]):
            self.api.calibrate_skill("m2", "cooldown")
        self.assertAlmostEqual(skill["ready_score"], 0.52)
        self.assertAlmostEqual(skill["cooldown_score"], 0.30)
        self.assertEqual(skill["threshold"], 0.9)   # intocado

    def test_threshold_is_set_by_the_user(self):
        self.api.update_skill("m2", {"threshold": 0.66})
        self.assertEqual(self.cfg["skills"][0]["threshold"], 0.66)

    def test_window_is_restored_even_if_capture_fails(self):
        self.cfg["skills"][0]["region"] = [0, 0, 10, 10]
        with mock.patch.object(api_module.calibration, "sample_scores",
                               side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.api.calibrate_skill("m2", "ready")
        self.assertEqual(self.window.restored, 1)


class DialogApiTest(ApiTestCase):
    def test_update_dialog_writes_and_saves(self):
        self.api.update_dialog("claim", {"action": "key", "key": "l"})
        self.assertEqual(self.cfg["claim"]["action"], "key")
        self.assertTrue(self.saves)

    def test_unknown_dialog_is_ignored(self):
        self.api.update_dialog("inexistente", {"action": "key"})
        self.assertEqual(self.saves, [])

    def test_capture_rejects_a_flat_region(self):
        flat = np.full((30, 30, 3), 90, dtype=np.uint8)
        with mock.patch.object(api_module.region_selector, "select_region",
                               return_value=(0, 0, 30, 30)), \
             mock.patch.object(api_module.vision, "grab", return_value=flat):
            self.api.capture_dialog_template("claim")
        self.assertEqual(self.cfg["claim"]["template"], "")

    def test_capture_stores_a_textured_template(self):
        rng = np.random.default_rng(3)
        patch = rng.integers(0, 256, (24, 24, 3), dtype=np.uint8)
        with mock.patch.object(api_module.region_selector, "select_region",
                               return_value=(5, 6, 24, 24)), \
             mock.patch.object(api_module.vision, "grab", return_value=patch), \
             mock.patch.object(api_module.calibration, "save_template",
                               return_value="claim.png"):
            self.api.capture_dialog_template("claim")
        self.assertEqual(self.cfg["claim"]["template"], "claim.png")
        self.assertEqual(self.cfg["claim"]["template_region"], [5, 6, 24, 24])

    def test_click_point_requires_a_template(self):
        with mock.patch.object(api_module.region_selector, "select_point") as picker:
            self.api.set_dialog_click_point("claim")
        picker.assert_not_called()

    def test_click_point_is_stored_as_offset(self):
        self.cfg["claim"]["template_region"] = [100, 200, 50, 20]
        with mock.patch.object(api_module.region_selector, "select_point",
                               return_value=(145, 205)):
            self.api.set_dialog_click_point("claim")
        self.assertEqual(self.cfg["claim"]["click_offset"], [20, -5])


class SettingsApiTest(ApiTestCase):
    def test_nested_sections_are_merged_not_replaced(self):
        self.api.update_settings({"autoclick": {"cps": 20.0}})
        self.assertEqual(self.cfg["autoclick"]["cps"], 20.0)
        self.assertIn("button", self.cfg["autoclick"])   # nao perdeu as outras

    def test_top_level_flags_are_written(self):
        self.api.update_settings({"only_when_focused": False,
                                  "target_window": "Jogo"})
        self.assertTrue(self.cfg["only_when_focused"])
        self.assertEqual(self.cfg["target_window"], "Jogo")

    def test_unknown_keys_are_ignored(self):
        self.api.update_settings({"algo_estranho": 1})
        self.assertNotIn("algo_estranho", self.cfg)

    def test_diagnose_writes_a_report(self):
        self.api.diagnose()
        text = "\n".join(self.api.poll()["logs"])
        self.assertIn("administrador", text)
        self.assertIn("Master", text)
        for key in api_module.FEATURE_KEYS:
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
