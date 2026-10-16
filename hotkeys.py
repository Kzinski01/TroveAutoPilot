"""Atalhos globais (funcionam com o jogo em foco) via pynput."""

import threading

from pynput import keyboard

MODIFIER_NAMES = {
    keyboard.Key.ctrl: "ctrl", keyboard.Key.ctrl_l: "ctrl", keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.alt: "alt", keyboard.Key.alt_l: "alt", keyboard.Key.alt_r: "alt",
    keyboard.Key.alt_gr: "alt",
    keyboard.Key.shift: "shift", keyboard.Key.shift_l: "shift",
    keyboard.Key.shift_r: "shift",
}

MODIFIER_ORDER = ("ctrl", "alt", "shift")


def key_name(key):
    """Nome canonico de uma tecla (ignora modificadores)."""
    if key in MODIFIER_NAMES:
        return None
    if isinstance(key, keyboard.Key):
        return key.name.lower()
    vk = getattr(key, "vk", None)
    if vk is not None:
        if 0x30 <= vk <= 0x39:              # 0-9
            return chr(vk)
        if 0x41 <= vk <= 0x5A:              # A-Z
            return chr(vk).lower()
        if 0x60 <= vk <= 0x69:              # numpad
            return f"num{vk - 0x60}"
    char = getattr(key, "char", None)
    return char.lower() if char else None


class HotkeyManager:
    """Registra combos no formato 'ctrl+shift+f5' e dispara callbacks."""

    def __init__(self):
        self._bindings = {}
        self._active_modifiers = set()
        self._pressed_keys = set()
        self._capture = None
        self._lock = threading.Lock()
        self._listener = keyboard.Listener(on_press=self._on_press,
                                           on_release=self._on_release)
        self._listener.daemon = True

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def set_bindings(self, mapping):
        """mapping: {combo: callback}. Combos vazios sao ignorados."""
        with self._lock:
            self._bindings = {self.normalize(combo): cb
                              for combo, cb in mapping.items() if combo}

    def capture_next(self, callback):
        """Captura o proximo combo pressionado (para a tela de configuracao)."""
        with self._lock:
            self._capture = callback

    def cancel_capture(self):
        with self._lock:
            self._capture = None

    @staticmethod
    def normalize(combo):
        parts = [p.strip().lower() for p in str(combo).split("+") if p.strip()]
        mods = [m for m in MODIFIER_ORDER if m in parts]
        main = [p for p in parts if p not in MODIFIER_ORDER]
        return "+".join(mods + main[-1:])

    def _on_press(self, key):
        if key in MODIFIER_NAMES:
            self._active_modifiers.add(MODIFIER_NAMES[key])
            return
        name = key_name(key)
        if not name:
            return
        mods = [m for m in MODIFIER_ORDER if m in self._active_modifiers]
        combo = "+".join(mods + [name])

        with self._lock:
            if name in self._pressed_keys:
                return
            self._pressed_keys.add(name)
            capture, self._capture = self._capture, None
            callback = self._bindings.get(combo) if capture is None else None

        if capture is not None:
            capture(combo)
        elif callback is not None:
            threading.Thread(target=callback, daemon=True).start()

    def _on_release(self, key):
        if key in MODIFIER_NAMES:
            self._active_modifiers.discard(MODIFIER_NAMES[key])
        else:
            with self._lock:
                self._pressed_keys.discard(key_name(key))
