"""Read-only Win32 discovery. Never changes the foreground window."""

import ctypes
import os
from ctypes import wintypes

import config

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
GAME_EXECUTABLES = frozenset({"trove.exe", "trove_x64.exe"})
_WindowCallback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _signature(dll, name, result, *args):
    function = getattr(dll, name)
    function.restype = result
    function.argtypes = list(args)


_signature(user32, "EnumWindows", wintypes.BOOL, _WindowCallback, wintypes.LPARAM)
_signature(user32, "IsWindow", wintypes.BOOL, wintypes.HWND)
_signature(user32, "IsWindowVisible", wintypes.BOOL, wintypes.HWND)
_signature(user32, "IsIconic", wintypes.BOOL, wintypes.HWND)
_signature(user32, "GetForegroundWindow", wintypes.HWND)
_signature(user32, "GetWindowTextLengthW", ctypes.c_int, wintypes.HWND)
_signature(user32, "GetWindowTextW", ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_signature(user32, "GetWindowThreadProcessId", wintypes.DWORD,
           wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_signature(user32, "GetClientRect", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_signature(user32, "ClientToScreen", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.POINT))
_signature(user32, "WindowFromPoint", wintypes.HWND, wintypes.POINT)
_signature(user32, "GetAncestor", wintypes.HWND, wintypes.HWND, wintypes.UINT)
_signature(kernel32, "OpenProcess", wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_signature(kernel32, "CloseHandle", wintypes.BOOL, wintypes.HANDLE)
_signature(kernel32, "QueryFullProcessImageNameW", wintypes.BOOL,
           wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
_signature(kernel32, "GetProcessTimes", wintypes.BOOL, wintypes.HANDLE,
           *([ctypes.POINTER(wintypes.FILETIME)] * 4))


def foreground_hwnd():
    return int(user32.GetForegroundWindow() or 0)


def window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def process_info(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        path = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(path))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return None
        # FILETIME exceeds JavaScript's safe integer range: keep it as text.
        return {"process_created": str(created), "exe": path.value}
    finally:
        kernel32.CloseHandle(handle)


def window_info(hwnd):
    if not hwnd or hwnd == 0xFFFF or not user32.IsWindow(hwnd):
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = process_info(pid.value)
    if not process:
        return None
    return {"hwnd": int(hwnd), "pid": pid.value, "title": window_title(hwnd), **process}


def same_identity(selected, current):
    return bool(selected and current and all(selected.get(key) == current.get(key)
                for key in ("hwnd", "pid", "process_created", "exe")))


def client_region(hwnd):
    rect, origin = wintypes.RECT(), wintypes.POINT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    return (origin.x, origin.y, width, height) if width > 0 and height > 0 else None


def contains(region, x, y):
    return bool(region and region[0] <= x < region[0] + region[2]
                and region[1] <= y < region[1] + region[3])


def point_belongs(hwnd, x, y):
    hit = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    return bool(hit and int(user32.GetAncestor(hit, 2) or 0) == hwnd)


def list_game_windows(cfg):
    """Executable allowlist + title filter; identity never depends on a title."""
    handles = []

    @_WindowCallback
    def collect(hwnd, _parameter):
        # No Python exceptions cross a native callback boundary.
        handles.append(int(hwnd))
        return True

    if not user32.EnumWindows(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    windows = []
    for hwnd in handles:
        if not user32.IsWindowVisible(hwnd):
            continue
        info = window_info(hwnd)
        if not info or info["pid"] == os.getpid():
            continue
        is_game = os.path.basename(info["exe"]).lower() in GAME_EXECUTABLES
        if is_game and (not config.window_titles(cfg) or config.matches_window(cfg, info["title"])):
            info["region"] = client_region(hwnd)
            windows.append(info)
    return sorted(windows, key=lambda item: (int(item["process_created"]), item["hwnd"]))
