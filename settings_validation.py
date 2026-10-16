"""Allowlisted, atomic validation of editable configuration fields."""

import math

from input_sender import SCANCODES


def boolean(value):
    if type(value) is not bool:
        raise ValueError("esperado verdadeiro/falso")
    return value


def number(low, high):
    def validate(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("esperado número")
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"valor fora de {low:g}–{high:g}")
        return value
    return validate


def choice(*options):
    def validate(value):
        if value not in options:
            raise ValueError("opção inválida")
        return value
    return validate


def text(value):
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("texto inválido ou muito longo")
    return value.strip()


def key(value):
    value = text(value).lower()
    if value and value not in SCANCODES and value not in {"mouse_left", "mouse_right", "mouse_middle"}:
        raise ValueError("tecla desconhecida")
    return value


SKILL = {"enabled": boolean, "key": key, "threshold": number(0.05, 2),
         "min_interval": number(0.05, 86400)}
DIALOG = {"enabled": boolean, "key": key, "action": choice("click", "key"),
          "confidence": number(0.05, 1), "cooldown": number(0.05, 86400)}
SETTINGS = {"only_when_focused": boolean, "pause_on_dialog": boolean,
            "target_window": text, "extra_windows": text}
SECTIONS = {
    "autoclick": {"mode": choice("click", "hold"), "cps": number(1, 40),
                  "button": choice("left", "right", "middle")},
    "potion": {"key": key, "interval": number(0.5, 86400)},
    "holdkey": {"key": key, "duration": number(0.1, 60)},
}


def patch(values, schema):
    if not isinstance(values, dict):
        raise ValueError("ajustes precisam ser um objeto")
    return {name: schema[name](value) for name, value in values.items() if name in schema}


def settings(values):
    result = patch(values, SETTINGS)
    for name, schema in SECTIONS.items():
        if name in values:
            result[name] = patch(values[name], schema)
    return result
