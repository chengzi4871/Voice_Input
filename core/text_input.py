import ctypes
from ctypes import wintypes, Structure, POINTER, c_ulong, Union

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008


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


def send_unicode(text: str):
    """
    Use Windows SendInput with KEYEVENTF_UNICODE to directly inject
    Unicode characters into the active window's message queue.
    This bypasses the keyboard layout and IME entirely, avoiding
    conflicts with Chinese input methods.
    """
    if not text:
        return

    user32 = ctypes.windll.user32

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
