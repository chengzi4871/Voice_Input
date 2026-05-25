import os
import sys
import threading
import winreg
import customtkinter as ctk
from core.config_manager import ConfigManager, AppConfig
from core.text_input import configure_clipboard_app_names
from core.recorder import AudioRecorder
from core.transcriber import GeminiTranscriber
from core.hotkey_controller import HotkeyController
from core.logger import setup_logging
from ui.tray_icon import TrayIcon
from ui.settings_window import SettingsWindow

APP_NAME = "VoiceInput"
REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


class VoiceInputApp:
    def __init__(self):
        self._config_manager = ConfigManager()
        cfg = self._config_manager.config
        self._log = setup_logging(cfg.log_level)
        configure_clipboard_app_names(cfg.clipboard_app_names)
        self._log.info("Voice Input 应用初始化开始")
        self._log.debug(
            f"配置加载: model={cfg.model} "
            f"profiles={len(cfg.profiles)} "
            f"auto_start={cfg.auto_start}"
        )
        for p in cfg.profiles:
            self._log.debug(f"  Profile: [{p.name}] hotkey={p.hotkey.to_string()}")

        self._recorder = AudioRecorder()
        self._transcriber = GeminiTranscriber(cfg)
        self._settings_window: SettingsWindow | None = None
        self._pending_settings = False
        self._active_profile_idx: int = 0

        self._hotkey_controller = HotkeyController(
            profiles=cfg.profiles,
            on_record_start=self._on_record_start,
            on_record_stop=self._on_record_stop,
        )

        self._tray = TrayIcon(
            on_settings=self._request_open_settings,
            on_quit=self._on_quit,
            on_auto_start_toggle=self._toggle_auto_start,
        )
        self._tray.update_auto_start(cfg.auto_start)

        self._root = ctk.CTk()
        self._root.withdraw()
        self._root.title("")
        self._log.debug("隐藏 tkinter root 窗口已创建")

    def run(self):
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self._log.info("主题设置: 跟随系统")

        self._ensure_auto_start()

        self._hotkey_controller.start_listening()

        tray_thread = threading.Thread(target=self._tray.run, daemon=True)
        tray_thread.start()
        self._log.debug("系统托盘线程已启动")

        self._root.after(1000, self._show_initial_notification)
        self._root.after(100, self._check_pending_settings)

        self._log.info("Voice Input 启动完成，等待热键...")
        self._root.mainloop()

    def _show_initial_notification(self):
        if self._config_manager.config.first_run:
            self._config_manager.update(first_run=False)
            self._log.info("首次运行提示已显示")
        self._tray.show_notification(
            "Voice Input",
            "Alt+X: 开发者语音输入\nAlt+C: 正式书面沟通\n右键托盘图标进入设置"
        )

    def _check_pending_settings(self):
        if self._pending_settings:
            self._pending_settings = False
            self._open_settings()
        self._root.after(200, self._check_pending_settings)

    def _request_open_settings(self):
        self._pending_settings = True

    def _ensure_auto_start(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, APP_NAME)
                current_state = True
            except FileNotFoundError:
                current_state = False
            winreg.CloseKey(key)

            if self._config_manager.config.auto_start != current_state:
                self._log.debug("开机自启状态不一致，同步中...")
                self._set_auto_start(self._config_manager.config.auto_start)
        except OSError:
            pass

    def _set_auto_start(self, enable: bool):
        exe_path = self._config_manager.get_exe_path()
        if not exe_path:
            exe_path = sys.executable
            if not exe_path.endswith(".exe"):
                self._log.debug("非 exe 运行模式, 跳过开机自启设置")
                return

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE
            )
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                self._log.info(f"开机自启已启用: {exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                self._log.info("开机自启已禁用")
            winreg.CloseKey(key)
        except OSError as e:
            self._log.error(f"开机自启设置失败: {e}")

    def _toggle_auto_start(self):
        new_state = not self._config_manager.config.auto_start
        self._log.info(f"切换开机自启: {new_state}")
        self._config_manager.update(auto_start=new_state)
        self._set_auto_start(new_state)
        self._tray.update_auto_start(new_state)
        suffix = "已启用" if new_state else "已禁用"
        self._tray.show_notification("Voice Input", f"开机自启{suffix}")

    def _on_record_start(self, profile_idx: int):
        self._active_profile_idx = profile_idx
        profile = self._config_manager.config.profiles[profile_idx]
        self._log.debug(f"开始录音: [{profile.name}]")
        try:
            self._recorder.start()
            self._tray.set_recording(True)
        except Exception as e:
            self._log.error(f"启动录音失败: {e}")
            self._tray.show_notification("Voice Input", f"录音启动失败: {e}")

    def _on_record_stop(self, profile_idx: int):
        if not self._recorder.is_recording:
            return
        audio_buffer = self._recorder.stop()
        self._tray.set_recording(False)

        audio_bytes = audio_buffer.read()
        if len(audio_bytes) < 3200:
            self._log.debug(f"音频数据太短: {len(audio_bytes)} bytes, 忽略")
            return

        self._log.debug(
            f"音频数据: {len(audio_bytes)} bytes, 开始异步转写 "
            f"[profile={profile_idx}]"
        )
        audio_buffer.seek(0)

        threading.Thread(
            target=self._transcribe_and_type,
            args=(audio_buffer, profile_idx),
            daemon=True,
        ).start()

    def _transcribe_and_type(self, audio_buffer, profile_idx: int):
        profile = self._config_manager.config.profiles[profile_idx]
        prompt = profile.system_prompt or self._config_manager.config.system_prompt
        self._log.debug(f"转写使用 profile: [{profile.name}] prompt_len={len(prompt)}")

        try:
            text = self._transcriber.transcribe(audio_buffer, system_prompt=prompt)
        except ValueError:
            self._log.warning("转写失败: API Key 未配置")
            self._tray.show_notification(
                "Voice Input",
                "API 密钥未配置，请打开设置填写 API Key",
            )
            return
        except Exception as e:
            self._log.error(f"转写异常: {type(e).__name__}: {e}")
            msg = str(e)[:200]
            self._tray.show_notification("Voice Input Error", msg)
            return

        if text:
            try:
                self._hotkey_controller.type_text(text)
            except Exception as e:
                self._log.error(f"模拟输入失败: {e}")
                self._tray.show_notification(
                    "Voice Input Error", f"输入失败: {e}"
                )
        else:
            self._log.debug("转写结果为空, 未输入任何文本")

    def _open_settings(self):
        self._log.debug("打开设置窗口")
        if self._settings_window is not None:
            self._settings_window.show()
            return

        self._settings_window = SettingsWindow(
            config=self._config_manager.config,
            on_save=self._on_settings_save,
            on_cancel=self._settings_window_closed,
        )
        self._settings_window.show()

    def _on_settings_save(self, config: AppConfig):
        self._log.info("保存设置")
        self._config_manager.update(
            api_key=config.api_key,
            proxy=config.proxy,
            base_url=config.base_url,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            top_p=config.top_p,
            max_output_tokens=config.max_output_tokens,
            thinking_level=config.thinking_level,
            thinking_budget=config.thinking_budget,
            profiles=config.profiles,
            auto_start=config.auto_start,
            clipboard_app_names=config.clipboard_app_names,
            log_level=config.log_level,
        )
        self._log = setup_logging(config.log_level)
        configure_clipboard_app_names(config.clipboard_app_names)
        self._transcriber.update_config(self._config_manager.config)
        self._hotkey_controller.update_profiles(config.profiles)
        self._set_auto_start(config.auto_start)
        self._tray.update_auto_start(config.auto_start)
        self._settings_window_closed()

    def _settings_window_closed(self):
        self._log.debug("设置窗口已关闭")
        self._settings_window = None

    def _on_quit(self):
        self._log.info("退出应用")
        self._hotkey_controller.stop_listening()
        os._exit(0)


def main():
    app = VoiceInputApp()
    app.run()


if __name__ == "__main__":
    main()
