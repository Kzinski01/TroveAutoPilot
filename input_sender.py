"""Envio de input via SendInput com scancodes (compativel com DirectInput/jogos).

pyautogui usa codigos virtuais, que varios jogos ignoram. Aqui usamos scancodes
do teclado fisico, que e o que o Trove (e a maioria dos jogos) le.
"""

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# Assinaturas explicitas. Sem elas o ctypes trata HWND como int de 32 bits e
# trunca o handle em 64 bits - fonte classica de comportamento indefinido.
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]


# Scancodes set 1. Teclas "estendidas" marcadas com o bit 0xE000.
SCANCODES = {
    "escape": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B, "minus": 0x0C,
    "equal": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15,
    "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "enter": 0x1C, "ctrl": 0x1D, "left ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23,
    "j": 0x24, "k": 0x25, "l": 0x26,
    "shift": 0x2A, "left shift": 0x2A,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30, "n": 0x31,
    "m": 0x32, "comma": 0x33, "period": 0x34, "slash": 0x35,
    "right shift": 0x36, "alt": 0x38, "left alt": 0x38, "space": 0x39,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F, "f6": 0x40,
    "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44, "f11": 0x57, "f12": 0x58,
    "right ctrl": 0xE01D, "right alt": 0xE038,
    "up": 0xE048, "left": 0xE04B, "right": 0xE04D, "down": 0xE050,
    "insert": 0xE052, "delete": 0xE053, "home": 0xE047, "end": 0xE04F,
    "page up": 0xE049, "page down": 0xE051,
}

MOUSE_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


def _send(*inputs):
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise OSError(f"SendInput inseriu {sent}/{len(inputs)} eventos; erro={ctypes.get_last_error()}")
    return True


def _key_input(scan, keyup):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if keyup else 0)
    if scan & 0xE000 == 0xE000:
        flags |= KEYEVENTF_EXTENDEDKEY
    return INPUT(type=INPUT_KEYBOARD,
                 ki=KEYBDINPUT(wVk=0, wScan=scan & 0xFF, dwFlags=flags,
                               time=0, dwExtraInfo=0))


def key_down(name):
    scan = SCANCODES.get(str(name).lower())
    if scan is None:
        return False
    _send(_key_input(scan, False))
    return True


def key_up(name):
    scan = SCANCODES.get(str(name).lower())
    if scan is None:
        return False
    _send(_key_input(scan, True))
    return True


def tap(name, hold=0.06):
    """Pressiona e solta uma tecla. `hold` curto demais e ignorado por jogos."""
    if not key_down(name):
        return False
    time.sleep(hold)
    key_up(name)
    return True


def _mouse_input(flags, dx=0, dy=0):
    return INPUT(type=INPUT_MOUSE,
                 mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=flags,
                               time=0, dwExtraInfo=0))


def mouse_down(button="left"):
    down, _ = MOUSE_FLAGS.get(button, MOUSE_FLAGS["left"])
    return _send(_mouse_input(down))


def mouse_up(button="left"):
    _, up = MOUSE_FLAGS.get(button, MOUSE_FLAGS["left"])
    return _send(_mouse_input(up))


def click(button="left", hold=0.05):
    mouse_down(button)
    time.sleep(hold)
    mouse_up(button)


def get_cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def move_to(x, y):
    """Move o cursor em coordenadas absolutas de tela virtual."""
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    nx = int((x - left) * 65535 / max(width - 1, 1))
    ny = int((y - top) * 65535 / max(height - 1, 1))
    return _send(_mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | 0x4000, nx, ny))


def click_at(x, y, button="left", restore=True):
    """Clica em (x, y) e opcionalmente devolve o cursor para onde estava."""
    origin = get_cursor_pos()
    move_to(x, y)
    time.sleep(0.03)
    click(button)
    if restore:
        time.sleep(0.03)
        move_to(*origin)


def foreground_window_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin():
    """Reabre o script elevado. Sem isso o Windows (UIPI) descarta nosso
    SendInput quando o jogo roda como administrador."""
    import os
    import sys
    # --no-elevate evita loop caso a elevacao nao seja detectada depois.
    if getattr(sys, "frozen", False):
        # No exe, sys.executable ja e o proprio bot: nao repassar o script.
        target = sys.executable
        args = sys.argv[1:] + ["--no-elevate"]
        workdir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        target = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = [script] + sys.argv[1:] + ["--no-elevate"]
        workdir = os.path.dirname(script)
    params = " ".join(f'"{a}"' for a in args)
    # ShellExecuteW devolve <= 32 para erro (inclui o usuario recusar o UAC)
    status = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", target, params, workdir, 1)
    return status > 32


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
