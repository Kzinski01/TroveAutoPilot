"""API exposta a interface React pela ponte do pywebview.

Cada metodo publico daqui vira `window.pywebview.api.<nome>()` no TypeScript
(ver `ui/lib/api.ts`). As chamadas chegam em threads do pywebview, entao tudo
que mexe em estado compartilhado passa por `_lock`.
"""

import collections
import threading
import time

import calibration
import config
import deps
import game_windows
import input_sender
import region_selector
import settings_validation as validation
import vision

LOG_BUFFER = 400
FEATURE_KEYS = ("autoclick", "skills", "potion", "dialogs", "holdkey")
DIALOG_NAMES = ("claim", "invite")


class Api:
    """Ponte entre a interface React e o nucleo Python.

    IMPORTANTE: todo estado interno fica em atributos privados (`_`). O
    pywebview monta a ponte percorrendo os atributos **publicos** deste objeto
    e descendo recursivamente nos que nao sao chamaveis. Se a janela ficasse
    publica, ele acessaria membros COM do WebView2 fora da thread de UI, a
    ponte nao subiria e a janela travaria em "Conectando ao motor do bot".
    Publicos aqui devem ser somente os metodos que o JS chama.
    """

    def __init__(self, cfg, bot, hotkeys):
        self._cfg = cfg
        self._bot = bot
        self._hotkeys = hotkeys
        self._window = None
        self._on_ui_ready = None
        self._telemetry = {"url": "", "token": ""}   # preenchido pelo main

        self._lock = threading.RLock()
        self._capture_lock = threading.Lock()
        self._logs = collections.deque(maxlen=LOG_BUFFER)
        self._pending_logs = collections.deque(maxlen=LOG_BUFFER)
        self._capturing = None

    def bind_window(self, window, on_ui_ready=None):
        """Liga a janela do pywebview (guardada privada, ver docstring)."""
        self._window = window
        self._on_ui_ready = on_ui_ready

    def bind_telemetry(self, url, token):
        """Endereco local de onde a interface le estado e telemetria."""
        self._telemetry = {"url": url, "token": token}

    def get_endpoint(self):
        """Chamado UMA vez pela interface, no arranque.

        Dali em diante ela usa `fetch` nesse endereco em vez da ponte: manter
        4 chamadas por segundo passando pelo pywebview derrubava o processo.
        """
        return dict(self._telemetry)

    # ------------------------------------------------------------- captura
    _SETTLE = 0.35       # tempo para a janela do bot terminar de minimizar

    def _offscreen(self, action):
        """Roda `action` com a janela do bot minimizada.

        Ja houve aqui uma troca de foco por EnumWindows/SetForegroundWindow,
        para garantir que o jogo ficasse na frente. Foi removida: o app passou
        a cair depois dela. Deixe o jogo visivel antes de capturar.
        """
        # A second bridge thread must not restore input during another capture.
        with self._capture_lock:
            return self._capture_offscreen(action)

    def _capture_offscreen(self, action):
        self._bot.input.suspend(True)
        try:
            if self._window is not None:
                self._window.minimize()
            time.sleep(self._SETTLE)
            return action()
        finally:
            try:
                if self._window is not None:
                    self._window.restore()
            finally:
                self._bot.input.suspend(False)

    # ------------------------------------------------------------------ log
    def log(self, message):
        """Recebe as mensagens do bot; a interface consome via `poll`."""
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        with self._lock:
            self._logs.append(line)
            self._pending_logs.append(line)

    def _drain_logs(self):
        with self._lock:
            pending = list(self._pending_logs)
            self._pending_logs.clear()
        return pending

    # ---------------------------------------------------------------- estado
    def _signal_ui_ready(self):
        """Dispara `on_ui_ready` uma unica vez, no primeiro poll.

        O primeiro poll e a prova de que a interface montou e esta rodando —
        o evento `loaded` do pywebview nao dispara com EdgeChromium +
        http_server, entao ele nao serve para tirar a tela de abertura.
        """
        with self._lock:
            callback, self._on_ui_ready = self._on_ui_ready, None
        if callback:
            callback()

    def get_state(self):
        """Estado completo: configuracao + informacoes do ambiente."""
        return {
            "master": self._bot.master,
            "features": {key: bool(self._bot.features.get(key, False))
                         for key in FEATURE_KEYS},
            "hotkeys": dict(self._cfg["hotkeys"]),
            "skills": [dict(skill) for skill in self._cfg["skills"]],
            "dialogs": {name: dict(self._cfg[name]) for name in DIALOG_NAMES},
            "settings": {
                "only_when_focused": self._cfg.get("only_when_focused", True),
                "target_window": self._cfg.get("target_window", "Trove"),
                "extra_windows": self._cfg.get("extra_windows", ""),
                "pause_on_dialog": self._cfg.get("pause_on_dialog", True),
                "autoclick": dict(self._cfg["autoclick"]),
                "potion": dict(self._cfg["potion"]),
                "holdkey": dict(self._cfg["holdkey"]),
            },
            "admin": input_sender.is_admin(),
            "frozen": deps.is_frozen(),
            "missingDeps": deps.missing(),
            "selectedWindow": self._bot.input.selected(),
            "savedWindow": dict(self._cfg.get("selected_window") or {}),
            "inputMode": self._cfg.get("input_mode", "foreground"),
            "secondary": self._bot.secondary.state(),
            "autoSlots": self._bot.slot_locator.state(),
        }

    def poll(self):
        """Dados vivos, chamados a cada tick pela interface."""
        self._signal_ui_ready()
        title = input_sender.foreground_window_title()
        matched = self._bot.input.is_focused()
        return {
            "master": self._bot.master,
            "features": {key: bool(self._bot.features.get(key, False))
                         for key in FEATURE_KEYS},
            "status": dict(self._bot.status),
            "ratios": self._live_ratios(),
            "focus": {"title": title, "matched": matched},
            "logs": self._drain_logs(),
            "capturing": self._capturing,
            "targetReason": self._bot.input.blocked_reason(),
            "secondary": self._bot.secondary.state(),
            "autoSlots": self._bot.slot_locator.state(),
        }

    def _live_ratios(self):
        """Le o que a rotina de skills ja mediu. **Nao captura tela aqui.**

        Cada chamada da ponte roda numa thread nova do pywebview; capturar
        aqui criava um capturador por thread e o processo caia durante a
        coleta de lixo. Quem mede e o `_loop_skills`, que vive o tempo todo.
        """
        ratios = {}
        for skill in self._cfg["skills"]:
            try:
                ratios[skill["id"]] = float(self._bot.status.get(skill["id"]))
            except (TypeError, ValueError):
                ratios[skill["id"]] = None
        return ratios

    # --------------------------------------------------------------- acoes
    def set_master(self, value):
        if type(value) is not bool:
            return False
        self._bot.set_master(value)

    def panic(self):
        self._bot.panic()
        self.save()

    def set_feature(self, key, value):
        if type(value) is not bool:
            return False
        if key in FEATURE_KEYS:
            self._bot.set_feature(key, value)

    def list_windows(self):
        try:
            return game_windows.list_game_windows(self._cfg)
        except OSError as exc:
            self.log(f"[Bot] Falha ao listar janelas: {exc}")
            return []

    def select_window(self, candidate):
        with self._bot._lock:
            return self._select_primary_window(candidate)

    def _select_primary_window(self, candidate):
        if not isinstance(candidate, dict):
            return False
        # Re-enumerate: a stale UI row must not select a recycled HWND.
        current = next((item for item in self.list_windows()
                        if game_windows.same_identity(candidate, item)), None)
        if current is None:
            self.log("[Bot] Input ignorado por segurança: janela da lista mudou; atualize.")
            return False
        if self._bot.secondary.conflicts_with(current):
            self.log("[Bot] Seleção recusada: o Jogo 1 não pode usar o processo do Jogo 2.")
            return False
        self._bot.panic()
        if not self._bot.input.select(current):
            return False
        self._bot.reload_templates()
        self._bot.slot_locator.invalidate()
        self.save()
        return True

    def select_secondary_window(self, candidate):
        if not isinstance(candidate, dict):
            return False
        current = next((item for item in self.list_windows()
                        if game_windows.same_identity(candidate, item)), None)
        if current is None:
            self.log("[Bot][Jogo 2] Seleção recusada: janela da lista mudou; atualize.")
            return False
        with self._bot._lock:
            if not self._bot.secondary.select(current):
                return False
            self.save()
            return True

    def update_secondary(self, patch):
        if not isinstance(patch, dict) or not self._bot.secondary.update(patch):
            return False
        self.save()
        return True

    def set_secondary_enabled(self, enabled):
        if type(enabled) is not bool or not self._bot.secondary.set_enabled(enabled):
            return False
        self.save()
        return True

    def set_input_mode(self, mode):
        self._bot.panic()
        if not self._bot.input.set_mode(mode):
            return False
        self.save()
        return True

    # -------------------------------------------------------------- atalhos
    def capture_hotkey(self, name):
        """Espera a proxima combinacao e a associa a `name`."""
        if not isinstance(name, str) or name not in config.DEFAULTS["hotkeys"]:
            return False
        self._capturing = name
        self._hotkeys.capture_next(lambda combo: self._finish_capture(name, combo))

    def _finish_capture(self, name, combo):
        self._capturing = None
        if combo in ("escape", "esc"):
            self.clear_hotkey(name)
            return
        if any(other != name and saved == combo
               for other, saved in self._cfg["hotkeys"].items()):
            self.log("Atalho recusado: combinação já usada por outro controle.")
            return
        self._cfg["hotkeys"][name] = combo
        self.apply_hotkeys()
        self.log(f"Atalho '{name}' = {combo}")
        self.save()

    def clear_hotkey(self, name):
        if not isinstance(name, str) or name not in config.DEFAULTS["hotkeys"]:
            return False
        self._capturing = None
        self._hotkeys.cancel_capture()
        self._cfg["hotkeys"][name] = ""
        self.apply_hotkeys()
        self.log(f"Atalho '{name}' removido.")
        self.save()

    def apply_hotkeys(self):
        bindings = {
            self._cfg["hotkeys"].get("master", ""): self._bot.toggle_master,
        }
        for key in FEATURE_KEYS:
            combo = self._cfg["hotkeys"].get(key, "")
            if combo:
                bindings[combo] = lambda k=key: self._bot.toggle_feature(k)
        # Old config files may contain duplicates: panic always wins.
        bindings[self._cfg["hotkeys"].get("panic", "")] = self._bot.panic
        self._hotkeys.set_bindings(bindings)

    # --------------------------------------------------------------- skills
    def _skill(self, skill_id):
        for skill in self._cfg["skills"]:
            if skill["id"] == skill_id:
                return skill
        return None

    def update_skill(self, skill_id, patch):
        skill = self._skill(skill_id)
        if skill is None:
            return
        with self._bot._lock:
            checked = self._validate_patch(patch, validation.SKILL)
            if checked is None:
                return False
            skill.update(checked)
            self.save()
        return True

    def _validate_patch(self, patch, schema):
        try:
            return validation.patch(patch, schema)
        except ValueError as exc:
            self.log(f"[Bot] Ajuste recusado: {exc}.")
            return None

    def select_skill_region(self, skill_id):
        skill = self._skill(skill_id)
        if skill is None:
            return
        def pick():
            region = region_selector.select_region(f"Selecione o ícone da skill {skill['name']}")
            return region, self._bot.input.bind_region(region) if region else None

        region, binding = self._offscreen(pick)
        if not region or not binding:
            if region:
                self.log("[Bot] Região ignorada: selecione o ícone na instância escolhida e visível.")
            return
        with self._bot._lock:
            self._bot.slot_locator.set_enabled(False)
            skill.update(region=list(region), window_region=binding, auto_sampling=False,
                         ready_score=0.0, cooldown_score=0.0)
        self.log(f"Skill {skill['name']}: área {region}. "
                 "Recapture 'Pronta' e 'Em cooldown'.")
        self.save()

    def calibrate_skill(self, skill_id, state):
        if state not in (calibration.READY, calibration.COOLDOWN):
            self.log("[Bot] Calibração recusada: estado inválido.")
            return False
        skill = self._skill(skill_id)
        if skill is None:
            return
        if not skill.get("region"):
            self.log(f"Skill {skill['name']}: defina a área primeiro.")
            return
        def sample():
            if not self._bot.slot_locator.ready_for(skill):
                self.log("[Bot][Slots] Calibração ignorada: aguarde a localização dos slots.")
                return []
            region = self._bot.input.skill_region(skill)
            if not region:
                self.log("[Bot] Calibração ignorada: recapture a área na janela selecionada em foco.")
                return []
            scores = calibration.sample_scores(region)
            # A changed/occluded window invalidates this calibration sample.
            return scores if self._bot.input.skill_region(skill) == region else []

        scores = self._offscreen(sample)
        with self._bot._lock:
            for line in calibration.apply_skill_sample(skill, state, scores):
                self.log(line)
            self.save()

    def set_auto_slots(self, enabled):
        if type(enabled) is not bool:
            return False
        self._bot.slot_locator.set_enabled(enabled)
        self.save()
        return True

    def locate_skills(self):
        if not self._cfg["auto_slots"]["enabled"]:
            self.log("[Bot][Slots] Ative a localização automática primeiro.")
            return False
        return self._offscreen(lambda: self._bot.slot_locator.update(force=True))

    # -------------------------------------------------------------- janelas
    def update_dialog(self, name, patch):
        if name in DIALOG_NAMES:
            checked = self._validate_patch(patch, validation.DIALOG)
            if checked is None:
                return False
            with self._bot._lock:
                self._cfg[name].update(checked)
                self.save()
            return True

    def capture_dialog_template(self, name):
        """Recorta um trecho da janela aberta e guarda como template."""
        if name not in DIALOG_NAMES:
            return

        region, image = self._offscreen(self._pick_region_and_grab)
        if not region or not self._template_is_usable(name, image):
            return

        cfg = self._cfg[name]
        cfg["template"] = calibration.save_template(name, image)
        cfg["template_region"] = list(region)
        cfg["click_offset"] = [0, 0]
        self._bot.reload_templates()
        self.log(f"{name}: template salvo em templates/{cfg['template']}")
        self.save()

    def _pick_region_and_grab(self):
        """Pede a area ao usuario e ja captura, com a janela fora da frente."""
        region = region_selector.select_region(
            "Selecione um trecho único da janela (com ela aberta)")
        if not region or not self._bot.input.bind_region(region):
            self.log("[Bot] Template ignorado: área fora da instância selecionada/visível.")
            return None, None
        return region, vision.grab(region)

    def _template_is_usable(self, name, image):
        if image is None:
            self.log(f"{name}: falha ao capturar a tela.")
            return False
        if not vision.has_texture(image):
            self.log(f"{name}: recorte liso demais, casaria em qualquer lugar. "
                     "Pegue uma área com texto ou ícone.")
            return False
        return True

    def set_dialog_click_point(self, name):
        if name not in DIALOG_NAMES:
            return
        cfg = self._cfg[name]
        if not cfg.get("template_region"):
            self.log(f"{name}: capture a janela primeiro.")
            return
        point = self._offscreen(lambda: region_selector.select_point(
            "Clique no ponto que o bot deve apertar"))
        if not point:
            return
        cfg["click_offset"] = calibration.click_offset(cfg["template_region"], point)
        self.log(f"{name}: offset de clique {cfg['click_offset']}")
        self.save()

    # -------------------------------------------------------------- ajustes
    def update_settings(self, patch):
        try:
            checked = validation.settings(patch)
        except ValueError as exc:
            self.log(f"[Bot] Ajuste recusado: {exc}.")
            return False
        with self._bot._lock:
            for key, value in checked.items():
                if key in validation.SECTIONS:
                    self._cfg[key].update(value)
                else:
                    self._cfg[key] = value
            self._cfg["only_when_focused"] = True
            self.save()
        return True

    def install_deps(self):
        deps.install(self.log, config.BASE_DIR)

    def diagnose(self):
        """Responde 'por que nada acontece?' com dados concretos."""
        self.log("-" * 54)
        self._diagnose_environment()
        self._diagnose_routines()
        self._diagnose_skills()
        self.log("Dica: ligue pelo atalho com o jogo em foco, não pela janela.")
        self.log("-" * 54)

    def _diagnose_environment(self):
        admin = input_sender.is_admin()
        self.log(f"Bot como administrador: {'sim' if admin else 'NÃO'}")
        if not admin:
            self.log("  ! Se o Trove roda como admin, o Windows descarta nosso")
            self.log("  ! input em silêncio. Rode o bot como administrador.")
        filtro = "ligado" if self._cfg.get("only_when_focused") else "desligado"
        self.log(f"Janela em foco: {input_sender.foreground_window_title()!r}")
        self.log(f"Filtro de foco: {self._cfg.get('target_window')!r} ({filtro})")
        self.log(f"[Bot] Instância: {self._bot.input.selected()}")
        self.log(f"[Bot] Backend: {self._cfg.get('input_mode', 'foreground')}")
        self.log(f"[Bot] Segurança: {self._bot.input.blocked_reason() or 'destino válido'}")

    def _diagnose_routines(self):
        self.log(f"Master: {'ligado' if self._bot.master else 'DESLIGADO'}")
        for key in FEATURE_KEYS:
            motivo = self._bot.blocked_reason(key)
            estado = "agindo" if motivo is None else f"bloqueado -> {motivo}"
            self.log(f"  {key}: {estado}")
        secondary = self._bot.secondary.state()
        self.log(f"[Bot][Jogo 2] Tecla periódica: {secondary['status']}; "
                 f"tecla={secondary['key']!r}; intervalo={secondary['interval']}s; "
                 f"destino={secondary['selectedWindow']}")

    def _diagnose_skills(self):
        medidos = self._live_ratios()
        for skill in self._cfg["skills"]:
            ratio = medidos.get(skill["id"])
            medido = "-" if ratio is None else f"{ratio:.2f}"
            self.log(f"  skill {skill['name']}: ratio={medido} "
                     f"limite={skill.get('threshold')} tecla={skill.get('key')!r}")

    def save(self):
        with self._bot._lock, self._lock:
            config.save(self._cfg)
