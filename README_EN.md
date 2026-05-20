<p align="center">
  <h1 align="center">🔭 vision</h1>
  <p align="center"><strong>Multi-Provider Multimodal Image & Video Description · Zero-Config OCR Fallback · Visual Bridge for Text-Only LLMs</strong></p>
</p>

<p align="center">
  <a href="README.md">中文</a> | <b>English</b>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Dependencies](#dependencies)
- [API Key Configuration](#api-key-configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [OCR Fallback Chain](#ocr-fallback-chain)
- [Video Pipeline](#video-pipeline)
- [Adding New Providers](#adding-new-providers)
- [Model Priority](#model-priority)
- [FAQ](#faq)

---

## Overview

`vision` is a Claude Code skill that enables **text-only LLMs** to understand images and videos. It bridges multiple vision model providers, auto-detects available API keys, and gracefully falls back to OCR text extraction when no API key is configured.

> **Target Audience**: This skill is designed for **text-only main models like DeepSeek V4 Pro**. If your main model already has native multimodal vision (e.g., Claude Opus, GPT-4o), it can see images directly — the vision skill will execute redundantly, wasting an extra vision API call and adding latency. Use this skill with text-only models; disable it with multimodal ones.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| 📷 Image Description | Structured 7-section output (overview / background / subjects / text / color / details / impression) |
| 🎬 Video Description | Keyframe extraction → per-frame description → summary |
| 🖼️ TUI Paste/Drag | Paste images directly in chat; **temp files without extensions identified via magic bytes** |
| 📦 Batch Processing | Pass multiple images/videos/URLs at once, described sequentially with separators |
| 🔀 Multi-Provider Auto-Detect | Auto-selects first available provider: ZHIPU → OpenAI → Anthropic → Google |
| 🔤 OCR Fallback | No API key → auto-degrade: easyocr → pytesseract → basic metadata |
| 🌐 Remote URLs | Pass image/video URLs directly, no download needed |
| 📥 Stdin Input | Pipe support: `cat img.png \| ... -` |
| 🎯 Custom Prompts | `--prompt` to focus on specifics, change output language, etc. |

### Supported Providers & Default Models

| Provider | Env Variable | Default Model |
|----------|-------------|---------------|
| Zhipu GLM | `ZHIPU_API_KEY` | `glm-4.6v` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Google | `GOOGLE_API_KEY` | `gemini-2.5-flash` |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r .claude/skills/vision/auto_config/requirements.txt

# 2. Configure at least one API key
export ZHIPU_API_KEY="your-key-here"

# 3. Use in Claude Code
#   - Drag/drop or paste an image in chat
#   - Type /vision
#   - Paste an image/video URL
```

---

## Dependencies

### One-Line Install

```bash
pip install -r .claude/skills/vision/auto_config/requirements.txt
```

### Per-Provider Install

If you only use a single provider, install only that SDK:

```bash
# Zhipu
pip install zai

# OpenAI
pip install openai

# Anthropic
pip install anthropic

# Google
pip install google-genai
```

### System Dependencies (Optional)

| Tool | Purpose | Install |
|------|---------|---------|
| `ffmpeg` | Local video keyframe extraction | `brew install ffmpeg` |
| `tesseract` | pytesseract OCR engine | `brew install tesseract` |

> `easyocr` requires no system tools, works offline, and auto-downloads models (~200MB) on first run.

---

## API Key Configuration

Three configuration methods (highest priority first):

### Method 1: Environment Variables (Recommended)

```bash
export ZHIPU_API_KEY="your-key"     # Zhipu GLM
export OPENAI_API_KEY="your-key"    # OpenAI GPT-4o
export ANTHROPIC_API_KEY="your-key" # Anthropic Claude
export GOOGLE_API_KEY="your-key"    # Google Gemini
```

### Method 2: settings.local.json

Add to `.claude/settings.local.json` under the `env` field (this file is gitignored):

```json
{
  "env": {
    "ZHIPU_API_KEY": "your-key",
    "VISION_MODEL": "glm-4.6v"
  }
}
```

### Method 3: Custom Model & Timeout (Optional)

```bash
export VISION_MODEL="gpt-4o-mini"   # Override provider default model
export VISION_TIMEOUT="90"          # API timeout ceiling (seconds), default 90s
```
> `VISION_TIMEOUT` is a **safety ceiling**, not a fixed delay — if the API responds in 5s, execution continues immediately.

---

## Usage

### As a Claude Code Skill (Auto-Trigger)

- **Paste/drag images in TUI**: paste images directly in chat; the skill auto-triggers. Temp files without extensions are identified via content magic bytes.
- **Type `/vision`** + file path / URL
- **Attach image/video files** to your message

The skill will:
1. Detect which API keys are configured
2. Auto-select the first available provider
3. Call the vision model to generate a text description
4. Inject the description into your conversation for the main model

### CLI Direct Invocation

```bash
# Image description (including TUI temp files)
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py photo.jpg

# Multiple files/URLs
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py \
  img1.jpg img2.png "https://example.com/photo.jpg"

# Specify provider and model
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py photo.jpg \
  --provider openai --model gpt-4o-mini

# Custom description prompt
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py screenshot.png \
  --prompt "Focus on code content, transcribe line by line"

# Video description (more keyframes)
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py video.mp4 \
  --max-frames 10

# Stdin pipe input
cat screenshot.png | .venv/bin/python \
  .claude/skills/vision/scripts/vision_describe.py -

# Remote URL
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py \
  "https://example.com/photo.jpg"

# List provider status
.venv/bin/python .claude/skills/vision/scripts/vision_describe.py --list-providers
```

---

## Architecture

```
vision_describe.py
│
├─ describe_media()          ← CLI entry, multi-file loop + stdin support
│   ├─ describe_image()      ← Image description (including TUI temp files)
│   └─ describe_video()      ← Video description
│
├─ Media Detection           ← File type detection (extensionless supported)
│   ├─ _detect_type_from_content() ← Magic-byte detection (primary)
│   └─ _guess_mime()              ← Extension-based fallback
│
├─ Provider Registry         ← Pluggable provider registry
│   ├─ ZhipuProvider         ← zai SDK
│   ├─ OpenAIProvider        ← openai SDK
│   ├─ AnthropicProvider     ← anthropic SDK
│   └─ GoogleProvider        ← google-genai SDK
│
├─ OCR Fallback Chain        ← No-API-key fallback
│   ├─ _ocr_easyocr()        ← easyocr (offline, cached model)
│   ├─ _ocr_tesseract()      ← pytesseract (requires system tesseract)
│   └─ _image_basic_info()   ← Pillow metadata (last resort)
│
└─ Video Pipeline            ← Video processing
    └─ _extract_keyframes()  ← ffprobe duration → ffmpeg uniform sampling
```

### Core Abstraction: `BaseProvider`

All provider adapters inherit from `BaseProvider` and implement two methods:

```python
class BaseProvider(ABC):
    @abstractmethod
    def describe_image(self, image_url: str, prompt: str, model: str) -> str: ...

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        """Text-only call (for video frame summarization). Defaults to describe_image."""
        return self.describe_image(text, prompt, model)
```

- `describe_image` — accepts an image URL (`data:` URL or `https://` URL) and prompt, returns text description
- `describe_text` — text-only call for video frame summarization; defaults to reusing image method; subclasses may override to use cheaper text models

---

## OCR Fallback Chain

When no provider API key is configured, the system automatically degrades to OCR:

```
Image Input
  │
  ├─ easyocr ────────────── ✅ Success → Text + confidence scores
  │  (offline, Chinese + English, auto-downloads model on first run)
  │
  ├─ pytesseract ────────── ✅ Success → Extracted text
  │  (requires: brew install tesseract)
  │
  └─ Pillow metadata ────── 🆘 Last resort
     (format / dimensions / mode / file size / EXIF)
```

OCR results include a prominent warning that only text was extracted — scene context, objects, people, and colors are not available — along with API key configuration instructions.

---

## Video Pipeline

### Local Video

```
Video File
  │
  ├─ ffprobe probes duration
  │   ├─ Success → uniform sampling by duration (e.g., 60s video, 6 frames = 1 per 10s)
  │   └─ Failure → fallback to even-interval sampling
  │
  ├─ ffmpeg extracts keyframes (jpg)
  │
  ├─ Per-frame vision model description
  │
  └─ Aggregate frame descriptions → describe_text generates coherent summary
```

### Remote Video URL

Passed directly to the vision model (providers like Gemini natively support video URL processing).

---

## Adding New Providers

The provider system uses the **registry pattern** — add a new provider in two steps.

### Step 1: Implement a Provider Subclass

```python
class MyProvider(BaseProvider):
    """Custom provider adapter example."""

    def __init__(self, api_key: str):
        from my_sdk import Client
        self._client = Client(api_key=api_key, timeout=120)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        """Construct request → call API → return text."""
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
        """(Optional) Text-only call, no image involved."""
        resp = self._client.chat.create(
            model=model,
            messages=[{"role": "user", "content": prompt + "\n\n" + text}],
        )
        return resp.choices[0].message.content
```

### Step 2: Register in the Provider Table

Add one line to `PROVIDER_REGISTRY` in `vision_describe.py`:

```python
PROVIDER_REGISTRY: list[tuple[ProviderInfo, type[BaseProvider]]] = [
    (ProviderInfo("zhipu",    "ZHIPU_API_KEY",    "glm-4.6v",         "Zhipu GLM"),        ZhipuProvider),
    (ProviderInfo("openai",   "OPENAI_API_KEY",    "gpt-4o",           "OpenAI GPT-4o"),     OpenAIProvider),
    (ProviderInfo("anthropic","ANTHROPIC_API_KEY", "claude-sonnet-4-6","Anthropic Claude"),  AnthropicProvider),
    (ProviderInfo("google",   "GOOGLE_API_KEY",    "gemini-2.5-flash", "Google Gemini"),     GoogleProvider),
    # ↓ New provider
    (ProviderInfo("myvendor", "MY_API_KEY",        "my-model-v1",      "My Vendor"),         MyProvider),
]
```

**`ProviderInfo` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Short name, used for `--provider` arg |
| `env_var` | `str` | Environment variable read for API key |
| `default_model` | `str` | Provider's default vision model |
| `label` | `str` | Display name for `--list-providers` and error messages |

After registration:

- `--list-providers` automatically shows the new provider's status
- `--provider myvendor` forces use of the new provider
- The `MY_API_KEY` env var is auto-detected
- No other code changes needed

### Provider Implementation Notes

In your `describe_image` method, `image_url` may be:

| Type | Format | Scenario |
|------|--------|----------|
| `data:` URL | `data:image/png;base64,...` | Local files |
| `https://` URL | `https://example.com/photo.jpg` | Remote files |

Pass images to the API according to your SDK's requirements:

- **URL-accepting SDKs** (e.g., zai, openai): pass URL directly
- **Base64-accepting SDKs** (e.g., anthropic): parse `data:` URL or download + base64-encode
- **PIL Image-accepting SDKs** (e.g., google-genai): load as PIL Image object

---

## Model Priority

The final model used is determined by these three layers (highest to lowest):

```
1. --model CLI argument           (highest priority, per-invocation)
2. VISION_MODEL env variable      (session-level override)
3. Provider default model         (ProviderInfo.default_model)
```

Examples:

```bash
# Use Zhipu but override model to glm-5-turbo
export ZHIPU_API_KEY="..."
.venv/bin/python vision_describe.py photo.jpg --model glm-5-turbo

# Globally default to gpt-4o-mini (instead of gpt-4o)
export OPENAI_API_KEY="..."
export VISION_MODEL="gpt-4o-mini"
.venv/bin/python vision_describe.py photo.jpg
```

---

## FAQ

### Can I use this without any API key?

Images: yes (OCR fallback). Videos: no. Without an API key, images go through OCR extraction — text only, no scene/object/person/color understanding.

### Why is OCR output garbled or in the wrong language?

easyocr supports Chinese and English by default. Garbled output usually means unusual text orientation or rare fonts. Try installing `tesseract` as a backup OCR engine.

### "ffprobe not found" error on video

Install ffmpeg: `brew install ffmpeg`. ffprobe is bundled with ffmpeg.

### Remote URL OCR fails

OCR requires local file access. Remote URLs cannot be OCR'd directly. Download locally first or configure an API key.

### How do I change the output language?

Use `--prompt`:

```bash
.venv/bin/python vision_describe.py photo.jpg --prompt "Please describe in English"
```

### I have multiple API keys configured — which one is used?

Auto-detected in registry order: Zhipu → OpenAI → Anthropic → Google. Use `--provider` to force a specific one.

### Google Gemini times out

Google's vision models can be slow with large images or video. The timeout defaults to 90s for all providers. Increase it via `export VISION_TIMEOUT=120`.

### Will this conflict with a multimodal main model?

No error, but **redundant waste**. Multimodal models (Claude Opus, GPT-4o, etc.) can see images directly — the vision skill will still trigger and make an extra vision API call, producing a text description the main model doesn't need. **Only use this skill with text-only main models (e.g., DeepSeek V4 Pro).**
