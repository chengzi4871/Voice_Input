from PIL import Image, ImageDraw
import pystray
from core.logger import get_logger


def _create_icon_image(color: str, size: int = 32) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 3
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
    )
    return image


class TrayIcon:
    def __init__(
        self,
        on_settings,
        on_quit,
        on_auto_start_toggle,
    ):
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._on_auto_start_toggle = on_auto_start_toggle
        self._auto_start = False
        self._log = get_logger()

        self._icon_idle = _create_icon_image("gray")
        self._icon_recording = _create_icon_image("#FF4444")

        self._tray = pystray.Icon(
            "voice_input",
            self._icon_idle,
            "Voice Input",
            menu=self._build_menu(),
        )

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "Settings",
                self._settings_action,
                default=True,
            ),
            pystray.MenuItem(
                "Auto Start",
                self._auto_start_action,
                checked=lambda item: self._auto_start,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._quit_action,
            ),
        )

    def _settings_action(self):
        self._log.debug("托盘: 点击设置")
        self._on_settings()

    def _auto_start_action(self, icon, item):
        self._log.debug("托盘: 切换开机自启")
        self._on_auto_start_toggle()

    def _quit_action(self):
        self._log.debug("托盘: 点击退出")
        self.stop()
        self._on_quit()

    def set_recording(self, recording: bool):
        if recording:
            self._tray.icon = self._icon_recording
            self._tray.title = "Voice Input — Recording..."
        else:
            self._tray.icon = self._icon_idle
            self._tray.title = "Voice Input"
        self._tray.update_menu()

    def update_auto_start(self, enabled: bool):
        self._auto_start = enabled
        self._tray.update_menu()

    def show_notification(self, title: str, message: str):
        self._tray.notify(message, title)

    def run(self):
        self._tray.run()

    def stop(self):
        self._tray.stop()
