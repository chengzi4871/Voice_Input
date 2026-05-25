import threading
import time

from core.config_manager import ProfileConfig
from core.logger import get_logger
from core.text_input import send_text
from core.windows_hotkey_hook import WindowsHotkeyHook


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
        self._hook: WindowsHotkeyHook | None = None
        self._lock = threading.Lock()
        self._log = get_logger()

    def update_profiles(self, profiles: list[ProfileConfig]):
        was_listening = self._hook is not None
        if was_listening:
            self.stop_listening()

        self._profiles = profiles
        self._log.info(
            f"Hotkey: update profiles, total={len(profiles)} "
            + ", ".join(f"{p.name} -> {p.hotkey.to_string()}" for p in profiles)
        )

        if was_listening:
            self.start_listening()

    def _handle_record_start(self, profile_idx: int):
        should_start = False
        with self._lock:
            if not self._recording:
                self._recording = True
                self._active_profile_idx = profile_idx
                should_start = True

        if should_start:
            profile_name = self._profiles[profile_idx].name
            hotkey = self._profiles[profile_idx].hotkey.to_string()
            self._log.debug(
                f"Hotkey: triggered -> [{profile_name}] "
                f"(hotkey={hotkey})"
            )
            self._on_record_start(profile_idx)

    def _handle_record_stop(self, profile_idx: int):
        should_stop = False
        with self._lock:
            if self._recording:
                self._recording = False
                should_stop = True

        if should_stop:
            self._log.debug("Hotkey: released -> stop recording")
            self._on_record_stop(profile_idx)

    def start_listening(self):
        if self._hook is not None:
            return

        names = ", ".join(p.hotkey.to_string() for p in self._profiles)
        self._log.info(f"Hotkey: start Windows low-level hook -> {names}")
        self._hook = WindowsHotkeyHook(
            profiles=self._profiles,
            on_record_start=self._handle_record_start,
            on_record_stop=self._handle_record_stop,
            logger=self._log,
        )
        self._hook.start()

    def stop_listening(self):
        if self._hook is not None:
            self._log.debug("Hotkey: stop listening")
            self._hook.stop()
            self._hook = None

    def type_text(self, text: str):
        self._log.debug(
            f"Hotkey: input text, length={len(text)}, "
            f"preview={text[:60]}..."
        )
        time.sleep(0.05)
        transport = send_text(text)
        self._log.debug(f"Hotkey: input completed via {transport}")

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
