# Voice Input - Gemini 语音输入法

基于 Google Gemini 多模态大模型的智能语音输入法工具。按下快捷键说话，松开后自动转写并输入到光标位置。

## 特性

- **多 Profile 支持**：内置"开发者语音输入"(Alt+X) 和"正式书面沟通"(Alt+C) 两套提示词，可自由添加/删除
- **绕过输入法冲突**：使用 Windows `SendInput` + `KEYEVENTF_UNICODE` 直送 Unicode 字符，不触发 IME
- **思考控制**：支持 Gemini 3.x 的 `thinkingLevel` 和 Gemini 2.x 的 `thinkingBudget`
- **自定义 Base URL**：支持 API 网关代理
- **开机自启**：写入 Windows 注册表
- **详细日志**：DEBUG 级别日志写入 `%APPDATA%/voice_input/voice_input.log`

## 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/voice-input.git
cd voice-input

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 使用

1. 首次运行后，右键系统托盘图标 → Settings
2. 填入 [Google AI Studio](https://aistudio.google.com/apikey) 获取的免费 API Key
3. 按下 `Alt+X`（开发者模式）或 `Alt+C`（正式书面模式）开始录音
4. 松开后自动识别并输入到光标处

## 设置说明

| 配置项 | 说明 |
|--------|------|
| API 密钥 | Google Gemini API Key |
| 模型选择 | gemini-3.5-flash 等，支持自定义模型名 |
| Temperature / Top P | 控制生成随机性 |
| 思考等级 | Gemini 3.x: minimal / low / medium / high |
| 思考预算 | Gemini 2.x: -1=动态, 0=关闭, >0=Token 预算 |
| 代理设置 | HTTP/SOCKS5 代理 |
| 自定义 Base URL | API 网关代理地址 |
| Profile 管理 | 添加快捷键+提示词组合 |

## Profile 示例

**Alt+X — 开发者语音输入**：保留口语结构，精准识别技术术语（MySQL, Spring Boot, JSON 等），去除语气词。

**Alt+C — 正式书面沟通**：将口语转化为专业书面语，适合邮件、Jira 需求、工作汇报。

## 打包

```bash
pip install pyinstaller
pyinstaller build.spec
# 输出: dist/VoiceInput.exe
```

## 技术栈

| 组件 | 库 |
|------|-----|
| GUI | customtkinter |
| 系统托盘 | pystray + Pillow |
| 音频录制 | sounddevice + numpy |
| 热键监听 | pynput |
| 文本输入 | Win32 SendInput (ctypes) |
| API | google-genai |
| 日志 | logging |

## 许可

MIT
