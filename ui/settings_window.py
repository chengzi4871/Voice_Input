import customtkinter as ctk
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from core.config_manager import AppConfig, HotkeyConfig, ProfileConfig
from core.logger import get_logger, get_log_path


_DEFAULT_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
]

_MODIFIER_KEYS = {
    Key.ctrl_l, Key.ctrl_r,
    Key.shift_l, Key.shift_r,
    Key.alt_l, Key.alt_r,
    Key.cmd_l, Key.cmd_r,
}


def _is_modifier_type(key) -> bool:
    return key in _MODIFIER_KEYS


def _key_to_display(key) -> str:
    if isinstance(key, Key):
        name = key.name.lower()
        if "ctrl" in name: return "Ctrl"
        if "shift" in name: return "Shift"
        if "alt" in name: return "Alt"
        if "cmd" in name: return "Win"
        name = key.name
        if name == "space": return "Space"
        if name == "tab": return "Tab"
        if name == "enter": return "Enter"
        if name == "backspace": return "Backspace"
        if name == "delete": return "Delete"
        if name == "escape": return "Esc"
        if name == "caps_lock": return "CapsLock"
        if name in ("up", "down", "left", "right"): return name.title()
        if len(name) == 1: return name.upper()
        return key.name.title()
    if isinstance(key, KeyCode):
        ch = key.char
        if ch:
            if ch == " ": return "Space"
            return ch.upper() if ch.isalpha() else ch
        vk = key.vk
        if vk is None: return str(key)
        if 0x60 <= vk <= 0x6F: return f"Num{vk - 0x60}"
        if 0x70 <= vk <= 0x87: return f"F{vk - 0x6F}"
        return str(key)
    return str(key)


def _key_to_config_char(key) -> str:
    if isinstance(key, Key):
        name = key.name
        lower = name.lower()
        if "ctrl" in lower: return "ctrl"
        if "shift" in lower: return "shift"
        if "alt" in lower: return "alt"
        if "cmd" in lower: return "cmd"
        if name == "space": return "space"
        if name == "tab": return "tab"
        if name == "enter": return "enter"
        if name in ("up", "down", "left", "right", "escape",
                     "backspace", "delete", "caps_lock",
                     "home", "end", "page_up", "page_down",
                     "insert", "print_screen", "scroll_lock",
                     "pause", "menu"):
            return name
        if len(name) == 1: return name.lower()
        return ""
    if isinstance(key, KeyCode):
        ch = key.char
        if ch: return ch.lower() if ch.isalpha() else ch
        vk = key.vk
        if vk is not None and 0x70 <= vk <= 0x87: return f"f{vk - 0x6F}"
    return ""


class SettingsWindow:
    def __init__(self, config: AppConfig, on_save, on_cancel):
        self._config = config
        self._on_save = on_save
        self._on_cancel = on_cancel
        self._window: ctk.CTkToplevel | None = None
        self._is_open = False
        self._log = get_logger()

        self._profiles: list[ProfileConfig] = [
            ProfileConfig(name=p.name, hotkey=HotkeyConfig(
                key=p.hotkey.key, ctrl=p.hotkey.ctrl,
                shift=p.hotkey.shift, alt=p.hotkey.alt,
            ), system_prompt=p.system_prompt)
            for p in config.profiles
        ]

        self._api_key_var: ctk.StringVar | None = None
        self._proxy_var: ctk.StringVar | None = None
        self._base_url_var: ctk.StringVar | None = None
        self._model_var: ctk.StringVar | None = None
        self._custom_model_var: ctk.StringVar | None = None
        self._temperature_var: ctk.StringVar | None = None
        self._top_p_var: ctk.StringVar | None = None
        self._max_tokens_var: ctk.StringVar | None = None
        self._thinking_level_var: ctk.StringVar | None = None
        self._thinking_budget_var: ctk.StringVar | None = None
        self._auto_start_var: ctk.BooleanVar | None = None
        self._log_level_var: ctk.StringVar | None = None
        self._clipboard_apps_text: ctk.CTkTextbox | None = None

        self._api_key_showing = False
        self._api_key_entry: ctk.CTkEntry | None = None
        self._custom_model_entry: ctk.CTkEntry | None = None

        self._selected_profile_idx: int = -1
        self._profile_name_var: ctk.StringVar | None = None
        self._profile_hotkey_var: ctk.StringVar | None = None
        self._profile_prompt_text: ctk.CTkTextbox | None = None
        self._profile_list_frame: ctk.CTkScrollableFrame | None = None
        self._profile_buttons: list[ctk.CTkButton] = []
        self._profile_radio_var: ctk.IntVar | None = None

        self._hotkey_recording = False
        self._hotkey_listener: keyboard.Listener | None = None
        self._captured_hotkey: HotkeyConfig | None = None
        self._recorded_keys: list = []
        self._held_keys: set = set()
        self._record_btn: ctk.CTkButton | None = None

    def show(self):
        if self._is_open:
            self._window.focus()
            return

        self._is_open = True
        self._window = ctk.CTkToplevel()
        self._window.title("语音输入法 设置")
        self._window.geometry("600x820")
        self._window.minsize(500, 650)
        self._window.resizable(True, True)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._window.attributes("-topmost", True)
        self._window.after(200, lambda: self._window.attributes("-topmost", False))

        self._build_ui()
        self._window.bind("<Escape>", lambda e: self._cancel())

    def _on_close(self):
        self._is_open = False
        self._stop_hotkey_recording()
        if self._window:
            self._window.destroy()
            self._window = None

    def _build_ui(self):
        tabview = ctk.CTkTabview(self._window)
        tabview.pack(fill="both", expand=True, padx=4, pady=(4, 0))
        tabview.add("基础设置")
        tabview.add("高级设置")

        container = ctk.CTkScrollableFrame(
            tabview.tab("基础设置"), fg_color="transparent", label_text="",
        )
        container.pack(fill="both", expand=True, padx=0, pady=0)

        advanced = ctk.CTkScrollableFrame(
            tabview.tab("高级设置"), fg_color="transparent", label_text="",
        )
        advanced.pack(fill="both", expand=True, padx=0, pady=0)

        title = ctk.CTkLabel(
            container, text="语音输入法 设置",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(anchor="w", pady=(8, 12))

        self._build_api_key_section(container)
        self._build_model_section(container)
        self._build_params_section(container)
        self._build_proxy_section(container)
        self._build_base_url_section(container)
        self._build_profile_section(container)
        self._build_auto_start_section(container)
        self._build_advanced_section(advanced)
        self._build_buttons(self._window)

    def _section_label(self, parent, text):
        l = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(weight="bold"))
        l.pack(anchor="w", pady=(10, 2))
        return l

    def _section_hint(self, parent, text):
        h = ctk.CTkLabel(parent, text=text, text_color="gray", font=ctk.CTkFont(size=10))
        h.pack(anchor="w", pady=(0, 4))
        return h

    def _build_api_key_section(self, parent):
        self._section_label(parent, "API 密钥")
        self._section_hint(parent, "在 Google AI Studio 获取免费 API 密钥: aistudio.google.com/apikey")
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        self._api_key_var = ctk.StringVar(value=self._config.api_key)
        self._api_key_entry = ctk.CTkEntry(row, textvariable=self._api_key_var, show="*", height=32)
        self._api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(row, text="显示", width=50, height=32, font=ctk.CTkFont(size=11),
                      command=self._toggle_api_key_visibility).pack(side="right")

    def _toggle_api_key_visibility(self):
        self._api_key_showing = not self._api_key_showing
        if self._api_key_entry:
            self._api_key_entry.configure(show="" if self._api_key_showing else "*")

    def _build_model_section(self, parent):
        self._section_label(parent, "模型选择")
        self._section_hint(parent, "gemini-3.5-flash: 最新最快  |  gemini-3.1-flash-lite: 成本更低")
        current_model = self._config.model
        is_custom = current_model not in _DEFAULT_MODELS
        self._model_var = ctk.StringVar(value=current_model if not is_custom else "custom")
        ctk.CTkOptionMenu(parent, values=_DEFAULT_MODELS + ["自定义模型..."],
                          variable=self._model_var, height=32, font=ctk.CTkFont(size=11),
                          command=self._on_model_dropdown_change).pack(fill="x", pady=(0, 4))
        self._custom_model_var = ctk.StringVar(value=current_model if is_custom else "")
        self._custom_model_entry = ctk.CTkEntry(parent, textvariable=self._custom_model_var,
                                                 height=32, font=ctk.CTkFont(size=11),
                                                 placeholder_text="输入自定义模型名称...")
        self._custom_model_entry.pack(fill="x", pady=(0, 8))
        if not is_custom:
            self._custom_model_entry.configure(state="disabled", fg_color="#3a3a3a")

    def _on_model_dropdown_change(self, value):
        if value == "自定义模型...":
            self._custom_model_entry.configure(state="normal", fg_color=None)
        else:
            self._custom_model_entry.configure(state="disabled", fg_color="#3a3a3a")

    def _get_selected_model(self) -> str:
        selected = self._model_var.get()
        if selected == "自定义模型...":
            return self._custom_model_var.get().strip()
        return selected

    def _build_params_section(self, parent):
        self._section_label(parent, "生成参数")
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 8))
        grid.columnconfigure(0, weight=0); grid.columnconfigure(1, weight=1)

        ctk.CTkLabel(grid, text="Temperature", font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
        self._temperature_var = ctk.StringVar(value=str(self._config.temperature))
        ctk.CTkEntry(grid, textvariable=self._temperature_var, height=28, width=80).grid(row=0, column=1, sticky="w", pady=2)

        ctk.CTkLabel(grid, text="Top P", font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)
        self._top_p_var = ctk.StringVar(value=str(self._config.top_p))
        ctk.CTkEntry(grid, textvariable=self._top_p_var, height=28, width=80).grid(row=1, column=1, sticky="w", pady=2)

        ctk.CTkLabel(grid, text="最大输出 Token", font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=2)
        self._max_tokens_var = ctk.StringVar(value=str(self._config.max_output_tokens))
        ctk.CTkEntry(grid, textvariable=self._max_tokens_var, height=28, width=80).grid(row=2, column=1, sticky="w", pady=2)

        self._section_label(parent, "思考控制 (Gemini 3/2.5 模型)")
        r1 = ctk.CTkFrame(parent, fg_color="transparent"); r1.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(r1, text="思考等级 (3.x)", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        self._thinking_level_var = ctk.StringVar(value=self._config.thinking_level if self._config.thinking_level else "不设置")
        ctk.CTkOptionMenu(r1, values=["不设置", "minimal", "low", "medium", "high"],
                          variable=self._thinking_level_var, height=28, font=ctk.CTkFont(size=11), width=120).pack(side="right")

        r2 = ctk.CTkFrame(parent, fg_color="transparent"); r2.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(r2, text="思考预算 (2.x)", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        budget_text = ""
        if self._config.thinking_budget >= 0: budget_text = str(self._config.thinking_budget)
        elif self._config.thinking_budget == -1: budget_text = "-1"
        self._thinking_budget_var = ctk.StringVar(value=budget_text)
        ctk.CTkEntry(r2, textvariable=self._thinking_budget_var, height=28, width=120,
                     font=ctk.CTkFont(size=11), placeholder_text="空=不设置").pack(side="right")

    def _build_proxy_section(self, parent):
        self._section_label(parent, "代理设置 (可选)")
        self._section_hint(parent, "例: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080")
        self._proxy_var = ctk.StringVar(value=self._config.proxy)
        ctk.CTkEntry(parent, textvariable=self._proxy_var, height=32, font=ctk.CTkFont(size=11)).pack(fill="x", pady=(0, 8))

    def _build_base_url_section(self, parent):
        self._section_label(parent, "自定义 Base URL (可选)")
        self._section_hint(parent, "用于 API 网关代理。留空使用默认地址")
        self._base_url_var = ctk.StringVar(value=self._config.base_url)
        ctk.CTkEntry(parent, textvariable=self._base_url_var, height=32, font=ctk.CTkFont(size=11)).pack(fill="x", pady=(0, 8))

    def _build_profile_section(self, parent):
        self._section_label(parent, "模式/Profile 管理")
        self._section_hint(parent, "每个 Profile 绑定一个快捷键和一套提示词。按下不同快捷键使用不同提示词转写")

        top_row = ctk.CTkFrame(parent, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(top_row, text="新增 Profile", width=100, height=28, font=ctk.CTkFont(size=11),
                      command=self._add_profile).pack(side="left", padx=(0, 4))
        ctk.CTkButton(top_row, text="删除当前", width=80, height=28, font=ctk.CTkFont(size=11),
                      fg_color="#AA3333", hover_color="#CC4444",
                      command=self._remove_profile).pack(side="left")

        list_frame = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        list_frame.pack(fill="x", pady=(4, 6))

        self._profile_radio_var = ctk.IntVar(value=0)
        self._profile_list_frame = list_frame
        self._refresh_profile_list()

        name_row = ctk.CTkFrame(parent, fg_color="transparent")
        name_row.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(name_row, text="名称:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        self._profile_name_var = ctk.StringVar(value="")
        ctk.CTkEntry(name_row, textvariable=self._profile_name_var, height=28, width=200,
                     font=ctk.CTkFont(size=11)).pack(side="left")

        hotkey_row = ctk.CTkFrame(parent, fg_color="transparent")
        hotkey_row.pack(fill="x", pady=(2, 4))
        ctk.CTkLabel(hotkey_row, text="快捷键:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        self._profile_hotkey_var = ctk.StringVar(value="")
        ctk.CTkEntry(hotkey_row, textvariable=self._profile_hotkey_var, height=28,
                     font=ctk.CTkFont(size=11), state="readonly", width=160).pack(side="left", padx=(0, 6))
        self._record_btn = ctk.CTkButton(hotkey_row, text="录制", width=50, height=28,
                                         font=ctk.CTkFont(size=11),
                                         command=self._start_hotkey_recording)
        self._record_btn.pack(side="left")

        ctk.CTkLabel(parent, text="提示词:", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(4, 2))
        self._profile_prompt_text = ctk.CTkTextbox(parent, height=180, font=ctk.CTkFont(size=10), wrap="word")
        self._profile_prompt_text.pack(fill="x", pady=(0, 6))

        self._select_profile(0)

    def _refresh_profile_list(self):
        for w in self._profile_list_frame.winfo_children():
            w.destroy()
        self._profile_buttons.clear()

        for i, p in enumerate(self._profiles):
            text = f"{p.name}  [{p.hotkey.to_string()}]"
            btn = ctk.CTkRadioButton(
                self._profile_list_frame, text=text,
                variable=self._profile_radio_var, value=i,
                font=ctk.CTkFont(size=11),
                command=lambda idx=i: self._select_profile(idx),
            )
            btn.pack(anchor="w", pady=1)

    def _select_profile(self, idx: int):
        if idx < 0 or idx >= len(self._profiles):
            return
        self._save_current_profile()
        self._selected_profile_idx = idx
        p = self._profiles[idx]
        self._profile_name_var.set(p.name)
        self._profile_hotkey_var.set(p.hotkey.to_string())
        self._profile_prompt_text.delete("1.0", "end")
        self._profile_prompt_text.insert("1.0", p.system_prompt)
        self._profile_radio_var.set(idx)

    def _save_current_profile(self):
        idx = self._selected_profile_idx
        if idx < 0 or idx >= len(self._profiles):
            return
        p = self._profiles[idx]
        p.name = self._profile_name_var.get().strip()
        prompt = self._profile_prompt_text.get("1.0", "end-1c").strip()
        p.system_prompt = prompt
        self._log.debug(f"设置: 保存当前 profile [{p.name}]")

    def _add_profile(self):
        self._save_current_profile()
        new_p = ProfileConfig(
            name=f"新 Profile {len(self._profiles)+1}",
            hotkey=HotkeyConfig(key="", alt=True),
            system_prompt="",
        )
        self._profiles.append(new_p)
        self._refresh_profile_list()
        self._select_profile(len(self._profiles) - 1)

    def _remove_profile(self):
        if len(self._profiles) <= 1:
            return
        idx = self._selected_profile_idx
        if idx < 0 or idx >= len(self._profiles):
            return
        del self._profiles[idx]
        self._refresh_profile_list()
        new_idx = min(idx, len(self._profiles) - 1)
        self._select_profile(new_idx)

    def _start_hotkey_recording(self):
        if self._hotkey_recording:
            return
        self._hotkey_recording = True
        self._record_btn.configure(text="等待按键...", state="disabled")
        self._profile_hotkey_var.set("请按下快捷键组合...")
        self._recorded_keys.clear()
        self._held_keys.clear()
        self._hotkey_listener = keyboard.Listener(
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self._hotkey_listener.start()

    def _on_hotkey_press(self, key):
        if not self._hotkey_recording: return
        self._held_keys.add(key)
        if key not in self._recorded_keys:
            self._recorded_keys.append(key)
        names = [_key_to_display(k) for k in self._recorded_keys]
        self._profile_hotkey_var.set(" + ".join(names))

    def _on_hotkey_release(self, key):
        if not self._hotkey_recording: return
        self._held_keys.discard(key)
        if len(self._held_keys) == 0 and len(self._recorded_keys) > 0:
            self._window.after(200, self._finalize_hotkey_capture)

    def _finalize_hotkey_capture(self):
        keys = self._recorded_keys
        non_modifiers = [k for k in keys if not _is_modifier_type(k)]
        modifiers = [k for k in keys if _is_modifier_type(k)]
        has_ctrl = any("ctrl" in _key_to_display(k).lower() for k in modifiers)
        has_shift = any("shift" in _key_to_display(k).lower() for k in modifiers)
        has_alt = any("alt" in _key_to_display(k).lower() for k in modifiers)

        if non_modifiers:
            trigger_key = _key_to_config_char(non_modifiers[-1])
        else:
            last_mod = keys[-1]
            trigger_key = _key_to_config_char(last_mod)
            if trigger_key == "ctrl": has_ctrl = False
            elif trigger_key == "shift": has_shift = False
            elif trigger_key == "alt": has_alt = False

        if not trigger_key:
            self._profile_hotkey_var.set("无效的按键, 请重试...")
            self._stop_hotkey_recording()
            return

        self._profiles[self._selected_profile_idx].hotkey = HotkeyConfig(
            key=trigger_key, ctrl=has_ctrl, shift=has_shift, alt=has_alt,
        )
        self._profile_hotkey_var.set(self._profiles[self._selected_profile_idx].hotkey.to_string())
        self._log.debug(f"设置: profile 快捷键录制完成 -> {self._profiles[self._selected_profile_idx].hotkey.to_string()}")
        self._stop_hotkey_recording()
        self._refresh_profile_list()

    def _stop_hotkey_recording(self):
        self._hotkey_recording = False
        if self._record_btn:
            self._record_btn.configure(text="录制", state="normal")
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        self._recorded_keys.clear()
        self._held_keys.clear()

    def _build_log_section(self, parent):
        self._section_label(parent, "调试日志")
        log_path = get_log_path() or "未初始化"
        ctk.CTkLabel(parent, text=f"日志文件: {log_path}", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 8))

    def _build_advanced_section(self, parent):
        title = ctk.CTkLabel(
            parent, text="高级设置",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(anchor="w", pady=(8, 12))

        self._section_label(parent, "粘贴兼容应用")
        self._section_hint(
            parent,
            "这些应用使用剪贴板粘贴文本，适合微信这类不兼容 Unicode 注入的输入框。每行一个进程名，留空表示禁用。",
        )
        self._clipboard_apps_text = ctk.CTkTextbox(
            parent, height=90, font=ctk.CTkFont(size=11), wrap="none",
        )
        self._clipboard_apps_text.pack(fill="x", pady=(0, 8))
        self._clipboard_apps_text.insert(
            "1.0",
            "\n".join(self._config.clipboard_app_names),
        )

        self._section_label(parent, "日志等级")
        self._section_hint(
            parent,
            "默认关闭日志以保护隐私。开启 Debug 会记录转写预览，仅排查问题时使用。",
        )
        self._log_level_var = ctk.StringVar(value=self._config.log_level)
        ctk.CTkOptionMenu(
            parent,
            values=["OFF", "ERROR", "WARNING", "INFO", "DEBUG"],
            variable=self._log_level_var,
            height=32,
            font=ctk.CTkFont(size=11),
        ).pack(fill="x", pady=(0, 4))

        log_path = get_log_path() or "日志已关闭"
        ctk.CTkLabel(
            parent,
            text=f"日志文件: {log_path}",
            text_color="gray",
            font=ctk.CTkFont(size=10),
        ).pack(anchor="w", pady=(0, 8))

    def _build_auto_start_section(self, parent):
        self._auto_start_var = ctk.BooleanVar(value=self._config.auto_start)
        ctk.CTkCheckBox(parent, text="开机自动启动", variable=self._auto_start_var,
                        font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 12))

    def _build_buttons(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(6, 12))
        ctk.CTkButton(row, text="取消", width=100, height=36, fg_color="transparent",
                      border_width=1, font=ctk.CTkFont(size=12),
                      command=self._cancel).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="保存", width=100, height=36, font=ctk.CTkFont(size=12),
                      command=self._save).pack(side="right")

    def _save(self):
        self._save_current_profile()

        self._config.api_key = self._api_key_var.get().strip()
        self._config.proxy = self._proxy_var.get().strip()
        self._config.base_url = self._base_url_var.get().strip()
        self._config.model = self._get_selected_model()

        level = self._thinking_level_var.get()
        self._config.thinking_level = level if level != "不设置" else ""

        budget_text = self._thinking_budget_var.get().strip()
        if budget_text == "":
            self._config.thinking_budget = -2
        else:
            try:
                self._config.thinking_budget = int(budget_text)
            except ValueError:
                self._config.thinking_budget = -2

        try: self._config.temperature = float(self._temperature_var.get())
        except ValueError: pass
        try: self._config.top_p = float(self._top_p_var.get())
        except ValueError: pass
        try: self._config.max_output_tokens = int(self._max_tokens_var.get())
        except ValueError: pass

        self._config.profiles = self._profiles
        self._config.auto_start = self._auto_start_var.get()
        self._config.clipboard_app_names = self._get_clipboard_app_names()
        self._config.log_level = self._log_level_var.get().strip().upper()

        self._log.debug(f"设置: 保存配置, {len(self._profiles)} profiles, model={self._config.model}")
        self._on_save(self._config)
        self._on_close()

    def _get_clipboard_app_names(self) -> list[str]:
        raw_text = self._clipboard_apps_text.get("1.0", "end-1c")
        names = []
        seen = set()
        for line in raw_text.replace(",", "\n").replace(";", "\n").splitlines():
            name = line.strip().lower()
            if not name:
                continue
            if "." not in name:
                name = f"{name}.exe"
            if name not in seen:
                names.append(name)
                seen.add(name)
        return names

    def _cancel(self):
        self._on_cancel()
        self._on_close()
