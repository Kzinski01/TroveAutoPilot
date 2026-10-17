"""Motor do bot: uma thread por rotina (clique, skills, pocao, janelas)."""

import copy
import threading
import time

import vision as vision
from auto_slots import AutoSlots
from config import SECONDARY_DEFAULTS
from periodic_key import PeriodicKey
from routines import (
    BUSY_SLEEP as BUSY_SLEEP,
)
from routines import (
    CLICK_HOLD as CLICK_HOLD,
)
from routines import (
    DIALOG_IDLE_SLEEP as DIALOG_IDLE_SLEEP,
)
from routines import (
    DIALOG_NAMES as DIALOG_NAMES,
)
from routines import (
    DIALOG_SETTLE as DIALOG_SETTLE,
)
from routines import (
    DIALOGS_BY_FEATURE as DIALOGS_BY_FEATURE,
)
from routines import (
    HOLD_TICK as HOLD_TICK,
)
from routines import (
    IDLE_MEASURE_INTERVAL as IDLE_MEASURE_INTERVAL,
)
from routines import (
    IDLE_SLEEP as IDLE_SLEEP,
)
from routines import (
    INDEPENDENT_FEATURES as INDEPENDENT_FEATURES,
)
from routines import (
    JOIN_TIMEOUT as JOIN_TIMEOUT,
)
from routines import (
    KEY_RELEASE_GAP as KEY_RELEASE_GAP,
)
from routines import (
    MAX_CPS as MAX_CPS,
)
from routines import (
    MAX_HOLD as MAX_HOLD,
)
from routines import (
    SKILL_GAP as SKILL_GAP,
)
from routines import (
    AutoclickRoutine,
    DialogRoutine,
    HeldKeyRoutine,
    PotionRoutine,
    SkillRoutine,
)
from routines import (
    clamp_hold as clamp_hold,
)
from skill_learning import SkillMonitor
from targeted_input import TargetedInput


class Bot(AutoclickRoutine, SkillRoutine, PotionRoutine, HeldKeyRoutine, DialogRoutine):
    """Cada rotina roda em sua propria thread e respeita o master switch.

    O auto clique e prioridade: mantem o proprio ritmo e so e interrompido por
    uma janela detectada, quando `pause_on_dialog` esta ligado.
    """

    def __init__(self, cfg, log=None, sender=None):
        self.cfg = cfg
        self._log = log or (lambda _message: None)
        self.input = sender if sender is not None else TargetedInput(cfg, self._log)

        self.master = False
        self.features = cfg.setdefault("features", {})
        self.status = {}              # rotina -> texto curto para a interface

        self._lock = threading.RLock()
        self.skill_monitor = SkillMonitor(self._lock)
        self.slot_locator = AutoSlots(cfg, self.input, self._lock, self._log)
        self.secondary = PeriodicKey(cfg.setdefault("secondary", copy.deepcopy(SECONDARY_DEFAULTS)),
                                     self.input, self._log, lock=self._lock)
        self._stop = threading.Event()
        self._threads = []

        self._mouse_held = False
        self._held_button = None
        self._held_key = None         # tecla presa agora pela rotina holdkey
        self._dialog_block_until = 0.0
        self._next_dialog_at = {}     # janela -> quando pode agir de novo
        self._next_skill_at = {}
        self._next_potion_at = 0.0
        self._templates = {}          # nome -> (caminho, imagem)

    # ---------------------------------------------------------------- ciclo
    def set_logger(self, log):
        self._log = log
        self.input.set_logger(log)
        self.slot_locator.set_logger(log)
        self.secondary.set_logger(log)

    def start(self):
        if self._threads:
            return
        self._stop.clear()
        self.secondary.start()
        for target in (self._loop_autoclick, self._loop_skills,
                       self._loop_potion, self._loop_dialogs,
                       self._loop_holdkey):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def shutdown(self):
        self._stop.set()
        self.slot_locator.invalidate()
        self.secondary.shutdown()
        self.master = False
        self._release_mouse()
        self._release_held_key()
        self.input.release_all()
        for thread in self._threads:
            thread.join(timeout=JOIN_TIMEOUT)
        self._threads = []

    # --------------------------------------------------------------- estado
    def set_master(self, value):
        self.master = bool(value)
        if not self.master:
            self._release_mouse()
            # a tecla segurada nao e solta aqui: essa rotina roda por conta
            # propria e so obedece ao proprio switch (ou ao panico).
        self._log(f"Master: {'ligado' if self.master else 'desligado'}")

    def toggle_master(self):
        self.set_master(not self.master)

    def set_feature(self, name, value):
        self.features[name] = bool(value)
        if value:
            return
        if name == "autoclick":
            self._release_mouse()
        elif name == "holdkey":
            self._release_held_key()

    def toggle_feature(self, name):
        self.set_feature(name, not self.features.get(name, False))
        self._log(f"{name}: {'ligado' if self.features[name] else 'desligado'}")

    def panic(self):
        """Para tudo, inclusive as rotinas que nao dependem do master."""
        self.set_master(False)
        self.secondary.set_enabled(False)
        for name in INDEPENDENT_FEATURES:
            self.set_feature(name, False)
        self._log("Pânico: tudo desligado.")

    def reload_templates(self):
        with self._lock:
            self._templates.clear()

    # --------------------------------------------------------------- regras
    def blocked_reason(self, feature):
        """None se a rotina pode agir; senao o motivo, usado no log e na tela."""
        if self._stop.is_set():
            return "encerrando"
        if not self.features.get(feature, False):
            return "off"
        if not self.master and feature not in INDEPENDENT_FEATURES:
            return "master off"
        return self.input.blocked_reason()

    def _active(self, feature):
        self.input.maintain()
        reason = self.blocked_reason(feature)
        if reason is None:
            return True
        self.status[feature] = reason
        return False

    def _blocked_by_dialog(self):
        return (self.cfg.get("pause_on_dialog", True)
                and time.time() < self._dialog_block_until)

    # ---------------------------------------------------------------- input
    def _press(self, key):
        """Aceita nomes de tecla e `mouse_left` / `mouse_right` / `mouse_middle`."""
        if not key:
            return False
        if key.startswith("mouse_"):
            return self.input.click(key.split("_", 1)[1], hold=CLICK_HOLD)
        else:
            return self.input.tap(key)
