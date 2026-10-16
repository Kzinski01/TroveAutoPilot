"""Recognize the M2/1/2 labels together, independently of class icons."""

from dataclasses import dataclass

import cv2
import numpy as np

LABELS = {"m2": (10, 4, 20, 12), "s1": (60, 4, 8, 12), "s2": (110, 4, 8, 12)}
SCALES = tuple(round(float(value), 2) for value in np.arange(0.65, 2.01, 0.05))
MIN_ANCHOR = 0.75
MIN_LABEL = 0.70
MIN_MEAN = 0.82


@dataclass(frozen=True)
class SlotMatch:
    x: int
    y: int
    scale: float
    score: float

    def regions(self):
        # Exclude the key labels and bottom charge counters from cooldown reads.
        return {name: [self.x + round((offset + 4) * self.scale),
                       self.y + round(11 * self.scale),
                       round(36 * self.scale), round(29 * self.scale)]
                for name, offset in (("m2", 0), ("s1", 50), ("s2", 100))}


def text_mask(image):
    """White/gray glyphs remain readable when the colored icon darkens."""
    return ((np.min(image, axis=2) > 150) &
            (np.ptp(image, axis=2) < 70)).astype(np.uint8) * 255


class SlotDetector:
    def __init__(self, reference):
        if reference is None or reference.shape[:2] != (53, 363):
            raise ValueError("referência visual da barra ausente ou inválida")
        self.templates = []
        for scale in SCALES:
            scaled = cv2.resize(reference, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            for whole_bar in (True, False):
                labels = {}
                for name, (x, y, width, height) in LABELS.items():
                    if whole_bar:
                        sx, sy = round(x * scale), round(y * scale)
                        crop = scaled[sy:sy + round(height * scale), sx:sx + round(width * scale)]
                    else:
                        crop = cv2.resize(reference[y:y + height, x:x + width], None,
                                          fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
                    labels[name] = text_mask(crop)
                self.templates.append((scale, labels))

    def find(self, image, previous=None):
        if image is None or image.size == 0:
            return None
        height, width = image.shape[:2]
        if previous:
            x = max(0, previous.x - 10)
            y = max(round(height * 0.5), previous.y - 6)
            right = min(width, previous.x + round(150 * previous.scale) + 10)
            bottom = min(height, previous.y + round(50 * previous.scale) + 6)
        else:
            x, y, right, bottom = 0, round(height * 0.5), width, height
        mask = text_mask(image[y:bottom, x:right])
        candidates = self._candidates(mask, x, y)
        return self._unambiguous(candidates)

    def _candidates(self, mask, offset_x, offset_y):
        found = []
        for scale, labels in self.templates:
            anchor = labels["m2"]
            if mask.shape[0] < anchor.shape[0] or mask.shape[1] < round(145 * scale):
                continue
            scores = cv2.matchTemplate(mask, anchor, cv2.TM_CCOEFF_NORMED)
            for _ in range(8):
                _, score, _, point = cv2.minMaxLoc(scores)
                if score < MIN_ANCHOR:
                    break
                px, py = point
                other = [self._label_score(mask, labels[name], px + round(step * scale), py)
                         for name, step in (("s1", 50), ("s2", 100))]
                average = (score + sum(other)) / 3
                if min(other) >= MIN_LABEL and average >= MIN_MEAN:
                    found.append(SlotMatch(px + offset_x, py + offset_y, scale, average))
                scores[max(0, py - 8):py + 9, max(0, px - 15):px + 16] = -1
        return found

    @staticmethod
    def _label_score(mask, template, x, y):
        height, width = template.shape
        crop = mask[max(0, y - 2):y + height + 3, max(0, x - 3):x + width + 4]
        if crop.shape[0] < height or crop.shape[1] < width:
            return -1.0
        return cv2.minMaxLoc(cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED))[1]

    @staticmethod
    def _unambiguous(candidates):
        if not candidates:
            return None
        best = max(candidates, key=lambda match: match.score)
        # Different scales of the same bar are one candidate; two bars are unsafe.
        if any(abs(match.x - best.x) > 18 or abs(match.y - best.y) > 10
               for match in candidates):
            return None
        return best
