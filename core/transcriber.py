import os
from google import genai
from google.genai import types
from core.config_manager import AppConfig
from core.logger import get_logger

SYSTEM_INSTRUCTION = """\
<role>
你是一个专为软件开发者和 IT 工程师打造的"智能语音输入法引擎"。你的核心任务是接收用户的 \
语音输入，并结合上下文语境，将其转化为极其精准、符合专业表达习惯的文本。
</role>

<context>
用户主要在编写代码、撰写技术文档、或进行技术交流（如 Code Review 讨论）时使用此输入法。 \
语音中会高频夹杂大量计算机科学、软件工程、系统架构以及各编程语言的专业术语（例如：MySQL, \
Spring Boot, Kubernetes, CI/CD, JSON, RESTful API 等）。
</context>

<instructions>
请严格遵循以下规则进行转写：
1. 【术语精准还原】：利用你的上下文推理能力，准确捕捉中英夹杂的专业术语，并使用行业标准的 \
官方拼写（例如：遇到类似"死不灵布特"的发音，结合语境转写为"Spring Boot"；遇到"买色扣" \
转写为"MySQL"）。
2. 【智能语境纠错】：修复同音词或近音词错误。遇到多义词发音时，根据前后文的技术逻辑，选择 \
最合理的词汇。
3. 【专业排版规范】：根据语音停顿自动添加准确的标点符号。在中英文混排时，中英文之间自动 \
补充空格（如"启动 Spring Boot 服务"），保持文本优雅。
4. 【纯净输出模式】：绝对严格的约束！由于你是输入法引擎，你的输出将被直接发送到用户的屏幕 \
光标处。因此，**只允许输出最终转写好的纯文本，绝对禁止输出任何寒暄、确认语、解释或类似 \
"好的，为您转写如下："的废话。**
</instructions>"""

USER_PROMPT = "Transcribe this audio."


class GeminiTranscriber:
    def __init__(self, config: AppConfig):
        self._config = config
        self._client: genai.Client | None = None
        self._log = get_logger()
        self._build_client()

    def _build_client(self):
        if not self._config.api_key:
            self._log.debug("Transcriber: API Key 为空，跳过客户端创建")
            self._client = None
            return

        if self._config.proxy:
            os.environ["HTTP_PROXY"] = self._config.proxy
            os.environ["HTTPS_PROXY"] = self._config.proxy
            self._log.debug(f"设置代理: {self._config.proxy}")
        else:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)

        http_options = None
        if self._config.base_url:
            self._log.debug(f"设置自定义 base_url: {self._config.base_url}")
            http_options = types.HttpOptions(base_url=self._config.base_url)

        self._client = genai.Client(
            api_key=self._config.api_key,
            http_options=http_options,
        )
        self._log.debug(f"Transcriber: 客户端已创建, model={self._config.model}")

    def update_config(self, config: AppConfig):
        self._log.debug(
            f"Transcriber: 配置更新 "
            f"model={config.model} "
            f"temperature={config.temperature} "
            f"top_p={config.top_p} "
            f"max_output_tokens={config.max_output_tokens}"
        )
        self._config = config
        self._build_client()

    def transcribe(self, audio_buffer, system_prompt: str | None = None) -> str:
        if not self._client or not self._config.api_key:
            raise ValueError("API Key not configured")

        audio_bytes = audio_buffer.read()
        audio_size_kb = len(audio_bytes) / 1024
        self._log.debug(
            f"Transcriber: 开始转写, "
            f"audio_size={audio_size_kb:.1f}KB, "
            f"model={self._config.model}"
        )

        if len(audio_bytes) == 0:
            self._log.warning("Transcriber: 音频数据为空")
            return ""

        prompt = system_prompt or self._config.system_prompt or SYSTEM_INSTRUCTION
        temperature = self._config.temperature
        top_p = self._config.top_p
        max_tokens = self._config.max_output_tokens

        self._log.debug(
            f"Transcriber: 调用 API "
            f"temperature={temperature} "
            f"top_p={top_p} "
            f"max_output_tokens={max_tokens}"
        )

        thinking_config = None
        if self._config.thinking_level:
            thinking_config = types.ThinkingConfig(
                thinking_level=self._config.thinking_level
            )
            self._log.debug(f"Transcriber: thinking_level={self._config.thinking_level}")
        elif self._config.thinking_budget >= 0:
            thinking_config = types.ThinkingConfig(
                thinking_budget=self._config.thinking_budget
            )
            self._log.debug(f"Transcriber: thinking_budget={self._config.thinking_budget}")
        elif self._config.thinking_budget == -1:
            thinking_config = types.ThinkingConfig(thinking_budget=-1)
            self._log.debug("Transcriber: thinking_budget=动态")

        generate_config = types.GenerateContentConfig(
            system_instruction=prompt,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_tokens,
        )
        if thinking_config is not None:
            generate_config.thinking_config = thinking_config

        response = self._client.models.generate_content(
            model=self._config.model,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                USER_PROMPT,
            ],
            config=generate_config,
        )

        text = response.text
        if text:
            text = text.strip()
            self._log.debug(
                f"Transcriber: 转写完成, "
                f"text_length={len(text)}, "
                f"preview={text[:80]}..."
            )
        else:
            self._log.warning("Transcriber: API 返回空文本")

        return text or ""
