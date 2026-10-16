"""An independent periodic key for a second process; always HWND messages."""

import math
import threading
import time

import input_sender
from targeted_input import TargetedInput


class PeriodicKey:
    def __init__(self, cfg, primary, log=None, lock=None, sender=None):
        self.cfg = cfg
        self.cfg["input_mode"] = "messages"
        self.cfg["enabled"] = False  # Explicit activation after each launch.
        self._primary = primary
        self._log = log or (lambda _message: None)
        self._lock = lock or threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._next_at = None
        self._status = "desligada"
        self._last_block = None
        self.input = sender if sender is not None else TargetedInput(cfg, self._input_log)

    def _input_log(self, message):
        message = message.replace("[Bot]", "[Bot][Jogo 2]", 1)
        self._log(message.replace("Enviando ataque para", "Enviando tecla periódica para"))

    def set_logger(self, log):
        self._log = log
        self.input.set_logger(self._input_log)

    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="tecla-jogo2", daemon=True)
        self._thread.start()

    def shutdown(self):
        self._stop.set()
        self.set_enabled(False)
        if self._thread is not None:
            self._thread.join(timeout=0.3)
            self._thread = None

    def selected(self):
        with self._lock:
            return self.input.selected()

    def conflicts_with(self, candidate):
        selected = self.selected()
        return bool(selected and candidate and selected["pid"] == candidate["pid"])

    def _target_reason(self):
        selected, primary = self.input.selected(), self._primary.selected()
        if selected and primary and selected["pid"] == primary["pid"]:
            return "escolha um processo diferente do Jogo 1"
        return self.input.blocked_reason()

    def select(self, candidate):
        with self._lock:
            primary = self._primary.selected()
            if primary and primary["pid"] == candidate["pid"]:
                self._log("[Bot][Jogo 2] Seleção recusada: mesmo processo do Jogo 1.")
                return False
            self.set_enabled(False)
            return self.input.select(candidate)

    def update(self, patch):
        try:
            key = str(patch.get("key", self.cfg["key"])).strip().lower()
            interval = float(patch.get("interval", self.cfg["interval"]))
        except (TypeError, ValueError):
            return False
        if key not in input_sender.SCANCODES or not math.isfinite(interval) or not 0.5 <= interval <= 86400:
            self._log("[Bot][Jogo 2] Ajuste recusado: tecla inválida ou intervalo fora de 0,5–86400 segundos.")
            return False
        with self._lock:
            self.cfg.update(key=key, interval=interval, input_mode="messages")
            if self.cfg["enabled"]:
                self._next_at = time.monotonic() + interval
            self._log(f"[Bot][Jogo 2] Tecla {key.upper()} a cada {interval:g}s.")
        return True

    def set_enabled(self, enabled):
        with self._lock:
            if enabled:
                reason = self._target_reason()
                if reason or not self.update({}):
                    self._log(f"[Bot][Jogo 2] Ativação recusada: {reason or 'ajustes inválidos'}.")
                    return False
            self.cfg["enabled"] = bool(enabled)
            self._next_at = time.monotonic() + self.cfg["interval"] if enabled else None
            self._status = "aguardando" if enabled else "desligada"
            self._last_block = None
            if not enabled:
                self.input.release_all()
            self._log(f"[Bot][Jogo 2] Tecla periódica {'ligada' if enabled else 'desligada'}.")
            return True

    def state(self):
        with self._lock:
            remaining = max(0.0, self._next_at - time.monotonic()) if self._next_at is not None else None
            return {"selectedWindow": self.input.selected(), "enabled": self.cfg["enabled"],
                    "key": self.cfg["key"], "interval": self.cfg["interval"],
                    "remaining": remaining, "status": self._status}

    def _loop(self):
        while not self._stop.wait(0.1):
            self._tick()

    def _tick(self, now=None):
        with self._lock:
            if self._stop.is_set() or not self.cfg["enabled"]:
                return False
            self.input.maintain()
            reason = self._target_reason()
            if reason:
                self._status = reason
                if reason != self._last_block:
                    self._log(f"[Bot][Jogo 2] Tecla periódica pausada: {reason}.")
                self._last_block = reason
                return False
            self._last_block = None
            now = time.monotonic() if now is None else now
            if self._next_at is None or now < self._next_at:
                self._status = "aguardando"
                return False
            if not self.input.tap(self.cfg["key"]):
                self._status = "input bloqueado"
                self._next_at = now + 0.5
                return False
            target = self.input.selected()
            self._log(f"[Bot][Jogo 2] {self.cfg['key'].upper()} enviado para HWND={target['hwnd']} PID={target['pid']}.")
            self._status = "aguardando"
            self._next_at = now + self.cfg["interval"]
            return True
