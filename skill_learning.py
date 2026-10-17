"""Learn visible cooldown cycles and gate spaced learning attempts."""

import time
from collections import deque

import cv2
import numpy as np

import vision

LEARNING_ATTEMPT_INTERVAL = 2.0

LABELS = {
    "learning": "Preparando o aprendizado automático",
    "watching": "Aguardando a skill voltar do cooldown",
    "ready": "Pronta",
    "cooldown": "Em cooldown",
    "confirming": "Confirmando resposta no ícone",
    "blocked": "Leitura pausada",
}


def thumbnail(frame):
    return cv2.resize(frame, (24, 24), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def resembles(frame, reference):
    difference = np.abs(frame - reference)
    return float(np.mean(difference)) < 0.065 and float(np.quantile(difference, 0.90)) < 0.18


def new_counter_pixels(image, reference):
    """Cooldown text can appear without a large change in average icon brightness."""
    mask = ((np.min(image, axis=2) > 0.68) & (np.ptp(image, axis=2) < 0.20)
            & (np.min(reference, axis=2) < 0.60))
    mask[:3] = False
    mask[-3:] = False
    return 6 <= int(np.count_nonzero(mask)) <= 120


class VisualCycle:
    """Confirm readiness only after a stable image, cooldown and observed return."""

    def __init__(self):
        self.reference = None
        self.baseline = 0.0
        self.calibrated = False
        self.low_seen = False
        self.awaiting_change = False
        self.ready = False
        self.status = "learning"
        self.last_cooldown = None
        self._cooldown_at = None
        self._last_at = None
        self._samples = deque(maxlen=4)
        self._dark_samples = 0
        self._different_since = None
        self._next_attempt_at = 0.0

    def pause(self, preserve_cycle=False):
        self.ready = False
        self._samples.clear()
        self._dark_samples = 0
        if not preserve_cycle:
            self.low_seen = False
            self.awaiting_change = False
            self._cooldown_at = None
            self._last_at = None
        self._different_since = None
        self.status = "blocked"

    def sent(self, now):
        self.ready = False
        self.awaiting_change = True
        self._samples.clear()
        self._cooldown_at = now
        self.status = "confirming"
        self.defer_attempt(now)

    def defer_attempt(self, now):
        self._next_attempt_at = now + LEARNING_ATTEMPT_INTERVAL

    def can_attempt(self, now):
        if (self.reference is None or self._last_at is None or not self._samples
                or now - self._last_at > 0.8 or now < self._next_attempt_at or self.low_seen):
            return False
        if self.calibrated and not self.awaiting_change:
            return False
        _, image, score = self._samples[-1]
        return (self._stable(now) and 0.94 <= score / self.baseline <= 1.10
                and resembles(image, self.reference) and not new_counter_pixels(image, self.reference))

    def message(self):
        if (self.awaiting_change and self._last_at is not None and self._cooldown_at is not None
                and self._last_at - self._cooldown_at > 1):
            return "Sem resposta visual. Tentativas espaçadas; confira o modo de envio."
        return LABELS[self.status]

    def observe(self, frame, now):
        if self._last_at is not None and now - self._last_at > 0.8:
            self.pause()
        self._last_at = now
        image, score = thumbnail(frame), vision.icon_score(frame)
        self.ready = False
        self._samples.append((now, image, score))
        if self.reference is None:
            if self._stable(now):
                self._set_reference(image, score)
            self.status = "learning"
            return None
        if self._replace_changed_icon(image, score, now):
            return None
        ratio = score / self.baseline
        counter = new_counter_pixels(image, self.reference)
        overlay = counter and float(np.mean(np.abs(image - self.reference))) > 0.04
        self._observe_darkening(ratio, now, overlay)
        matches = 0.94 <= ratio <= 1.10 and resembles(image, self.reference) and not counter
        if matches and self._stable(now):
            self._observe_return(image, score, now)
        else:
            self.status = "cooldown" if self.calibrated else ("watching" if self.low_seen else "learning")
        if self.awaiting_change:
            self.status = "confirming"
        return ratio if self.calibrated else None

    def _stable(self, now):
        if len(self._samples) < 3 or now - self._samples[0][0] < 0.20:
            return False
        latest = self._samples[-1][1]
        return all(float(np.mean(np.abs(sample[1] - latest))) < 0.025 for sample in self._samples)

    def _set_reference(self, image, score):
        self.reference = image.copy()
        self.baseline = max(score, 0.001)
        self.low_seen = False
        self.awaiting_change = False
        self._dark_samples = 0

    def _replace_changed_icon(self, image, score, now):
        # A brighter starting plateau may have been a partial cooldown. Never arm it.
        if not self.calibrated and score > self.baseline * 1.15 and self._stable(now):
            self._set_reference(image, score)
        different = (score >= self.baseline * 0.90 and not resembles(image, self.reference)
                     and not self.awaiting_change and not self.low_seen)
        self._different_since = (self._different_since or now) if different else None
        if self._different_since is not None and now - self._different_since > 1.5:
            self.__init__()
            return True
        return False

    def _observe_darkening(self, ratio, now, overlay=False):
        dark = ((ratio <= 0.75 and self.baseline * (1 - ratio) >= 0.075)
                or (overlay and (self.awaiting_change or self.calibrated or self.low_seen)))
        self._dark_samples = self._dark_samples + 1 if dark else 0
        if self._dark_samples >= 2:
            self.low_seen = True
            self.awaiting_change = False
            if self._cooldown_at is None:
                self._cooldown_at = now

    def _observe_return(self, image, score, now):
        if self.low_seen:
            self.calibrated = True
            if self._cooldown_at is not None:
                self.last_cooldown = round(now - self._cooldown_at, 2)
            self._cooldown_at = None
            self.low_seen = False
        self.ready = self.calibrated and not self.awaiting_change
        self.status = "ready" if self.ready else "learning"
        if self.ready and 0.96 <= score / self.baseline <= 1.06:
            # Only a confirmed ready plateau may adapt; dark cooldowns cannot lower the baseline.
            self.reference = self.reference * 0.99 + image * 0.01
            self.baseline = self.baseline * 0.99 + score * 0.01


class SkillMonitor:
    """Keep learning separate per target, binding and key; expose cached JSON only."""

    def __init__(self, lock):
        self._lock = lock
        self._cycles = {}
        self._readings = {}

    def reset(self):
        with self._lock:
            self._cycles.clear()
            self._readings.clear()

    def observe(self, skill, target, frame):
        with self._lock:
            key = (target["hwnd"], target["pid"], target["process_created"],
                   repr(skill.get("window_region")), skill.get("key"))
            saved_key, cycle = self._cycles.get(skill["id"], (None, None))
            if key != saved_key:
                cycle = VisualCycle()
                self._cycles[skill["id"]] = key, cycle
            if frame is None or not vision.has_texture(frame):
                self.pause(skill, "Ícone sem leitura. Deixe a barra visível.")
                return None
            ratio = cycle.observe(frame, time.monotonic())
            self._readings[skill["id"]] = {
                "status": cycle.status, "message": cycle.message(), "ratio": ratio,
                "calibrated": cycle.calibrated, "ready": cycle.ready,
                "lastCooldown": cycle.last_cooldown,
            }
            return ratio

    def pause(self, skill, message, issue=None, preserve_cycle=False):
        with self._lock:
            saved = self._cycles.get(skill["id"])
            if saved:
                saved[1].pause(preserve_cycle=preserve_cycle)
            self._readings[skill["id"]] = {
                "status": "blocked", "message": message, "ratio": None,
                "calibrated": bool(saved and saved[1].calibrated), "ready": False,
                "lastCooldown": None,
                "issue": issue,
            }

    def ready(self, skill, target):
        with self._lock:
            return self._matches(skill, target) and self._readings.get(skill["id"], {}).get("ready", False)

    def _matches(self, skill, target):
        saved = self._cycles.get(skill["id"])
        if not target or not saved:
            return False
        expected = (target["hwnd"], target["pid"], target["process_created"],
                    repr(skill.get("window_region")), skill.get("key"))
        return saved[0] == expected

    def can_attempt(self, skill, target):
        with self._lock:
            return self._matches(skill, target) and self._cycles[skill["id"]][1].can_attempt(time.monotonic())

    def defer_attempt(self, skill):
        with self._lock:
            self._cycles[skill["id"]][1].defer_attempt(time.monotonic())

    def sent(self, skill):
        with self._lock:
            saved = self._cycles.get(skill["id"])
            if saved:
                saved[1].sent(time.monotonic())
            self._readings[skill["id"]].update(status="confirming", message=LABELS["confirming"], ready=False)

    def message(self, skill):
        with self._lock:
            return self._readings.get(skill["id"], {}).get("message", LABELS["learning"])

    def state(self):
        with self._lock:
            return {name: dict(reading) for name, reading in self._readings.items()}
