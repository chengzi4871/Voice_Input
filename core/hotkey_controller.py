import threading
import time
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from core.config_manager import HotkeyConfig, ProfileConfig
from core.logger import get_logger
from core.text_input import send_unicode


_KEY_NAME_TO_PYNPUT = {
    "space": Key.space, "tab": Key.tab, "enter": Key.enter,
    "escape": Key.esc, "esc": Key.esc, "backspace": Key.backspace,
    "delete": Key.delete, "caps_lock": Key.caps_lock,
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "home": Key.home, "end": Key.end, "page_up": Key.page_up,
    "page_down": Key.page_down, "insert": Key.insert, "menu": Key.menu,
    "print_screen": Key.print_screen, "scroll_lock": Key.scroll_lock,
    "pause": Key.pause,
}
for _i in range(1, 25):
    _KEY_NAME_TO_PYNPUT[f"f{_i}"] = getattr(Key, f"f{_i}", None)


def _key_name_to_pynput(name: str):
    lower = name.lower()
    if lower in _KEY_NAME_TO_PYNPUT:
        return _KEY_NAME_TO_PYNPUT[lower]
    if len(lower) == 1:
        return KeyCode.from_char(lower)
    return None


def _key_name_match(key_name: str, key) -> bool:
    lower = key_name.lower()
    if isinstance(key, Key):
        pynput_name = key.name.lower().replace("_l", "").replace("_r", "")
        if lower == pynput_name:
            return True
        mapped = _KEY_NAME_TO_PYNPUT.get(lower)
        if mapped is not None and key == mapped:
            return True
        return False
    if isinstance(key, KeyCode):
        ch = key.char
        if ch and lower == ch.lower():
            return True
        vk = key.vk
        if vk is not None:
            mapped = _KEY_NAME_TO_PYNPUT.get(lower)
            if mapped is not None and isinstance(mapped, KeyCode) and mapped.vk == vk:
                return True
            return False
        return False
    return False


def _format_key(key) -> str:
    if isinstance(key, Key):
        return key.name.replace("_l", "(L)").replace("_r", "(R)")
    if isinstance(key, KeyCode):
        ch = key.char
        if ch:
            return repr(ch)
        vk = key.vk
        return f"vk={vk}" if vk is not None else "?"
    return str(key)


class _HotkeyEntry:
    def __init__(self, hotkey: HotkeyConfig, profile_index: int):
        self.hotkey = hotkey
        self.profile_index = profile_index

    def _key_name(self, key) -> str:
        if isinstance(key, Key):
            return key.name.lower().replace("_l", "").replace("_r", "")
        if isinstance(key, KeyCode):
            ch = key.char
            if ch:
                return ch.lower()
            return str(key.vk)
        return ""

    def trigger_key_held(self, pressed_keys: set) -> bool:
        trigger_name = self.hotkey.key.lower()
        for k in pressed_keys:
            if _key_name_match(trigger_name, k):
                return True
        return False

    def is_active(self, pressed_keys: set) -> bool:
        held_names = {self._key_name(k) for k in pressed_keys}
        modifiers = set()
        if self.hotkey.ctrl:
            modifiers.add("ctrl")
        if self.hotkey.shift:
            modifiers.add("shift")
        if self.hotkey.alt:
            modifiers.add("alt")
        if not modifiers.issubset(held_names):
            return False
        if not self.trigger_key_held(pressed_keys):
            return False
        return True


class HotkeyController:
    def __init__(
        self,
        profiles: list[ProfileConfig],
        on_record_start,
        on_record_stop,
    ):
        self._profiles = profiles
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._recording = False
        self._active_profile_idx: int = 0
        self._pressed_keys: set = set()
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()
        self._log = get_logger()
        self._entries = self._build_entries()

    def _build_entries(self) -> list[_HotkeyEntry]:
        entries = []
        for idx, profile in enumerate(self._profiles):
            entries.append(_HotkeyEntry(profile.hotkey, idx))
        return entries

    def update_profiles(self, profiles: list[ProfileConfig]):
        was_listening = self._listener is not None
        if was_listening:
            self.stop_listening()
        self._profiles = profiles
        self._entries = self._build_entries()
        self._log.info(
            f"Hotkey: 更新 profiles, 共 {len(profiles)} 个: "
            + ", ".join(f"{p.name} -> {p.hotkey.to_string()}" for p in profiles)
        )
        if was_listening:
            self.start_listening()

    def _find_active_entry(self) -> _HotkeyEntry | None:
        for entry in self._entries:
            if entry.is_active(self._pressed_keys):
                return entry
        return None

    def _on_press(self, key):
        self._pressed_keys.add(key)
        active = self._find_active_entry()
        if active is not None:
            with self._lock:
                if not self._recording:
                    self._recording = True
                    self._active_profile_idx = active.profile_index
                    profile_name = self._profiles[active.profile_index].name
                    self._log.debug(
                        f"Hotkey: 热键触发 -> [{profile_name}] "
                        f"(hotkey={active.hotkey.to_string()})"
                    )
                    self._on_record_start(active.profile_index)

    def _on_release(self, key):
        if key in self._pressed_keys:
            self._pressed_keys.discard(key)

        was_recording = False
        with self._lock:
            if self._recording and self._find_active_entry() is None:
                self._recording = False
                was_recording = True

        if was_recording:
            self._log.debug("Hotkey: 热键释放 -> 停止录音")
            self._on_record_stop(self._active_profile_idx)

    def start_listening(self):
        if self._listener is not None:
            return
        names = ", ".join(p.hotkey.to_string() for p in self._profiles)
        self._log.info(f"Hotkey: 开始监听热键 -> {names}")
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop_listening(self):
        if self._listener is not None:
            self._log.debug("Hotkey: 停止监听")
            self._listener.stop()
            self._listener = None

    def type_text(self, text: str):
        self._log.debug(
            f"Hotkey: 输入文本, length={len(text)}, "
            f"preview={text[:60]}..."
        )
        time.sleep(0.05)
        send_unicode(text)
        self._log.debug("Hotkey: 输入完成")

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
