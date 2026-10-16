"""Automatic slot location, with selected-window and visibility validation."""

import os
import sys
import threading
import time
from dataclasses import dataclass

import cv2

import vision
from slot_detection import SlotDetector, SlotMatch


@dataclass(frozen=True)
class SlotLocation:
    context: tuple
    match: SlotMatch
    regions: dict
    bindings: dict
    revision: int


class AutoSlots:
    def __init__(self, cfg, sender, lock, log=None):
        self.cfg, self.input, self._lock = cfg, sender, lock
        self.options = cfg.setdefault("auto_slots", {"enabled": False})
        self._log = log or (lambda message: None)
        self._scan_lock = threading.Lock()
        self._detector = None
        self._match = None
        self._context = None
        self._validated = None
        self._next_at = 0.0
        self._status = "manual"
        self._confidence = None
        self._revision = 0

    def set_logger(self, log):
        self._log = log

    def invalidate(self):
        with self._lock:
            self._revision += 1
            self._validated = None
            self._context = None
            self._match = None
            self._next_at = 0.0

    def set_enabled(self, enabled):
        with self._lock:
            self.options["enabled"] = bool(enabled)
            self.invalidate()
            self._set_status("aguardando localização" if enabled else "manual")

    def _set_status(self, status):
        if not self.options["enabled"]:
            status = "manual"
        if status != self._status:
            self._log(f"[Bot][Slots] {status}")
        self._status = status

    def _current(self):
        selected = self.input.selected()
        client = self.input.client_region(require_focus=self.cfg.get("input_mode") != "messages")
        return (selected, tuple(client)) if selected and client else None

    def ready_for(self, skill):
        with self._lock:
            if not self.options["enabled"]:
                return True
            return (self._validated is not None and self._validated == self._current()
                    and skill.get("auto_sampling") is True)

    def state(self):
        with self._lock:
            return {"enabled": self.options["enabled"], "status": self._status,
                    "confidence": self._confidence,
                    "skills": [dict(skill) for skill in self.cfg["skills"]]}

    def update(self, force=False):
        if not self.options["enabled"]:
            return False
        if not force:
            reason = self.input.blocked_reason()
            if reason:
                if reason != "captura/calibração em andamento":
                    with self._lock:
                        self._validated = None
                        self._confidence = None
                        self._set_status(f"aguardando: {reason}")
                return False
        current = self._current()
        now = time.monotonic()
        if not force and current == self._context and now < self._next_at:
            return self._validated is not None
        if not self._scan_lock.acquire(blocking=False):
            return False
        try:
            return self._scan(current)
        except (OSError, ValueError, cv2.error) as exc:
            with self._lock:
                self._validated = None
                self._set_status(f"localização pausada: {exc}")
            return False
        finally:
            self._next_at = time.monotonic() + 1.5
            self._scan_lock.release()

    def _scan(self, current):
        with self._lock:
            revision = self._revision
            previous = self._match if current == self._context else None
            self._validated = None
            self._confidence = None
            self._context = current
        if not current:
            self._set_status("aguardando janela selecionada e disponível")
            return False
        _, client = current
        detector = self._get_detector()
        match = self._find_match(detector, client, previous)
        if match is None:
            self._set_status("barra não reconhecida ou ambígua; skills pausadas")
            return False
        regions = self._screen_regions(match, client)
        bindings = self._bind_all(regions)
        if not bindings or current != self._current():
            self._set_status("barra encoberta ou janela alterada; skills pausadas")
            return False
        # Confirm on a second frame, so a resize/move during capture cannot bind stale pixels.
        if not self._confirm_match(detector, client, match):
            self._set_status("barra mudou durante a captura; tentando novamente")
            return False
        return self._apply(SlotLocation(current, match, regions, bindings, revision))

    @staticmethod
    def _find_match(detector, client, previous):
        frame = vision.grab(client)
        match = detector.find(frame, previous)
        return detector.find(frame) if match is None and previous is not None else match

    @staticmethod
    def _screen_regions(match, client):
        regions = {name: [client[0] + x, client[1] + y, width, height]
                   for name, (x, y, width, height) in match.regions().items()}
        regions["bar"] = [client[0] + match.x, client[1] + match.y,
                          round(145 * match.scale), round(45 * match.scale)]
        return regions

    @staticmethod
    def _confirm_match(detector, client, match):
        confirmation = detector.find(vision.grab(client), match)
        return (confirmation is not None and abs(confirmation.x - match.x) <= 2
                and abs(confirmation.y - match.y) <= 2
                and abs(confirmation.scale - match.scale) <= 0.05)

    def _get_detector(self):
        if self._detector is None:
            base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "assets", "skill-bar-reference.png")
            self._detector = SlotDetector(cv2.imread(path))
        return self._detector

    def _bind_all(self, regions):
        bindings = {name: self.input.bind_region(region, require_focus=False)
                    for name, region in regions.items()}
        return bindings if all(bindings.values()) else None

    def _apply(self, location):
        current, match = location.context, location.match
        regions, bindings = location.regions, location.bindings
        with self._lock:
            if not self.options["enabled"] or location.revision != self._revision:
                return False
            if current != self._current() or self._bind_all(regions) != bindings:
                self._set_status("barra encoberta ou janela alterada; skills pausadas")
                return False
            changed = (self._match is None or
                       (self._match.x, self._match.y, self._match.scale) != (match.x, match.y, match.scale))
            for skill in self.cfg["skills"]:
                name = skill["id"]
                if name not in regions:
                    continue
                if not skill.get("auto_sampling"):
                    # Old manual crops have different pixels; never fabricate a ready baseline.
                    skill.update(ready_score=0.0, cooldown_score=0.0, auto_sampling=True)
                    self._log(f"[Bot][Slots] Slot {skill['name']}: capture Pronta uma vez para a nova área.")
                skill.update(region=regions[name], window_region=bindings[name])
            self._match = match
            self._validated = current
            self._confidence = match.score
            self._set_status("slots M2, 1 e 2 localizados")
            if changed:
                selected, client = current
                self._log(f"[Bot][Slots] HWND={selected['hwnd']} PID={selected['pid']} "
                          f"área={client[2:]} escala={match.scale:g} confiança={match.score:.3f}")
            return True
