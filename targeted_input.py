"""Single input boundary for every bot routine, including releases and dialogs."""

import ctypes
import threading
import time
from ctypes import wintypes

import game_windows as windows
import input_sender as raw

raw.user32.PostMessageW.restype = wintypes.BOOL
raw.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
raw.user32.MapVirtualKeyW.restype = wintypes.UINT
raw.user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]

BUTTON_MESSAGES = {"left": (0x0201, 0x0202, 1),
                   "right": (0x0204, 0x0205, 2),
                   "middle": (0x0207, 0x0208, 16)}

REGION_MESSAGES = {
    "unavailable": "janela indisponível/minimizada ou sem foco no modo Compatibilidade",
    "outside": "área do ícone fora da janela; detecte as skills novamente",
    "covered": "ícone encoberto por outra janela",
}


class TargetedInput:
    def __init__(self, cfg, log=None):
        self.cfg = cfg
        if cfg.get("input_mode") not in ("foreground", "messages"):
            cfg["input_mode"] = "foreground"
        self._log = log or (lambda _message: None)
        self._lock = threading.RLock()
        self._target = None  # Saved handles must be explicitly selected each launch.
        self._pressed = {}  # (kind, name) -> coordinates for a directed mouse release
        self._pending = set()
        self._last_reason = None
        self._last_sent_log = 0.0
        self._last_focused = None
        self._suspended = False
        self._skill_blocks = {}
        self._skill_block_codes = {}

    def set_logger(self, log):
        self._log = log

    def selected(self):
        with self._lock:
            return dict(self._target) if self._target else None

    def select(self, candidate):
        with self._lock:
            if not windows.same_identity(candidate, windows.window_info(candidate["hwnd"])):
                self._log("[Bot] Input ignorado por segurança: janela mudou; atualize a lista.")
                return False
            self.release_all()
            if self._pressed:
                self._log("[Bot] Seleção bloqueada: volte à janela anterior para soltar o input pendente.")
                return False
            self._target = {key: candidate[key] for key in
                            ("hwnd", "pid", "process_created", "exe", "title")}
            self.cfg["selected_window"] = dict(self._target)
            self._last_reason = None
            self._last_focused = None
            self._skill_blocks.clear()
            self._skill_block_codes.clear()
            self._log(f"[Bot] Janela selecionada: {candidate['title']} ({candidate['exe']})")
            self._log(f"[Bot] HWND: {candidate['hwnd']} (0x{candidate['hwnd']:X})")
            self._log(f"[Bot] PID: {candidate['pid']}")
            return True

    def set_mode(self, mode):
        if mode not in ("foreground", "messages"):
            return False
        with self._lock:
            self.release_all()
            if self._pressed:
                self._log("[Bot] Mudança de modo bloqueada: input ainda pendente na janela anterior.")
                return False
            self.cfg["input_mode"] = mode
            self._log(f"[Bot] Modo de input: {mode}; sem troca automática de foco.")
            return True

    def suspend(self, value):
        with self._lock:
            self._suspended = bool(value)
            if value:
                self.release_all()

    def _identity_valid(self):
        return bool(self._target and windows.same_identity(
            self._target, windows.window_info(self._target["hwnd"])))

    def is_focused(self):
        with self._lock:
            return bool(self._identity_valid()
                        and windows.foreground_hwnd() == self._target["hwnd"])

    def blocked_reason(self):
        with self._lock:
            reason = self._reason()
            if reason != self._last_reason:
                if reason:
                    self._log(f"[Bot] Input ignorado por segurança: {reason}")
                self._last_reason = reason
            return reason

    def _reason(self):
        if self._suspended:
            return "captura/calibração em andamento"
        if not self._target:
            return "selecione a instância do jogo"
        if not self._identity_valid():
            return "janela encerrada ou identidade alterada; selecione novamente"
        focused = windows.foreground_hwnd() == self._target["hwnd"]
        if self._last_focused is True and not focused:
            self._log("[Bot] Janela perdeu foco")
        self._last_focused = focused
        if self.cfg.get("input_mode", "foreground") == "foreground" and not focused:
            return "sem foco na instância selecionada"
        if windows.user32.IsIconic(self._target["hwnd"]):
            return "janela minimizada"
        return None

    def maintain(self):
        """Retry directed releases anytime; global releases require target focus."""
        with self._lock:
            if not self._pending:
                return
            if self.cfg.get("input_mode") != "messages" and not self.is_focused():
                return
            for token in tuple(self._pending):
                self._release(token)

    def client_region(self, require_focus=False):
        with self._lock:
            if not self._identity_valid() or (require_focus and not self.is_focused()):
                return None
            if windows.user32.IsIconic(self._target["hwnd"]):
                return None
            return windows.client_region(self._target["hwnd"])

    def bind_region(self, region, require_focus=True):
        """Associate a manually captured area with client coordinates and size."""
        with self._lock:
            client, issue = self._check_region(region, require_focus)
            if issue:
                return None
            x, y, width, height = region
            return {"relative": [x - client[0], y - client[1], width, height],
                    "client_size": list(client[2:])}

    def region_issue(self, region, require_focus=False):
        with self._lock:
            return self._check_region(region, require_focus)[1]

    def _check_region(self, region, require_focus):
        client = self.client_region(require_focus=require_focus)
        if not client:
            return None, "unavailable"
        if not region:
            return client, "outside"
        x, y, width, height = region
        if (width <= 0 or height <= 0 or not windows.contains(client, x, y)
                or not windows.contains(client, x + width - 1, y + height - 1)):
            return client, "outside"
        points = ((px, py) for px in (x, x + width // 2, x + width - 1)
                  for py in (y, y + height // 2, y + height - 1))
        if not all(windows.point_belongs(
                self._target["hwnd"], px, py) for px, py in points):
            return client, "covered"
        return client, None

    def skill_region(self, skill):
        with self._lock:
            region, reason, code = self._skill_region(skill)
            skill_id = skill.get("id", "?")
            previous = self._skill_blocks.get(skill_id)
            self._skill_blocks[skill_id] = reason
            self._skill_block_codes[skill_id] = code
            if reason != previous:
                message = f"pausada: {reason}" if reason else "leitura retomada"
                self._log(f"[Bot] Skill {skill.get('name', skill_id)}: {message}")
            return region

    def skill_blocked_reason(self, skill):
        with self._lock:
            return self._skill_blocks.get(skill.get("id", "?"))

    def skill_blocked_code(self, skill):
        with self._lock:
            return self._skill_block_codes.get(skill.get("id", "?"))

    def _skill_region(self, skill):
        # Messages can target an unfocused game. MSS still needs its icon pixels
        # exposed on the desktop, so validate visibility before AND after grab.
        require_focus = self.cfg.get("input_mode") != "messages"
        client = self.client_region(require_focus=require_focus)
        binding = skill.get("window_region")
        if not client:
            return None, REGION_MESSAGES["unavailable"], "unavailable"
        if not binding:
            return None, "recapture a área do ícone na instância selecionada", "not_found"
        if list(client[2:]) != binding.get("client_size"):
            return None, "janela redimensionada; recapture a área do ícone", "outside"
        x, y, width, height = binding["relative"]
        region = [client[0] + x, client[1] + y, width, height]
        issue = self.region_issue(region, require_focus=require_focus)
        if issue:
            return None, REGION_MESSAGES[issue], issue
        return region, None, None

    def _post(self, message, wparam, lparam):
        if not self._identity_valid():
            return False
        if not raw.user32.PostMessageW(self._target["hwnd"], message, wparam, lparam):
            self._log(f"[Bot] Input ignorado por segurança: PostMessage falhou ({ctypes.get_last_error()}).")
            return False
        return True

    def _key_message(self, name, up):
        scan = raw.SCANCODES.get(name)
        if scan is None:
            return False
        vk = raw.user32.MapVirtualKeyW(scan, 3)  # MAPVK_VSC_TO_VK_EX
        extended = bool(scan & 0xE000)
        flags = 1 | ((scan & 0xFF) << 16) | (int(extended) << 24)
        is_alt = name in ("alt", "left alt", "right alt")
        if up:
            flags |= (1 << 30) | (1 << 31)
        message = (0x0105 if up else 0x0104) if is_alt else (0x0101 if up else 0x0100)
        return self._post(message, vk, flags)

    def _mouse_message(self, name, up, point):
        client = self.client_region()
        if not client:
            return False
        x, y = point[0] - client[0], point[1] - client[1]
        down, release, mask = BUTTON_MESSAGES[name]
        state = 0
        for kind, button in self._pressed:
            if kind == "mouse" and (not up or button != name):
                state |= BUTTON_MESSAGES[button][2]
        if not up:
            state |= mask
        return self._post(release if up else down, state, (x & 0xFFFF) | ((y & 0xFFFF) << 16))

    def _debug_sent(self, action):
        now = time.monotonic()
        if now - self._last_sent_log >= 1.0:
            self._log(f"[Bot] Enviando ataque para: HWND={self._target['hwnd']} PID={self._target['pid']} ({action})")
            suffix = "mensagem enfileirada; aceitação pelo jogo não verificada" if self.cfg.get("input_mode") == "messages" else "SendInput global com foco verificado"
            self._log(f"[Bot] Input enviado: {suffix}")
            self._last_sent_log = now

    def _global_event(self, kind, name, up):
        try:
            if kind == "key":
                return raw.key_up(name) if up else raw.key_down(name)
            return raw.mouse_up(name) if up else raw.mouse_down(name)
        except OSError as exc:
            self._log(f"[Bot] Input ignorado por segurança: {exc}")
            return False

    def _down(self, kind, name, point=None):
        with self._lock:
            self.maintain()
            if self.blocked_reason() or self._pending:
                return False
            token = (kind, name)
            if token in self._pressed:
                return False
            if kind == "mouse":
                if name not in BUTTON_MESSAGES:
                    return False
                client = self.client_region()
                point = point or raw.get_cursor_pos()
                if not windows.contains(client, *point):
                    if self.cfg.get("input_mode") == "messages" and client:
                        point = (client[0] + client[2] // 2, client[1] + client[3] // 2)
                    else:
                        self._log("[Bot] Input ignorado por segurança: mouse fora da janela selecionada.")
                        return False
                if self.cfg.get("input_mode") != "messages" and not windows.point_belongs(self._target["hwnd"], *point):
                    self._log("[Bot] Input ignorado por segurança: outra janela sob o mouse.")
                    return False
            elif name not in raw.SCANCODES:
                return False
            if self.cfg.get("input_mode") == "messages":
                sent = self._key_message(name, False) if kind == "key" else self._mouse_message(name, False, point)
            else:
                # Recheck immediately before a GLOBAL injection. This cannot
                # atomically pin Windows focus; messages mode avoids this race.
                if not self.is_focused():
                    return False
                sent = self._global_event(kind, name, False)
            if sent:
                self._pressed[token] = point
                self._debug_sent(f"{kind}:{name}")
            return bool(sent)

    def _release(self, token):
        with self._lock:
            if token not in self._pressed:
                return True
            kind, name = token
            if not self._identity_valid():
                self._log("[Bot] Input ignorado por segurança: destino da soltura não existe mais. Nenhum evento global enviado.")
                del self._pressed[token]
                self._pending.discard(token)
                return False
            if self.cfg.get("input_mode") == "messages":
                sent = self._key_message(name, True) if kind == "key" else self._mouse_message(name, True, self._pressed[token])
            elif not self.is_focused():
                if token not in self._pending:
                    self._log(f"[Bot] Input ignorado por segurança: soltura {name} adiada; volte à instância selecionada. Não enviaremos soltura à outra conta.")
                self._pending.add(token)
                return False
            else:
                sent = self._global_event(kind, name, True)
            if sent:
                del self._pressed[token]
                self._pending.discard(token)
            else:
                self._pending.add(token)
            return bool(sent)

    def release_all(self):
        with self._lock:
            for token in tuple(self._pressed):
                self._release(token)

    def key_down(self, name):
        return self._down("key", str(name).lower())

    def key_up(self, name):
        return self._release(("key", str(name).lower()))

    def mouse_down(self, button="left"):
        return self._down("mouse", button)

    def mouse_up(self, button="left"):
        return self._release(("mouse", button))

    def tap(self, name, hold=0.06):
        with self._lock:
            if not self.key_down(name):
                return False
            try:
                time.sleep(hold)
            finally:
                released = self.key_up(name)
            return released

    def click(self, button="left", hold=0.05):
        with self._lock:
            if not self.mouse_down(button):
                return False
            try:
                time.sleep(hold)
            finally:
                released = self.mouse_up(button)
            return released

    def click_at(self, x, y, button="left", restore=True):
        with self._lock:
            if self.blocked_reason() or not windows.contains(self.client_region(), x, y):
                return False
            if self.cfg.get("input_mode") == "messages":
                if not self._down("mouse", button, (x, y)):
                    return False
                try:
                    time.sleep(0.05)
                finally:
                    released = self.mouse_up(button)
                return released
            if not windows.point_belongs(self._target["hwnd"], x, y):
                self._log("[Bot] Input ignorado por segurança: destino do clique encoberto.")
                return False
            origin = raw.get_cursor_pos()
            if not self.is_focused():
                return False
            try:
                raw.move_to(x, y)
            except OSError as exc:
                self._log(f"[Bot] Movimento ignorado: {exc}")
                return False
            try:
                time.sleep(0.03)
                return self.click(button)
            finally:
                if restore and self.is_focused():
                    try:
                        raw.move_to(*origin)
                    except OSError as exc:
                        self._log(f"[Bot] Falha ao restaurar cursor: {exc}")
