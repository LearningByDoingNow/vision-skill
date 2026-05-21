<p align="center">
  <h1 align="center">🔭 vision</h1>
  <p align="center"><strong>多厂商多模态图片/视频描述 · 零配置 OCR 兜底 · 纯文本模型视觉桥梁</strong></p>
</p>

<p align="center">
  <b>中文</b> | <a href="README_EN.md">English</a>
</p>

---

## 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [依赖安装](#依赖安装)
- [配置 API Key](#配置-api-key)
- [使用方式](#使用方式)
- [架构设计](#架构设计)
- [OCR 兜底链](#ocr-兜底链)
- [视频处理流程](#视频处理流程)
- [扩展新厂商](#扩展新厂商)
- [模型优先级](#模型优先级)
- [常见问题](#常见问题)

---

## 概述

`vision` 是一个 Claude Code 技能（skill），让**纯文本模型**也能理解图片和视频的内容。它连接多个厂商的视觉大模型，自动检测可用 API，在完全没有 API key 时降级到 OCR 文字提取。

> **适用场景**：本 skill 为 **DeepSeek V4 Pro 等纯文本主模型**设计。如果你使用的主模型本身就具备多模态视觉能力（如 Claude Opus、GPT-4o 等），它可以直接查看图片，此时 vision skill 会**冗余执行**——主模型能看到原图，skill 还会额外调用一次视觉 API 生成文字描述，浪费一次调用和延迟。建议在纯文本模型下启用，在多模态模型下移除或禁用该 skill。

### 核心能力

| 能力 | 说明 |
|------|------|
| 📷 图片描述 | 结构化 7 段式描述（场景/背景/主体/文字/色彩/细节/印象） |
| 🎬 视频描述 | 关键帧提取 → 逐帧描述 → 汇总总结 |
| 🖼️ TUI 粘贴/拖入 | 聊天框直接粘贴图片，**无扩展名的临时文件通过文件头魔数自动识别** |
| 📦 多文件批处理 | 一次传入多个图片/视频/URL，逐个描述，带序号分隔 |
| 🔀 多厂商自动切换 | 按 `ZHIPU` → `OpenAI` → `Anthropic` → `Google` 顺序自动检测 |
| 🔤 OCR 兜底 | 无 API key 时自动降级：easyocr → pytesseract → 基础元信息 |
| 🌐 远程 URL | 直接传入图片/视频 URL，无需下载 |
| 📥 标准输入 | 支持管道输入 `cat img.png \| ... -` |
| 🎯 自定义提示词 | `--prompt` 指定关注重点、输出语言等 |

### 支持的厂商与默认模型

| 厂商 | 环境变量 | 默认模型 |
|------|----------|----------|
| 智谱 GLM | `ZHIPU_API_KEY` | `glm-4.6v` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Google | `GOOGLE_API_KEY` | `gemini-2.5-flash` |

---

## 配置概览

开始之前，了解你需要做的三件事，每件事都有多种方式可选：

| 事项 | 选项 |
|------|------|
| **安装位置** | ① 项目级（`.claude/skills/vision`） ② 全局（`~/.claude/skills/vision`） |
| **依赖安装** | ① `bash install.sh`（自动检测 pip/uv） ② 手动 `pip install -r auto_config/requirements.txt` ③ 按需只装一个厂商的 SDK |
| **API key** | ① 环境变量 `export`（临时） ② 项目级 `settings.local.json`（推荐） ③ 全局 `~/.claude/settings.json` |

> **`install.sh` 不是必须的**——它只是一个便利脚本。如果你熟悉 Python，直接 `pip install` 即可。Windows 用户请优先手动安装。

---

## 快速开始

### macOS / Linux

```bash
# 1. 克隆到项目或全局
git clone https://github.com/<user>/vision-skill.git .claude/skills/vision   # 项目级
git clone https://github.com/<user>/vision-skill.git ~/.claude/skills/vision  # 全局

# 2. 安装依赖
pip install -r auto_config/requirements.txt
# 或 bash install.sh（自动检测 pip/uv）

# 3. 配置任意一个 API key
export ZHIPU_API_KEY="your-key-here"

# 4. 在 Claude Code 中使用
#   - 直接拖入图片/视频文件
#   - 输入 /vision
#   - 粘贴图片/视频 URL
```

### Windows

`install.sh` 依赖 bash 环境，Windows 用户直接手动操作即可：

```powershell
# 1. 克隆到项目或全局
git clone https://github.com/<user>/vision-skill.git .claude/skills/vision

# 2. 安装 Python 依赖（PowerShell / CMD 均可）
pip install -r auto_config/requirements.txt

# 3. 配置 API key（三选一，见下方"配置 API Key"章节）
set ZHIPU_API_KEY=your-key-here          # CMD 临时
$env:ZHIPU_API_KEY = "your-key-here"     # PowerShell 临时
# 或写入 settings.json（推荐，持久生效）
```

---

## 安装

### 一键安装依赖（macOS / Linux）

```bash
bash install.sh
```

脚本会自动检测 pip/uv，安装 `auto_config/requirements.txt` 中的全部依赖。

### Windows / 手动安装

```bash
pip install -r auto_config/requirements.txt
```

### 按需安装

如果只用某一个厂商，可以只装对应的 SDK：

```bash
# 智谱
pip install zai

# OpenAI
pip install openai

# Anthropic
pip install anthropic

# Google
pip install google-genai
```

### 系统依赖（可选）

| 工具 | 用途 | macOS | Linux | Windows |
|------|------|-------|-------|---------|
| `ffmpeg` | 本地视频关键帧提取 | `brew install ffmpeg` | `apt install ffmpeg` | `winget install ffmpeg` |
| `tesseract` | pytesseract OCR 引擎 | `brew install tesseract` | `apt install tesseract-ocr` | `winget install tesseract-ocr` |

> `easyocr` 不依赖系统工具，离线可用，首次运行自动下载模型（~200MB）。

---

## 配置 API Key

三种配置方式，任选其一即可：

### 方式一：环境变量（临时生效）

```bash
export ZHIPU_API_KEY="your-key"     # 智谱 GLM
export OPENAI_API_KEY="your-key"    # OpenAI GPT-4o
export ANTHROPIC_API_KEY="your-key" # Anthropic Claude
export GOOGLE_API_KEY="your-key"    # Google Gemini
```

终端关闭后失效，适合临时使用或测试。

### 方式二：项目级 settings.local.json（推荐）

写入项目 `.claude/settings.local.json` 的 `env` 字段（已在 `.gitignore`，不会提交）：

```json
{
  "env": {
    "ZHIPU_API_KEY": "your-key",
    "VISION_MODEL": "glm-4.6v"
  }
}
```

仅当前项目生效，不会泄露到其他项目或 git 仓库。

### 方式三：全局 settings.json

写入 `~/.claude/settings.json` 的 `env` 字段，格式同方式二。所有项目共享，适合个人常用配置。

### 可选配置

```bash
export VISION_MODEL="gpt-4o-mini"   # 覆盖厂商默认模型
export VISION_TIMEOUT="90"          # API 超时上限(秒)，默认 90s
```
> `VISION_TIMEOUT` 是**保护上限**而非固定延迟——API 在 5s 内返回则 5s 就继续执行，不会空等到超时。

---

## 使用方式

### 作为 Claude Code Skill（自动触发）

- **TUI 粘贴/拖入图片**：直接在聊天框粘贴或拖入图片，skill 自动触发，图片临时文件即使无扩展名也能通过文件头魔数正确识别
- **输入 `/vision`** + 文件路径/URL
- **附带图片/视频文件**发起对话

Skill 会：
1. 检测当前配置了哪些 API key
2. 自动选择第一个可用的厂商
3. 调用视觉模型生成描述
4. 将描述返回给 Claude 作为视觉理解依据

### 命令行直接调用

```bash
# 图片描述（含 TUI 临时文件）
python3 scripts/vision_describe.py photo.jpg

# 多个文件/URL 依次描述
python3 scripts/vision_describe.py \
  img1.jpg img2.png "https://example.com/photo.jpg"

# 指定厂商和模型
python3 scripts/vision_describe.py photo.jpg \
  --provider openai --model gpt-4o-mini

# 自定义描述要求
python3 scripts/vision_describe.py screenshot.png \
  --prompt "重点关注代码部分，逐行抄录"

# 视频描述（更多关键帧）
python3 scripts/vision_describe.py video.mp4 \
  --max-frames 10

# 管道输入（stdin）
cat screenshot.png | .venv/bin/python \
  .claude/skills/vision/scripts/vision_describe.py -

# 远程 URL
python3 scripts/vision_describe.py \
  "https://example.com/photo.jpg"

# 查看厂商状态
python3 scripts/vision_describe.py --list-providers
```

---

## 架构设计

```
vision_describe.py
│
├─ describe_media()          ← CLI 入口，多文件循环 + stdin 支持
│   ├─ describe_image()      ← 图片描述（含 TUI 临时文件）
│   └─ describe_video()      ← 视频描述
│
├─ Media Detection           ← 文件类型识别（无扩展名也支持）
│   ├─ _detect_type_from_content() ← 文件头魔数检测（主方案）
│   └─ _guess_mime()              ← 扩展名兜底
│
├─ Provider Registry         ← 厂商注册表（可扩展）
│   ├─ ZhipuProvider         ← zai SDK
│   ├─ OpenAIProvider        ← openai SDK
│   ├─ AnthropicProvider     ← anthropic SDK
│   └─ GoogleProvider        ← google-genai SDK
│
├─ OCR Fallback Chain        ← 无 API key 时的兜底方案
│   ├─ _ocr_easyocr()        ← easyocr（离线，模型缓存复用）
│   ├─ _ocr_tesseract()      ← pytesseract（需系统 tesseract）
│   └─ _image_basic_info()   ← Pillow 基础元信息（最终兜底）
│
└─ Video Pipeline            ← 视频处理流水线
    └─ _extract_keyframes()  ← ffprobe 探测时长 → ffmpeg 均分抽帧
```

### 核心抽象：`BaseProvider`

所有厂商适配器继承自 `BaseProvider`，只需实现两个方法：

```python
class BaseProvider(ABC):
    @abstractmethod
    def describe_image(self, image_url: str, prompt: str, model: str) -> str: ...

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        """纯文本调用（视频帧汇总用），默认复用 describe_image。"""
        return self.describe_image(text, prompt, model)
```

- `describe_image` — 接收图片 URL（可以是 `data:` URL 或 `https://` URL）和提示词，返回文字描述
- `describe_text` — 纯文本调用，用于视频帧汇总；默认复用图片方法，子类可重写以使用更便宜的纯文本模型

---

## OCR 兜底链

当所有厂商的 API key 都未配置时，自动降级为 OCR 模式：

```
图片输入
  │
  ├─ easyocr ────────────── ✅ 成功 → 返回文字 + 置信度
  │  (离线，中英文，首次自动下载模型)
  │
  ├─ pytesseract ────────── ✅ 成功 → 返回文字
  │  (需 brew install tesseract)
  │
  └─ Pillow 基础信息 ────── 🆘 最终兜底
     (格式 / 尺寸 / 模式 / 文件大小 / EXIF)
```

OCR 结果会附带醒目的警告，告知用户当前仅提取了文字，无法理解场景、物体、色彩等视觉信息，并给出 API key 配置指引。

---

## 视频处理流程

### 本地视频

```
视频文件
  │
  ├─ ffprobe 探测时长
  │   ├─ 成功 → 根据时长均分抽帧（例如 60s 视频，6 帧 = 每 10s 一帧）
  │   └─ 失败 → 回退到均匀间隔抽帧
  │
  ├─ ffmpeg 提取关键帧（jpg）
  │
  ├─ 逐帧调用视觉模型描述
  │
  └─ 汇总所有帧描述 → 调用 describe_text 生成连贯总结
```

### 远程视频 URL

直接传递给视觉模型（部分厂商如 Gemini 原生支持视频 URL 处理）。

---

## 扩展新厂商

厂商系统通过 **注册表模式** 设计，添加新厂商只需两步。

### 步骤一：实现 Provider 子类

```python
class MyProvider(BaseProvider):
    """自定义厂商适配器示例。"""

    def __init__(self, api_key: str):
        # 初始化你的 SDK 客户端
        from my_sdk import Client
        self._client = Client(api_key=api_key, timeout=120)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        """实现图片描述：构造请求 → 调用 API → 返回文字。"""
        content = []
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        content.append({"type": "text", "text": prompt})

        resp = self._client.chat.create(
            model=model,
            messages=[{"role": "user", "content": content}],
        )
        return resp.choices[0].message.content

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        """（可选）纯文本调用，不涉及图片。"""
        resp = self._client.chat.create(
            model=model,
            messages=[{"role": "user", "content": prompt + "\n\n" + text}],
        )
        return resp.choices[0].message.content
```

### 步骤二：注册到厂商表

在 `vision_describe.py` 顶部的 `PROVIDER_REGISTRY` 中添加一行：

```python
PROVIDER_REGISTRY: list[tuple[ProviderInfo, type[BaseProvider]]] = [
    (ProviderInfo("zhipu",    "ZHIPU_API_KEY",    "glm-4.6v",         "智谱 GLM"),        ZhipuProvider),
    (ProviderInfo("openai",   "OPENAI_API_KEY",    "gpt-4o",           "OpenAI GPT-4o"),    OpenAIProvider),
    (ProviderInfo("anthropic","ANTHROPIC_API_KEY", "claude-sonnet-4-6","Anthropic Claude"), AnthropicProvider),
    (ProviderInfo("google",   "GOOGLE_API_KEY",    "gemini-2.5-flash", "Google Gemini"),    GoogleProvider),
    # ↓ 新增厂商
    (ProviderInfo("myvendor", "MY_API_KEY",        "my-model-v1",      "My Vendor"),        MyProvider),
]
```

**`ProviderInfo` 字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 厂商短名，用于 `--provider` 参数 |
| `env_var` | `str` | 读取此环境变量获取 API key |
| `default_model` | `str` | 厂商默认视觉模型 |
| `label` | `str` | 中文显示名，用于 `--list-providers` 和错误提示 |

注册完成后：

- `--list-providers` 自动展示新厂商状态
- `--provider myvendor` 强制使用新厂商
- 环境变量 `MY_API_KEY` 被检测后自动选用
- 无需修改任何其他代码

### Provider 实现要点

在你的 `describe_image` 方法中，`image_url` 参数可能是：

| 类型 | 格式 | 场景 |
|------|------|------|
| `data:` URL | `data:image/png;base64,...` | 本地文件 |
| `https://` URL | `https://example.com/photo.jpg` | 远程文件 |

你需要根据 SDK 的要求将图片传给 API：

- **接受 URL 的 SDK**（如 zai、openai）：直接传入 URL
- **接受 base64 的 SDK**（如 anthropic）：解析 `data:` URL 或下载远程 URL 后 base64 编码
- **接受 PIL Image 的 SDK**（如 google-genai）：加载为 PIL Image 对象

---

## 模型优先级

最终使用的模型由以下三层决定（从高到低）：

```
1. --model 命令行参数          （最高优先级，单次调用）
2. VISION_MODEL 环境变量       （会话级别覆盖）
3. 厂商默认模型                 （ProviderInfo.default_model）
```

示例：

```bash
# 使用 Zhipu 但覆盖模型为 glm-5-turbo
export ZHIPU_API_KEY="..."
.venv/bin/python vision_describe.py photo.jpg --model glm-5-turbo

# 全局默认使用 gpt-4o-mini（而非 gpt-4o）
export OPENAI_API_KEY="..."
export VISION_MODEL="gpt-4o-mini"
.venv/bin/python vision_describe.py photo.jpg
```

---

## 常见问题

### 没有任何 API key 能用吗？

图片可以，视频不行。无 API key 时图片自动进入 OCR 兜底模式，提取文字内容。但 OCR 无法理解场景、物体、人物、色彩等视觉信息。

### 为什么 OCR 返回的是英文或乱码？

easyocr 默认支持中英文，乱码通常是因为图片中的文字方向特殊或字体罕见。可以尝试安装 `tesseract` 作为备用 OCR 引擎。

### 视频文件报错 "未找到 ffprobe"

安装 ffmpeg：`brew install ffmpeg`。ffprobe 随 ffmpeg 一起安装。

### 远程 URL 图片 OCR 失败

OCR 需要下载到本地，远程 URL 无法直接 OCR。请下载到本地后重试，或配置任一 API key。

### 如何指定输出语言？

通过 `--prompt` 参数：

```bash
.venv/bin/python vision_describe.py photo.jpg --prompt "请用英文描述"
```

### 多个 API key 同时配置了，用哪个？

按注册表顺序自动选择第一个可用的：智谱 → OpenAI → Anthropic → Google。可通过 `--provider` 强制指定。

### Google Gemini 报超时

Google 的视觉模型处理大图或视频较慢，已设置 120s 超时。如果仍超时，可以尝试使用更小的图片或换用其他厂商。

### 主模型本身是多模态的，和 vision skill 会冲突吗？

不会报错，但会**冗余浪费**。多模态主模型（Claude Opus、GPT-4o 等）可以直接看图，此时 vision skill 仍会触发并额外调用一次视觉 API，生成一段文字描述——主模型最终会看到两份信息（原图 + 文字描述），造成一次无效的 API 调用和延迟。**建议仅在纯文本主模型（DeepSeek V4 Pro 等）下使用 vision skill。**
