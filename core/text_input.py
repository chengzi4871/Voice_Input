import ctypes
import os
import time
from ctypes import wintypes, Structure, POINTER, c_ulong, Union

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001

VK_CONTROL = 0x11
VK_V = 0x56

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_clipboard_app_names = {"wechat.exe", "weixin.exe"}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SendInput.argtypes = (wintypes.UINT, wintypes.LPVOID, ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.argtypes = ()
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (
    wintypes.HWND,
    POINTER(wintypes.DWORD),
)
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetClassNameW.restype = ctypes.c_int
user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = ()
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = ()
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = (wintypes.UINT,)
user32.GetClipboardData.restype = wintypes.HANDLE
user32.EnumClipboardFormats.argtypes = (wintypes.UINT,)
user32.EnumClipboardFormats.restype = wintypes.UINT

kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalSize.restype = ctypes.c_size_t


class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", POINTER(c_ulong)),
    ]


class _INPUT_UNION(Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", ctypes.c_char * 28),
        ("hi", ctypes.c_char * 28),
    ]


class INPUT(Structure):
    _anonymous_ = ("_union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_union", _INPUT_UNION),
    ]


def send_text(text: str) -> str:
    """
    Send text to the active control and return the transport used.

    WeChat's Windows input box mishandles VK_PACKET/KEYEVENTF_UNICODE around
    Chinese punctuation, so use paste there and keep SendInput elsewhere.
    """
    if not text:
        return "none"

    if should_use_clipboard_for_foreground_window():
        paste_unicode(text)
        return "clipboard"

    send_unicode(text)
    return "unicode"


def configure_clipboard_app_names(app_names: list[str]):
    global _clipboard_app_names
    _clipboard_app_names = _normalize_app_names(app_names)


def get_clipboard_app_names() -> list[str]:
    return sorted(_clipboard_app_names)


def send_unicode(text: str):
    """
    Use Windows SendInput with KEYEVENTF_UNICODE to directly inject
    Unicode characters into the active window's message queue.
    This bypasses the keyboard layout and IME entirely, avoiding
    conflicts with Chinese input methods.
    """
    if not text:
        return

    inputs = (INPUT * (len(text) * 2))()

    for i, ch in enumerate(text):
        code = ord(ch)

        idx_down = i * 2
        idx_up = i * 2 + 1

        inputs[idx_down].type = INPUT_KEYBOARD
        inputs[idx_down].ki.wVk = 0
        inputs[idx_down].ki.wScan = code
        inputs[idx_down].ki.dwFlags = KEYEVENTF_UNICODE

        inputs[idx_up].type = INPUT_KEYBOARD
        inputs[idx_up].ki.wVk = 0
        inputs[idx_up].ki.wScan = code
        inputs[idx_up].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))


def paste_unicode(text: str, restore_delay: float = 0.2):
    if not text:
        return

    saved_formats = _snapshot_clipboard()
    try:
        _set_clipboard_unicode_text(text)
        _send_ctrl_v()
        time.sleep(restore_delay)
    finally:
        try:
            _restore_clipboard(saved_formats)
        except OSError:
            pass


def should_use_clipboard_for_foreground_window() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    process_name = _get_window_process_name(hwnd)
    if process_name in _clipboard_app_names:
        return True

    title = _get_window_text(hwnd)
    class_name = _get_window_class_name(hwnd)
    return _window_hint_matches_clipboard_app(title, class_name)


def is_wechat_foreground_window() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    process_name = _get_window_process_name(hwnd)
    title = _get_window_text(hwnd)
    class_name = _get_window_class_name(hwnd)
    return (
        process_name in {"wechat.exe", "weixin.exe"}
        or "微信" in title
        or class_name.startswith("WeChat")
    )


def _normalize_app_names(app_names: list[str]) -> set[str]:
    names = set()
    for name in app_names:
        normalized = os.path.basename(str(name).strip().lower())
        if not normalized:
            continue
        if "." not in normalized:
            normalized = f"{normalized}.exe"
        names.add(normalized)
    return names


def _window_hint_matches_clipboard_app(title: str, class_name: str) -> bool:
    if "wechat.exe" in _clipboard_app_names or "weixin.exe" in _clipboard_app_names:
        return "微信" in title or class_name.startswith("WeChat")
    return False


def _get_window_process_name(hwnd) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid.value,
    )
    if not handle:
        return ""

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return ""
        return os.path.basename(buffer.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def _get_window_text(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _get_window_class_name(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _snapshot_clipboard() -> list[tuple[int, bytes]]:
    formats: list[tuple[int, bytes]] = []
    _open_clipboard()
    try:
        fmt = 0
        while True:
            fmt = user32.EnumClipboardFormats(fmt)
            if fmt == 0:
                break

            handle = user32.GetClipboardData(fmt)
            if not handle:
                continue

            size = kernel32.GlobalSize(handle)
            if size == 0:
                continue

            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                continue
            try:
                formats.append((fmt, ctypes.string_at(ptr, size)))
            finally:
                kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    return formats


def _set_clipboard_unicode_text(text: str):
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = _global_alloc_bytes(data)

    _open_clipboard()
    try:
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise ctypes.WinError(ctypes.get_last_error())
    except Exception:
        # Ownership stays with us if SetClipboardData failed.
        raise
    finally:
        user32.CloseClipboard()


def _restore_clipboard(formats: list[tuple[int, bytes]]):
    _open_clipboard()
    try:
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        for fmt, data in formats:
            handle = _global_alloc_bytes(data)
            user32.SetClipboardData(fmt, handle)
    finally:
        user32.CloseClipboard()


def _global_alloc_bytes(data: bytes):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        kernel32.GlobalUnlock(handle)

    return handle


def _open_clipboard(timeout: float = 1.0):
    deadline = time.monotonic() + timeout
    while True:
        if user32.OpenClipboard(None):
            return
        if time.monotonic() >= deadline:
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.01)


def _send_ctrl_v():
    inputs = (INPUT * 4)()

    inputs[0].type = INPUT_KEYBOARD
    inputs[0].ki.wVk = VK_CONTROL
    inputs[0].ki.dwFlags = 0

    inputs[1].type = INPUT_KEYBOARD
    inputs[1].ki.wVk = VK_V
    inputs[1].ki.dwFlags = 0

    inputs[2].type = INPUT_KEYBOARD
    inputs[2].ki.wVk = VK_V
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP

    inputs[3].type = INPUT_KEYBOARD
    inputs[3].ki.wVk = VK_CONTROL
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP

    sent = user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise ctypes.WinError(ctypes.get_last_error())
