import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional


DEFAULT_CLIPBOARD_APP_NAMES = ["wechat.exe", "weixin.exe"]
DEFAULT_LOG_LEVEL = "OFF"


@dataclass
class HotkeyConfig:
    key: str = "x"
    ctrl: bool = False
    shift: bool = False
    alt: bool = True

    def to_string(self) -> str:
        parts = []
        if self.ctrl:
            parts.append("Ctrl")
        if self.shift:
            parts.append("Shift")
        if self.alt:
            parts.append("Alt")
        parts.append(self.key.upper())
        return "+".join(parts)

    @classmethod
    def from_string(cls, s: str) -> "HotkeyConfig":
        parts = [p.strip().lower() for p in s.split("+")]
        return cls(
            key=parts[-1],
            ctrl="ctrl" in parts,
            shift="shift" in parts,
            alt="alt" in parts,
        )


@dataclass
class ProfileConfig:
    name: str = ""
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    system_prompt: str = ""


_DEV_PROMPT = """\
<role>
你是一个顶级的软件开发领域语音转写助手。你精通各种编程语言、框架、数据库架构，并熟悉 \
程序员的日常沟通习惯。
</role>

<task>
你的任务是将用户的语音输入转写为清晰、准确的文字。你需要利用你的技术背景，精准识别语音 \
中的中英夹杂词汇和专业术语，并进行轻度的文本清洗。
</task>

<rules>
1. 去除语气词：删除"额"、"嗯"、"啊"、"那个"、"就是说"、"然后"等无意义的思考停顿词。
2. 术语精准化：根据上下文，正确拼写并规范化软件开发专业术语的大小写（例如：将"买色扣" \
转写为 MySQL，将"死不灵布特"转写为 Spring Boot，将"接森"转写为 JSON）。
3. 保持原意与结构：在清理废话和术语纠错后，尽可能保留用户原始的句子结构和表达习惯， \
不要过度润色，不要改变原意。
4. 标点符号：根据语音的停顿和语气，自动添加正确的中文标点符号。
</rules>

<examples>
<example 1>
用户语音输入内容：额，我刚才查了一下那个，嗯，买色扣的报错，好像是那个死不灵布特的配置没写对。
你的输出：我刚才查了一下 MySQL 的报错，好像是 Spring Boot 的配置没写对。
</example>
<example 2>
用户语音输入内容：那个，前端传过来的接森数据里，字段好像缺了一个，你查一下那个 API 文档。
你的输出：前端传过来的 JSON 数据里，字段好像缺了一个，你查一下 API 文档。
</example>
</examples>

<instruction>
请严格按照上述规则，处理接下来的音频输入。直接输出转写后的文本，不要包含任何解释性的话语。
</instruction>"""

_FORMAL_PROMPT = """\
<role>
你是一位资深的技术沟通专家兼高级项目经理。你擅长将口语化的、零散的技术交流，转化为 \
专业、严谨、逻辑清晰的正式书面表达。
</role>

<task>
你的任务是将用户的语音输入转写并重构成正式的书面文本，适用于发送工作邮件、编写 Jira \
需求或提交工作汇报。
</task>

<rules>
1. 彻底净化：完全去除所有语气词、口头禅、重复的半句话以及思考时的停顿。
2. 术语规范：精准识别并规范化所有技术术语（如 MySQL, Spring Boot, Redis, API, CI/CD 等）。
3. 结构重组与精炼：将口语化的长句拆分或重组为逻辑清晰的短句。消除冗余表述，提炼核心 \
事实和诉求。
4. 语气转换：将随意的口语语气转化为专业、客观、礼貌的职场书面语。
5. 忠于事实：无论如何重构，必须 100% 保留原始语音中的技术细节、数据、责任人等核心信息， \
绝不捏造。
</rules>

<examples>
<example 1>
用户语音输入内容：额，老李啊，那个昨天线上的那个买色扣数据库，嗯，好像有点卡，就是查询 \
特别慢。然后我看了下，应该是咱们那个死不灵布特项目里有个接口，额，那个搜扣没加索引， \
你今天抽空给优化一下吧。
你的输出：老李，你好。昨天线上 MySQL 数据库出现查询缓慢的问题。经排查，原因是 Spring \
Boot 项目中的一个接口缺少 SQL 索引。请你今天抽空进行优化。
</example>
<example 2>
用户语音输入内容：就是说，客户那边想要个新功能，嗯，需要在后台能看到每天的活跃用户数， \
然后最好能导出一个一个的那个一丢赛欧表格，这个事儿下周三之前得弄完上线。
你的输出：客户提出新需求：需要在后台查看每日活跃用户数，并支持导出 Excel 表格。此功能 \
需在下周三前完成并上线。
</example>
</examples>

<instruction>
请严格按照上述规则，处理接下来的音频输入。直接输出重构后的正式文本，不要包含任何解释性 \
的话语。
</instruction>"""

_DEFAULT_PROFILES = [
    ProfileConfig(
        name="开发者语音输入",
        hotkey=HotkeyConfig(key="x", alt=True),
        system_prompt=_DEV_PROMPT,
    ),
    ProfileConfig(
        name="正式书面沟通",
        hotkey=HotkeyConfig(key="c", alt=True),
        system_prompt=_FORMAL_PROMPT,
    ),
]


@dataclass
class AppConfig:
    api_key: str = ""
    proxy: str = ""
    base_url: str = ""
    model: str = "gemini-3.5-flash"
    system_prompt: str = ""
    temperature: float = 0.1
    top_p: float = 0.95
    max_output_tokens: int = 4096
    thinking_level: str = ""
    thinking_budget: int = -2
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    profiles: list = field(default_factory=list)
    auto_start: bool = False
    first_run: bool = True
    clipboard_app_names: list[str] = field(
        default_factory=lambda: DEFAULT_CLIPBOARD_APP_NAMES.copy()
    )
    log_level: str = DEFAULT_LOG_LEVEL

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hotkey"] = self.hotkey.to_string()
        serialized_profiles = []
        for p in self.profiles:
            if isinstance(p, ProfileConfig):
                serialized_profiles.append({
                    "name": p.name,
                    "hotkey": p.hotkey.to_string(),
                    "system_prompt": p.system_prompt,
                })
            elif isinstance(p, dict):
                serialized_profiles.append(p)
        d["profiles"] = serialized_profiles
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AppConfig":
        data = dict(d)
        hotkey_raw = data.pop("hotkey", "Alt+X")
        if isinstance(hotkey_raw, dict):
            hotkey = HotkeyConfig(**hotkey_raw)
        else:
            hotkey = HotkeyConfig.from_string(hotkey_raw)

        profiles_raw = data.pop("profiles", None)
        profiles = []
        if profiles_raw is None:
            profiles = [
                ProfileConfig(
                    name=p.name if hasattr(p, 'name') else p.get("name", ""),
                    hotkey=HotkeyConfig() if isinstance(p, ProfileConfig) else HotkeyConfig.from_string(p["hotkey"]),
                    system_prompt=p.system_prompt if isinstance(p, ProfileConfig) else p["system_prompt"],
                )
                for p in _DEFAULT_PROFILES
            ]
        else:
            for p in profiles_raw:
                if isinstance(p, dict):
                    profiles.append(ProfileConfig(
                        name=p.get("name", ""),
                        hotkey=HotkeyConfig.from_string(p.get("hotkey", "Alt+X")),
                        system_prompt=p.get("system_prompt", ""),
                    ))
        clipboard_app_names = data.pop(
            "clipboard_app_names",
            DEFAULT_CLIPBOARD_APP_NAMES.copy(),
        )
        if not isinstance(clipboard_app_names, list):
            clipboard_app_names = DEFAULT_CLIPBOARD_APP_NAMES.copy()
        clipboard_app_names = [
            str(name).strip().lower()
            for name in clipboard_app_names
            if str(name).strip()
        ]

        log_level = str(data.pop("log_level", DEFAULT_LOG_LEVEL)).upper()
        if log_level not in {"OFF", "ERROR", "WARNING", "INFO", "DEBUG"}:
            log_level = DEFAULT_LOG_LEVEL

        return cls(
            hotkey=hotkey,
            profiles=profiles,
            clipboard_app_names=clipboard_app_names,
            log_level=log_level,
            **data,
        )


class ConfigManager:
    def __init__(self):
        self._config_dir = os.path.join(os.getenv("APPDATA", ""), "voice_input")
        self._config_path = os.path.join(self._config_dir, "config.json")
        self._config: AppConfig = self._load()

    def _load(self) -> AppConfig:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = AppConfig()
            cfg.profiles = [
                ProfileConfig(
                    name=p.name,
                    hotkey=p.hotkey,
                    system_prompt=p.system_prompt,
                )
                for p in _DEFAULT_PROFILES
            ]
            return cfg

    def save(self):
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)

    @property
    def config(self) -> AppConfig:
        return self._config

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self.save()

    def get_exe_path(self) -> Optional[str]:
        if getattr(sys, "frozen", False):
            return sys.executable
        return None
