import ctypes
import queue
import threading
from ctypes import wintypes

from core.config_manager import HotkeyConfig, ProfileConfig


WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WM_USER = 0x0400
PM_NOREMOVE = 0x0000

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_PAUSE = 0x13
VK_CAPITAL = 0x14
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

CTRL_VKS = {VK_CONTROL, VK_LCONTROL, VK_RCONTROL}
SHIFT_VKS = {VK_SHIFT, VK_LSHIFT, VK_RSHIFT}
ALT_VKS = {VK_MENU, VK_LMENU, VK_RMENU}

SPECIAL_KEY_VKS = {
    "space": VK_SPACE,
    "tab": VK_TAB,
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "escape": VK_ESCAPE,
    "esc": VK_ESCAPE,
    "backspace": VK_BACK,
    "delete": VK_DELETE,
    "caps_lock": VK_CAPITAL,
    "capslock": VK_CAPITAL,
    "up": VK_UP,
    "down": VK_DOWN,
    "left": VK_LEFT,
    "right": VK_RIGHT,
    "home": VK_HOME,
    "end": VK_END,
    "page_up": VK_PRIOR,
    "pageup": VK_PRIOR,
    "page_down": VK_NEXT,
    "pagedown": VK_NEXT,
    "insert": VK_INSERT,
    "print_screen": VK_SNAPSHOT,
    "printscreen": VK_SNAPSHOT,
    "pause": VK_PAUSE,
}

ULONG_PTR = wintypes.WPARAM
LRESULT = wintypes.LPARAM
HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

USER32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
USER32.SetWindowsHookExW.restype = wintypes.HANDLE
USER32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
USER32.UnhookWindowsHookEx.restype = wintypes.BOOL
USER32.CallNextHookEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
USER32.CallNextHookEx.restype = LRESULT
USER32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
USER32.GetMessageW.restype = wintypes.BOOL
USER32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
USER32.TranslateMessage.restype = wintypes.BOOL
USER32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
USER32.DispatchMessageW.restype = LRESULT
USER32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
USER32.PostThreadMessageW.restype = wintypes.BOOL
USER32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
USER32.PeekMessageW.restype = wintypes.BOOL
KERNEL32.GetCurrentThreadId.argtypes = []
KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD
KERNEL32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
KERNEL32.GetModuleHandleW.restype = wintypes.HINSTANCE


def hotkey_key_to_vk(key_name: str) -> int | None:
    key = key_name.strip().lower()
    if not key:
        return None
    if len(key) == 1:
        return ord(key.upper())
    if key.startswith("f"):
        try:
            number = int(key[1:])
        except ValueError:
            return None
        if 1 <= number <= 24:
            return 0x6F + number
    return SPECIAL_KEY_VKS.get(key)


def _modifier_held(pressed_vks: set[int], modifier_vks: set[int]) -> bool:
    return bool(pressed_vks.intersection(modifier_vks))


class HotkeyEntry:
    def __init__(self, hotkey: HotkeyConfig, profile_index: int):
        self.hotkey = hotkey
        self.profile_index = profile_index
        self.trigger_vk = hotkey_key_to_vk(hotkey.key)

    def is_valid(self) -> bool:
        return self.trigger_vk is not None

    def is_trigger(self, vk_code: int) -> bool:
        return self.trigger_vk == vk_code

    def matches(self, pressed_vks: set[int]) -> bool:
        if self.trigger_vk is None or self.trigger_vk not in pressed_vks:
            return False
        if self.hotkey.ctrl and not _modifier_held(pressed_vks, CTRL_VKS):
            return False
        if self.hotkey.shift and not _modifier_held(pressed_vks, SHIFT_VKS):
            return False
        if self.hotkey.alt and not _modifier_held(pressed_vks, ALT_VKS):
            return False
        return True


class HotkeyEventProcessor:
    def __init__(
        self,
        profiles: list[ProfileConfig],
        on_record_start,
        on_record_stop,
    ):
        self._entries = [
            HotkeyEntry(profile.hotkey, idx)
            for idx, profile in enumerate(profiles)
        ]
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._pressed_vks: set[int] = set()
        self._recording = False
        self._active_entry: HotkeyEntry | None = None
        self._lock = threading.RLock()

    def handle_key_event(self, vk_code: int, is_down: bool) -> bool:
        with self._lock:
            if is_down:
                return self._handle_key_down(vk_code)
            return self._handle_key_up(vk_code)

    def reset(self):
        with self._lock:
            self._pressed_vks.clear()
            self._recording = False
            self._active_entry = None

    def _handle_key_down(self, vk_code: int) -> bool:
        self._pressed_vks.add(vk_code)
        active = self._find_active_entry()

        if active is not None and not self._recording:
            self._recording = True
            self._active_entry = active
            self._on_record_start(active.profile_index)

        if self._recording and self._active_entry is not None:
            return self._active_entry.is_trigger(vk_code)
        return active.is_trigger(vk_code) if active is not None else False

    def _handle_key_up(self, vk_code: int) -> bool:
        suppress = (
            self._recording
            and self._active_entry is not None
            and self._active_entry.is_trigger(vk_code)
        )

        self._pressed_vks.discard(vk_code)

        if (
            self._recording
            and self._active_entry is not None
            and not self._active_entry.matches(self._pressed_vks)
        ):
            profile_index = self._active_entry.profile_index
            self._recording = False
            self._active_entry = None
            self._on_record_stop(profile_index)

        return suppress

    def _find_active_entry(self) -> HotkeyEntry | None:
        for entry in self._entries:
            if entry.is_valid() and entry.matches(self._pressed_vks):
                return entry
        return None


class WindowsHotkeyHook:
    def __init__(
        self,
        profiles: list[ProfileConfig],
        on_record_start,
        on_record_stop,
        logger=None,
    ):
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._callback_queue: queue.Queue[tuple[str, int] | None] = queue.Queue()
        self._callback_thread: threading.Thread | None = None
        self._processor = HotkeyEventProcessor(
            profiles=profiles,
            on_record_start=self._enqueue_record_start,
            on_record_stop=self._enqueue_record_stop,
        )
        self._log = logger
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook_handle = None
        self._hook_proc = HOOKPROC(self._low_level_keyboard_proc)
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

    def start(self):
        if self._thread is not None:
            return
        self._ready.clear()
        self._start_error = None
        self._callback_thread = threading.Thread(
            target=self._callback_loop,
            name="VoiceInputHotkeyCallbacks",
            daemon=True,
        )
        self._callback_thread.start()
        self._thread = threading.Thread(
            target=self._message_loop,
            name="VoiceInputHotkeyHook",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=3.0):
            if self._thread_id is not None:
                USER32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=1.0)
            self._thread = None
            self._thread_id = None
            self._stop_callback_thread()
            raise TimeoutError("Timed out while starting hotkey hook")
        if self._start_error is not None:
            self._thread = None
            self._thread_id = None
            self._stop_callback_thread()
            raise self._start_error

    def stop(self):
        if self._thread is None:
            return
        if self._thread_id is not None:
            USER32.PostThreadMessageW(
                self._thread_id,
                WM_QUIT,
                0,
                0,
            )
        self._thread.join(timeout=3.0)
        if self._thread.is_alive():
            if self._log:
                self._log.error("Hotkey hook thread did not stop within timeout")
        else:
            self._thread = None
            self._thread_id = None
        self._processor.reset()
        self._stop_callback_thread()

    def _enqueue_record_start(self, profile_idx: int):
        self._callback_queue.put(("start", profile_idx))

    def _enqueue_record_stop(self, profile_idx: int):
        self._callback_queue.put(("stop", profile_idx))

    def _callback_loop(self):
        while True:
            item = self._callback_queue.get()
            if item is None:
                return

            action, profile_idx = item
            try:
                if action == "start":
                    self._on_record_start(profile_idx)
                else:
                    self._on_record_stop(profile_idx)
            except Exception as exc:
                if self._log:
                    self._log.error(f"Hotkey callback failed: {exc}")

    def _stop_callback_thread(self):
        if self._callback_thread is None:
            return
        self._callback_queue.put(None)
        self._callback_thread.join(timeout=3.0)
        self._callback_thread = None

    def _message_loop(self):
        self._thread_id = KERNEL32.GetCurrentThreadId()
        msg = MSG()
        USER32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)

        try:
            module_handle = KERNEL32.GetModuleHandleW(None)
            self._hook_handle = USER32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._hook_proc,
                module_handle,
                0,
            )
            if not self._hook_handle:
                raise ctypes.WinError(ctypes.get_last_error())

            self._ready.set()
            while USER32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                USER32.TranslateMessage(ctypes.byref(msg))
                USER32.DispatchMessageW(ctypes.byref(msg))
        except BaseException as exc:
            self._start_error = exc
            self._ready.set()
            if self._log:
                self._log.error(f"Hotkey hook failed: {exc}")
        finally:
            if self._hook_handle:
                USER32.UnhookWindowsHookEx(self._hook_handle)
                self._hook_handle = None

    def _low_level_keyboard_proc(self, n_code, w_param, l_param):
        if n_code != HC_ACTION:
            return USER32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

        if w_param not in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
            return USER32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

        event = ctypes.cast(
            l_param,
            ctypes.POINTER(KBDLLHOOKSTRUCT),
        ).contents
        is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)

        try:
            suppress = self._processor.handle_key_event(event.vkCode, is_down)
        except Exception as exc:
            suppress = False
            if self._log:
                self._log.error(f"Hotkey event handling failed: {exc}")

        if suppress:
            return 1
        return USER32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)
