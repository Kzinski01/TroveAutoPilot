"""Garante uma unica instancia do bot rodando.

Duas instancias brigam de verdade: cada uma registra os atalhos globais (o F5
chega nas duas) e cada uma comanda o mouse — uma segura o botao enquanto a
outra solta. O resultado parece "o bot parou de funcionar".
"""

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

# Assinaturas explicitas: sem elas HANDLE/HWND viram int de 32 bits e o
# handle e truncado em 64 bits.
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.ReleaseMutex.restype = wintypes.BOOL
kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

# "Global\\" para valer entre sessoes; o nome precisa ser estavel entre versoes
MUTEX_NAME = "Global\\TroveAutoBot_SingleInstance"
WINDOW_TITLE = "Trove AutoBot"

_handle = None      # mantido vivo pelo processo inteiro


def acquire():
    """True se esta e a unica instancia. False se ja existe outra rodando."""
    global _handle
    _handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def release():
    """Solta o mutex. Necessario antes de relancar o processo elevado, que
    precisa conseguir o mesmo mutex para si."""
    global _handle
    if _handle:
        kernel32.ReleaseMutex(_handle)
        kernel32.CloseHandle(_handle)
        _handle = None


def focus_existing():
    """Traz a janela da instancia que ja esta aberta para a frente."""
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True
