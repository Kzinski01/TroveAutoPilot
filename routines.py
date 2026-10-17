"""Attack routines sharing the Bot lifecycle and selected input boundary."""

import time

import vision

IDLE_SLEEP = 0.10          # espera quando a rotina esta bloqueada
BUSY_SLEEP = 0.05          # espera curta dentro de uma rotina ativa
DIALOG_IDLE_SLEEP = 0.30
CLICK_HOLD = 0.015         # tempo de botao pressionado no spam de cliques
SKILL_GAP = 0.03           # respiro entre duas skills no mesmo ciclo
# Com a rotina parada ainda medimos os icones, mais devagar, so para a tela de
# calibracao mostrar o ratio ao vivo. A interface apenas le esse valor: medir
# do lado dela mandaria a interface disputar a thread de captura a cada quadro.
IDLE_MEASURE_INTERVAL = 0.5
DIALOG_SETTLE = 0.25       # espera apos agir sobre uma janela
MAX_CPS = 40.0
# join curto: quem chama o shutdown e a thread da interface ao fechar a janela.
# As rotinas sao daemon e checam `_stop` a cada ciclo (<= 0,3s), entao esperar
# mais so faria a janela parecer travada ao fechar.
JOIN_TIMEOUT = 0.3
MAX_HOLD = 60.0            # teto do "segurar tecla", para nao travar a tecla
HOLD_TICK = 0.05           # granularidade da contagem enquanto segura
# respiro minimo entre soltar e apertar de novo: sem ele o jogo pode nao
# registrar a soltura e entender tudo como um unico toque continuo
KEY_RELEASE_GAP = 0.05

# Quais janelas cada rotina vigia.
DIALOGS_BY_FEATURE = {
    "dialogs": ("claim", "invite"),
}
DIALOG_NAMES = tuple(nome for nomes in DIALOGS_BY_FEATURE.values() for nome in nomes)

# Rotinas que rodam sozinhas: nao passam pelo master, basta o switch delas.
# Continuam respeitando o foco do jogo e o panico, que sao travas de seguranca.
INDEPENDENT_FEATURES = frozenset({"holdkey"})


def clamp_hold(duration):
    """Mantem o tempo de "segurar tecla" numa faixa sensata."""
    try:
        value = float(duration)
    except (TypeError, ValueError):
        return 3.0
    return max(0.1, min(value, MAX_HOLD))


class AutoclickRoutine:
    """Autoclick scheduling; uses the Bot configuration and input boundary."""

    def _loop_autoclick(self):
        while not self._stop.is_set():
            if not self._active("autoclick"):
                self._release_mouse()
                time.sleep(BUSY_SLEEP)
                continue
            if self._blocked_by_dialog():
                self._release_mouse()
                self.status["autoclick"] = "pausado (janela)"
                time.sleep(BUSY_SLEEP)
                continue

            cfg = self.cfg["autoclick"]
            button = cfg.get("button", "left")
            if cfg.get("mode", "click") == "hold":
                self._hold_mouse(button)
            else:
                self._spam_click(button, cfg.get("cps", 12.0))

    def _hold_mouse(self, button):
        if not self._mouse_held:
            if self.input.mouse_down(button) is False:
                self.status["autoclick"] = "input bloqueado"
                time.sleep(BUSY_SLEEP)
                return
            self._mouse_held = True
            self._held_button = button
            self._log(f"Auto clique: {button} pressionado (modo segurar).")
        self.status["autoclick"] = "segurando"
        time.sleep(BUSY_SLEEP)

    def _spam_click(self, button, cps):
        self._release_mouse()
        rate = max(1.0, min(float(cps), MAX_CPS))
        if self.input.click(button, hold=CLICK_HOLD) is False:
            self.status["autoclick"] = "input bloqueado"
            time.sleep(BUSY_SLEEP)
            return
        self.status["autoclick"] = f"{rate:.0f} cps"
        time.sleep(max(0.0, 1.0 / rate - CLICK_HOLD))

    def _release_mouse(self):
        if not self._mouse_held:
            return
        self._mouse_held = False
        button, self._held_button = self._held_button or "left", None
        try:
            if self.input.mouse_up(button) is not False:
                self._log("Auto clique: botão solto.")
        except OSError as exc:
            # nao da para reerguer no shutdown, mas silenciar seria pior:
            # falhar aqui significa que o botao ficou preso no jogo
            self._log(f"ATENCAO: falha ao soltar o botao {button} ({exc}). "
                      "Se o jogo continuar clicando, clique uma vez na tela.")


class SkillRoutine:
    """Skill scheduling; uses the Bot configuration and input boundary."""

    def _loop_skills(self):
        while not self._stop.is_set():
            self.slot_locator.update()
            if not self._active("skills") or self._blocked_by_dialog():
                self._measure_skills()
                time.sleep(IDLE_MEASURE_INTERVAL)
                continue
            for skill in self.cfg["skills"]:
                if self._try_skill(skill):
                    time.sleep(SKILL_GAP)
            time.sleep(float(self.cfg.get("scan_interval", IDLE_SLEEP)))

    def _measure_skills(self):
        """Atualiza os ratios sem agir, para a tela de calibracao."""
        for skill in self.cfg["skills"]:
            if not skill.get("region"):
                continue
            ratio = self._skill_ratio(skill)
            self.status[skill["id"]] = ((self._skill_reading_message(skill) or "sem calibracao") if ratio is None
                                        else f"{ratio:.2f}")

    def _try_skill(self, skill):
        """Usa a skill se ela estiver pronta. Devolve True se disparou."""
        if not skill.get("enabled", True) or not skill.get("region"):
            return False

        automatic = self.cfg.get("auto_slots", {}).get("enabled", False)
        ratio = self._skill_ratio(skill)
        if ratio is None:
            self.status[skill["id"]] = self._skill_reading_message(skill) or "sem calibração"
            return False

        self.status[skill["id"]] = f"{ratio:.2f}"
        if not automatic and ratio < float(skill.get("threshold", 0.80)):
            return False

        now = time.time()
        if now < self._next_skill_at.get(skill["id"], 0.0):
            return False

        with self._lock:
            if automatic != self.cfg.get("auto_slots", {}).get("enabled", False):
                return False
            if automatic and (self.blocked_reason("skills") is not None
                              or not self.slot_locator.ready_for(skill)
                              or not self.skill_monitor.ready(skill, self.input.selected())):
                return False
            if automatic and not self.input.skill_region(skill):
                self.skill_monitor.pause(skill, self.input.skill_blocked_reason(skill))
                return False
            if self._press(skill.get("key", "")) is False:
                return False
            if automatic:
                self.skill_monitor.sent(skill)
        self._next_skill_at[skill["id"]] = now + float(skill.get("min_interval", 0.6))
        self._log(f"Skill {skill['name']}: comando enviado (ratio {ratio:.2f}).")
        return True

    def _skill_ratio(self, skill):
        if self.cfg.get("auto_slots", {}).get("enabled", False):
            return self._adaptive_skill_ratio(skill)
        if not self.slot_locator.ready_for(skill):
            return None
        selected = self.input.selected()
        region = self.input.skill_region(skill)
        if not region:
            return None
        ratio = vision.skill_ratio({**skill, "region": region})
        if (not self.slot_locator.ready_for(skill) or self.input.selected() != selected
                or self.input.skill_region(skill) != region):
            return None
        return ratio

    def _skill_reading_message(self, skill):
        if self.cfg.get("auto_slots", {}).get("enabled", False):
            return self.skill_monitor.message(skill)
        return self.input.skill_blocked_reason(skill)

    def _adaptive_skill_ratio(self, skill):
        if self._blocked_by_dialog():
            self.skill_monitor.pause(skill, "Aguardando o diálogo fechar")
            return None
        reason = self.input.blocked_reason()
        if reason or not self.slot_locator.ready_for(skill):
            self.skill_monitor.pause(skill, reason or "Aguardando a barra de skills")
            return None
        selected, region = self.input.selected(), self.input.skill_region(skill)
        if not region:
            self.skill_monitor.pause(skill, self.input.skill_blocked_reason(skill))
            return None
        try:
            frame = vision.grab(region)
        except (OSError, ValueError) as error:
            self.skill_monitor.pause(skill, f"Falha na leitura: {error}")
            return None
        with self._lock:
            if (not self.cfg.get("auto_slots", {}).get("enabled", False)
                    or not self.slot_locator.ready_for(skill) or self.input.selected() != selected
                    or self.input.skill_region(skill) != region or self.input.blocked_reason()):
                self.skill_monitor.pause(skill, "Leitura interrompida. Deixe os ícones visíveis.")
                return None
            return self.skill_monitor.observe(skill, selected, frame)


class PotionRoutine:
    """Potion scheduling; uses the Bot configuration and input boundary."""

    def _loop_potion(self):
        while not self._stop.is_set():
            if not self._active("potion"):
                time.sleep(IDLE_SLEEP * 2)
                continue

            remaining = self._next_potion_at - time.time()
            if remaining > 0:
                self.status["potion"] = f"{remaining:.0f}s"
            elif not self._blocked_by_dialog():
                cfg = self.cfg["potion"]
                if self._press(cfg.get("key", "q")) is not False:
                    self._next_potion_at = time.time() + max(
                        0.5, float(cfg.get("interval", 10.0)))
                    self._log("Poção: comando enviado.")
            time.sleep(IDLE_SLEEP)


class HeldKeyRoutine:
    """HeldKey scheduling; uses the Bot configuration and input boundary."""

    def _loop_holdkey(self):
        """Segura uma tecla por N segundos, solta e repete sem pausa."""
        while not self._stop.is_set():
            if not self._active("holdkey") or self._blocked_by_dialog():
                self._release_held_key()
                time.sleep(IDLE_SLEEP)
                continue

            cfg = self.cfg["holdkey"]
            key = (cfg.get("key") or "").strip()
            if not key:
                self.status["holdkey"] = "sem tecla"
                time.sleep(IDLE_SLEEP)
                continue

            self._hold_key_once(key, float(cfg.get("duration", 3.0)))
            time.sleep(KEY_RELEASE_GAP)

    def _hold_key_once(self, key, duration):
        """Um ciclo: aperta, segura ate o prazo, solta."""
        if not self.input.key_down(key):
            self.status["holdkey"] = f"tecla invalida: {key}"
            time.sleep(IDLE_SLEEP)
            return

        self._held_key = key
        duration = clamp_hold(duration)
        self._log(f"Segurar tecla: {key.upper()} pressionada por {duration:.1f}s.")
        self._wait_while_holding(key, duration)
        self._release_held_key()

    def _wait_while_holding(self, key, duration):
        """Espera o prazo, mas em fatias curtas.

        Se o master cair (ou o jogo perder o foco) no meio dos segundos, a
        tecla precisa ser solta na hora - senao ficaria presa no jogo.
        """
        prazo = time.time() + duration
        while not self._stop.is_set():
            restante = prazo - time.time()
            if restante <= 0:
                return
            if self.blocked_reason("holdkey") is not None or self._blocked_by_dialog():
                return
            self.status["holdkey"] = f"{key.upper()} {restante:.1f}s"
            time.sleep(min(HOLD_TICK, restante))

    def _release_held_key(self):
        if not self._held_key:
            return
        key, self._held_key = self._held_key, None
        try:
            if self.input.key_up(key) is not False:
                self._log(f"Segurar tecla: {key.upper()} solta.")
        except OSError as exc:
            self._log(f"ATENCAO: falha ao soltar {key.upper()} ({exc}). "
                      f"Se a tecla ficar presa, aperte {key.upper()} uma vez.")


class DialogRoutine:
    """Dialog scheduling; uses the Bot configuration and input boundary."""

    def _loop_dialogs(self):
        self._watch_dialogs("dialogs")

    def _watch_dialogs(self, feature):
        """Vigia as janelas de uma rotina ate o bot encerrar."""
        names = DIALOGS_BY_FEATURE[feature]
        while not self._stop.is_set():
            if not self._active(feature):
                time.sleep(DIALOG_IDLE_SLEEP)
                continue
            for name in names:
                self._handle_dialog(name, self.cfg[name])
            time.sleep(float(self.cfg.get("dialog_interval", 0.5)))

    def _handle_dialog(self, name, cfg):
        if not cfg.get("enabled", True):
            return
        # o `cooldown` vale para a propria janela: depois de agir, damos tempo
        # de ela responder. Sem isso o bot martelaria o botao a cada varredura
        # enquanto o dialogo continuasse na tela (o RETRY demora a reconectar).
        if time.time() < self._next_dialog_at.get(name, 0.0):
            return

        match = self._find_dialog(name, cfg)
        if match is None:
            return

        self.status[name] = f"detectada {match.score:.2f}"
        cooldown = float(cfg.get("cooldown", 1.5))
        self._next_dialog_at[name] = time.time() + cooldown
        # Segura o auto clique para nao clicar no jogo por baixo do dialogo.
        self._dialog_block_until = time.time() + cooldown
        self._release_mouse()
        time.sleep(BUSY_SLEEP)
        self._dismiss_dialog(name, cfg, match)
        time.sleep(DIALOG_SETTLE)

    def _find_dialog(self, name, cfg):
        template = self._template_for(name, cfg.get("template", ""))
        if template is None:
            self.status[name] = "sem template"
            return None
        region = self.input.client_region(require_focus=True)
        if not region:
            self.status[name] = "instância sem foco/visibilidade"
            return None
        selected = self.input.selected()
        hit = vision.find_template(template, float(cfg.get("confidence", 0.80)), region=region)
        if self.input.selected() != selected or self.input.client_region(require_focus=True) != region:
            return None
        if hit is None:
            self.status[name] = "nenhuma"
        return hit

    def _dismiss_dialog(self, name, cfg, match):
        """Fecha a janela detectada: pela tecla ou clicando no ponto marcado."""
        if cfg.get("action", "click") == "key" and cfg.get("key"):
            if self._press(cfg["key"]) is not False:
                self._log(f"{name}: comando enviado com a tecla '{cfg['key']}'.")
            return
        offset_x, offset_y = cfg.get("click_offset") or (0, 0)
        alvo = (match.x + int(offset_x), match.y + int(offset_y))
        if self.input.click_at(*alvo) is not False:
            self._log(f"{name}: clique em {alvo} (score {match.score:.2f}).")

    def _template_for(self, name, path):
        import config
        path = config.resolve_template(path)
        with self._lock:
            cached = self._templates.get(name)
            if cached and cached[0] == path:
                return cached[1]
            image = vision.load_template(path)
            self._templates[name] = (path, image)
            return image
