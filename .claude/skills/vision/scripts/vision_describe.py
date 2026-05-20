#!/usr/bin/env python3
"""多厂商多模态图片/视频描述工具，支持 OCR 兜底。

按环境变量自动检测可用厂商（优先级=注册顺序）：
  智谱 Zhipu:  ZHIPU_API_KEY    — glm-4.6v / glm-5-turbo
  OpenAI:       OPENAI_API_KEY    — gpt-4o / gpt-4o-mini
  Anthropic:    ANTHROPIC_API_KEY — claude-sonnet-4-6 / claude-haiku-4-5
  Google:       GOOGLE_API_KEY    — gemini-2.5-flash / gemini-2.5-pro

无 API key → OCR 兜底（easyocr > pytesseract > Pillow 基础信息）。
依赖：pip install zai openai anthropic google-genai easyocr pillow requests
"""

from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 全局配置
# ═══════════════════════════════════════════════════════════════════════════════

# API 超时上限（秒）。多模态视觉 API 通常 20-60s 响应，大图可能更久，90s 兼顾安全与容错。
# 可通过 VISION_TIMEOUT 环境变量自定义，例如 VISION_TIMEOUT=120。
# 注意：这是等待上限，非固定延迟——API 在 10s 返回则 10s 就继续，不会空等。
_API_TIMEOUT = int(os.environ.get("VISION_TIMEOUT", "90"))


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

# 常见图像/视频文件头魔数 — 无需任何依赖即可识别，覆盖 TUI 临时文件（无扩展名）场景
_IMAGE_MAGIC = {
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff':         'image/jpeg',
    b'GIF87a':               'image/gif',
    b'GIF89a':               'image/gif',
    b'BM':                   'image/bmp',
}
_VIDEO_MAGIC = {
    b'\x1aE\xdf\xa3':        'video/webm',   # Matroska / WebM
}
# RIFF 容器需要进一步区分
_RIFF_IMAGE = b'WEBP'
_RIFF_VIDEO = b'AVI '

# MP4/MOV 在偏移 4 处有 ftyp
_FTYP_OFFSET = 4
_FTYP_MAGIC = b'ftyp'


def _detect_type_from_content(path: str) -> str | None:
    """读取文件头魔数检测媒体类型，无需依赖文件扩展名。适用于 TUI 粘贴的临时文件。"""
    try:
        with open(path, 'rb') as f:
            header = f.read(16)
    except OSError:
        return None

    if len(header) < 4:
        return None

    # 图像魔数
    for magic, mime in _IMAGE_MAGIC.items():
        if header.startswith(magic):
            return mime

    # RIFF 容器（WebP 或 AVI）
    if header[:4] == b'RIFF' and len(header) >= 12:
        subtype = header[8:12]
        if subtype == _RIFF_IMAGE:
            return 'image/webp'
        if subtype == _RIFF_VIDEO:
            return 'video/avi'

    # 视频魔数
    for magic, mime in _VIDEO_MAGIC.items():
        if header.startswith(magic):
            return mime

    # MP4/MOV: ftyp 在偏移 4
    if len(header) >= 8 and header[_FTYP_OFFSET:_FTYP_OFFSET + 4] == _FTYP_MAGIC:
        return 'video/mp4'

    return None


def _guess_mime(path: str) -> str:
    """检测文件 MIME 类型：优先内容魔数 → 兜底扩展名。"""
    content_type = _detect_type_from_content(path)
    if content_type:
        return content_type
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def _is_image(path: str) -> bool:
    return (_guess_mime(path) or "").startswith("image/")


def _is_video(path: str) -> bool:
    return (_guess_mime(path) or "").startswith("video/")


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _encode_data_url(path: str) -> str:
    mime = _guess_mime(path)
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# -------------------------------------------------------------------------------
# 优化后的描述提示词 - 结构化输出，确保纯文本模型可完整理解
# -------------------------------------------------------------------------------

IMAGE_PROMPT = """\
请对这张图片进行全方位、无遗漏的详细描述。你的描述将作为一个纯文本 AI 的\
唯一信息来源，它完全无法看到原图，因此你必须做到：宁可冗长也不要有任何遗漏。

按以下结构组织输出：

## 一、场景概述
- 一句话概括图片主题和整体氛围（室内/室外、白天/夜晚、正式/休闲等）。

## 二、环境与背景
- 空间类型、光线条件、天气和时间感。
- 背景中所有可见的建筑物、家具、自然元素、装饰物的位置和外观。

## 三、前景主体（逐一列举，不可遗漏）
### 人物（如有）
- 数量、性别（如可辨）、大致年龄、衣着（颜色/款式/材质）、姿态、动作、面部表情。
- 人物之间的空间关系和互动状态。
### 物体
- 逐一列出所有可见物体，描述：名称、颜色、材质、形状、尺寸感、品牌/标签、状态。
- 物体之间的空间位置关系（如：A 在 B 左边，C 放在 D 上方）。
- 前景与背景的层次关系。

## 四、文字内容
- 逐条列出画面中出现的每一个文字、数字、符号、标志，注明位置。
- 描述字体风格（手写/印刷/衬线/无衬线）、颜色、大小（相对）。
- 模糊或部分遮挡的文字：注明"不确定"并给出你的最佳猜测。

## 五、色彩与构图
- 主色调和辅助色。
- 视觉焦点位置（画面中心/三分线某处/边缘）。
- 构图方式（对称/三分法/对角线/引导线/框架式等）。

## 六、细节与特殊元素
- 反射、阴影、纹理、图案、透明度等视觉细节。
- 如有 UI 界面：描述窗口布局、按钮位置、菜单项、图标。
- 如有数据图表：描述图表类型、轴标签、数据趋势、图例。
- 如有代码：逐行抄录，保留缩进。

## 七、整体印象
- 图片传达的信息、情绪或用途。
- 适合的使用场景（宣传物料/技术文档/生活记录/艺术创作等）。

重要：描述应以让盲人通过文字完整还原画面为目标。\
"""

VIDEO_FRAME_PROMPT = (
    "这是视频的第 {frame}/{total} 个关键帧（按时间顺序排列）。"
    "请详细描述这个帧中所有可见的物体、人物、场景、文字和任何值得注意的细节。"
)

VIDEO_SUMMARY_PROMPT = (
    "以下是从一个视频中按时间顺序提取的 {total} 个关键帧的文字描述。"
    "请基于这些描述生成一段连贯、完整的视频内容总结：\n"
    "- 视频整体主题和场景\n"
    "- 场景变化与转场\n"
    "- 人物动作的时间序列\n"
    "- 关键事件的时间线\n"
    "- 出现的文字/对话（如有）\n\n"
    "=== 帧描述 ===\n\n{descriptions}\n\n"
    "=== 总结 ==="
)

VIDEO_URL_PROMPT = (
    "请对这个视频进行全方位、无遗漏的详细描述，你的描述将作为一个纯文本 AI 的"
    "唯一信息来源。请包含：视频主题、场景设置、出现的所有人物和物体、"
    "动作时间线、文字内容、色彩与氛围、以及任何值得注意的细节。"
)

OCR_FALLBACK_NOTE = (
    "\n\n---\n"
    "⚠️ 当前运行在 OCR 兜底模式：以上内容仅包含从图片中提取的文字，"
    "无法描述场景、物体、人物、色彩等视觉信息。\n\n"
    "如需完整的视觉理解能力，请设置以下任一环境变量：\n"
    "  export ZHIPU_API_KEY=\"your-key\"    # 智谱 GLM\n"
    "  export OPENAI_API_KEY=\"your-key\"    # OpenAI GPT-4o\n"
    "  export ANTHROPIC_API_KEY=\"your-key\" # Anthropic Claude\n"
    "  export GOOGLE_API_KEY=\"your-key\"    # Google Gemini\n\n"
    "OCR 增强（可选）: pip install easyocr"
)


# ═══════════════════════════════════════════════════════════════════════════════
# 视频关键帧提取
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_keyframes(video_path: str, max_frames: int = 6) -> list[str]:
    out_dir = tempfile.mkdtemp(prefix="vision_keyframes_")
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=30,
        )
        if probe.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {probe.stderr.strip()}")
        info = json.loads(probe.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
    except FileNotFoundError:
        raise RuntimeError(
            "未找到 ffprobe。请安装 ffmpeg: brew install ffmpeg"
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[警告] 解析视频时长失败: {e}，将使用均匀抽帧", file=sys.stderr)
        duration = 0

    if duration <= 0:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{max(max_frames, 1)}",
            "-frames:v", str(max_frames),
            f"{out_dir}/frame_%03d.jpg",
        ]
    else:
        interval = max(1, int(duration / max_frames))
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{interval}",
            "-frames:v", str(max_frames),
            f"{out_dir}/frame_%03d.jpg",
        ]

    subprocess.run(cmd, capture_output=True, timeout=120)
    frames = sorted(Path(out_dir).glob("frame_*.jpg"))
    return [str(f) for f in frames]


# ═══════════════════════════════════════════════════════════════════════════════
# 多模态厂商适配器
# ═══════════════════════════════════════════════════════════════════════════════

class BaseProvider(ABC):
    """厂商适配器基类。"""

    @abstractmethod
    def describe_image(self, image_url: str, prompt: str, model: str) -> str: ...

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        """纯文本调用（用于视频帧汇总），默认复用 describe_image。"""
        # 子类可重写以使用更便宜的文本模型
        return self.describe_image(text, prompt, model)


class ZhipuProvider(BaseProvider):
    """智谱 GLM 视觉模型 (zai SDK)。"""

    def __init__(self, api_key: str):
        from zai import ZhipuAiClient
        self._client = ZhipuAiClient(api_key=api_key)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image_url:
            content.insert(0, {"type": "image_url", "image_url": {"url": image_url}})
        resp = self._client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": content}],
            stream=False, temperature=0.1, timeout=_API_TIMEOUT,
        )
        return resp.choices[0].message.content

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt + "\n\n" + text}],
            stream=False, temperature=0.3, timeout=_API_TIMEOUT,
        )
        return resp.choices[0].message.content


class OpenAIProvider(BaseProvider):
    """OpenAI GPT-4o 视觉模型。"""

    def __init__(self, api_key: str):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, timeout=_API_TIMEOUT)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image_url:
            content.insert(0, {"type": "image_url", "image_url": {"url": image_url}})
        resp = self._client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": content}],
            temperature=0.1,
        )
        return resp.choices[0].message.content

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt + "\n\n" + text}],
            temperature=0.3,
        )
        return resp.choices[0].message.content


class AnthropicProvider(BaseProvider):
    """Anthropic Claude 视觉模型。"""

    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=_API_TIMEOUT)

    @staticmethod
    def _parse_image_url(image_url: str) -> tuple[str, str]:
        """将 image_url 解析为 (media_type, base64_data)。"""
        if image_url.startswith("data:"):
            header, b64 = image_url.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]
            return (media_type, b64)
        # 远程 URL：下载
        import requests as req
        resp = req.get(image_url, timeout=30)
        ct = resp.headers.get("content-type", "image/png")
        media_type = ct.split(";")[0]
        b64 = base64.b64encode(resp.content).decode("ascii")
        return (media_type, b64)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        blocks: list[dict] = []
        if image_url:
            mt, b64 = self._parse_image_url(image_url)
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mt, "data": b64},
            })
        blocks.append({"type": "text", "text": prompt})
        resp = self._client.messages.create(
            model=model, max_tokens=4096,
            messages=[{"role": "user", "content": blocks}],
        )
        return resp.content[0].text

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        resp = self._client.messages.create(
            model=model, max_tokens=4096,
            messages=[{"role": "user", "content": prompt + "\n\n" + text}],
        )
        return resp.content[0].text


class GoogleProvider(BaseProvider):
    """Google Gemini 视觉模型。"""

    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key, http_options={"timeout": _API_TIMEOUT * 1000})

    @staticmethod
    def _load_image(image_url: str):
        """将 image_url 加载为 PIL Image。"""
        import PIL.Image
        if image_url.startswith("data:"):
            _, b64_data = image_url.split(",", 1)
            return PIL.Image.open(io.BytesIO(base64.b64decode(b64_data)))
        if image_url.startswith("http"):
            import requests as req
            return PIL.Image.open(io.BytesIO(req.get(image_url, timeout=30).content))
        return PIL.Image.open(image_url)

    def describe_image(self, image_url: str, prompt: str, model: str) -> str:
        parts: list = [prompt]
        if image_url:
            parts.insert(0, self._load_image(image_url))
        resp = self._client.models.generate_content(model=model, contents=parts)
        return resp.text

    def describe_text(self, text: str, prompt: str, model: str) -> str:
        resp = self._client.models.generate_content(
            model=model, contents=prompt + "\n\n" + text,
        )
        return resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# 厂商注册表
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProviderInfo:
    name: str
    env_var: str
    default_model: str
    label: str       # 中文显示名


PROVIDER_REGISTRY: list[tuple[ProviderInfo, type[BaseProvider]]] = [
    (ProviderInfo("zhipu",    "ZHIPU_API_KEY",    "glm-4.6v",            "智谱 GLM"),         ZhipuProvider),
    (ProviderInfo("openai",   "OPENAI_API_KEY",    "gpt-4o",              "OpenAI GPT-4o"),     OpenAIProvider),
    (ProviderInfo("anthropic","ANTHROPIC_API_KEY", "claude-sonnet-4-6",   "Anthropic Claude"),  AnthropicProvider),
    (ProviderInfo("google",   "GOOGLE_API_KEY",    "gemini-2.5-flash",    "Google Gemini"),     GoogleProvider),
]


def _detect_provider(preferred: Optional[str] = None
                     ) -> tuple[str, BaseProvider, str] | None:
    """检测可用厂商，返回 (name, instance, default_model) 或 None。"""
    # 用户指定厂商
    if preferred:
        for info, cls in PROVIDER_REGISTRY:
            if info.name == preferred:
                key = os.environ.get(info.env_var)
                if not key:
                    raise RuntimeError(
                        f"{info.label} 的 {info.env_var} 未设置。"
                        f"请 export {info.env_var}=<your-key>"
                    )
                return (info.name, cls(key), info.default_model)
        raise RuntimeError(f"未知厂商: {preferred}。可选: {_provider_names()}")

    # 自动检测第一个有 key 的厂商
    for info, cls in PROVIDER_REGISTRY:
        key = os.environ.get(info.env_var)
        if key:
            try:
                return (info.name, cls(key), info.default_model)
            except Exception as e:
                print(f"[警告] {info.label} 初始化失败: {e}", file=sys.stderr)
                continue

    return None


def _provider_names() -> str:
    return "/".join(info.name for info, _ in PROVIDER_REGISTRY)


def _provider_status() -> list[str]:
    """列出所有厂商的配置状态。"""
    lines = []
    for info, _ in PROVIDER_REGISTRY:
        configured = "已配置" if os.environ.get(info.env_var) else "未配置"
        lines.append(
            f"  {info.label:18s}  {info.env_var:22s}  {info.default_model:20s}  [{configured}]"
        )
    return lines


def _provider_env_guide() -> str:
    """生成 API key 配置指南。"""
    lines = ["配置方法：\n"]
    for info, _ in PROVIDER_REGISTRY:
        lines.append(
            f"  export {info.env_var}=\"your-key\"   # {info.label} ({info.default_model})"
        )
    lines.append(
        "\n  或在 .claude/settings.local.json 的 env 字段中添加以上变量。\n"
        "\n  可选：设置 VISION_MODEL 环境变量来指定默认模型，"
        "例如 VISION_MODEL=gpt-4o-mini。\n"
        "  优先级: --model 参数 > VISION_MODEL > 厂商默认值。"
    )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# OCR 兜底模块
# ═══════════════════════════════════════════════════════════════════════════════

# easyocr Reader 缓存，避免重复加载模型
_easyocr_reader = None


def _ocr_easyocr(image_path: str) -> str | None:
    """easyocr — 离线，中文+英文，首次运行会下载模型（~200MB）。"""
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["ch_sim", "en"], verbose=False)
    results = _easyocr_reader.readtext(image_path)
    if not results:
        return None
    lines = []
    for _, text, confidence in results:
        lines.append(f"- {text}  [置信度: {confidence:.0%}]")
    return "## OCR 文字提取 (easyocr)\n\n" + "\n".join(lines)


def _ocr_tesseract(image_path: str) -> str | None:
    """pytesseract — 需系统安装 tesseract（brew install tesseract）。"""
    import pytesseract
    from PIL import Image
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
    return f"## OCR 文字提取 (pytesseract)\n\n{text}" if text else None


def _image_basic_info(image_path: str) -> str:
    """Pillow 基础图像元信息。"""
    from PIL import Image
    img = Image.open(image_path)
    exif = img.getexif() if hasattr(img, "getexif") else {}
    info = (
        f"- 格式: {img.format}\n"
        f"- 尺寸: {img.size[0]} x {img.size[1]} 像素\n"
        f"- 模式: {img.mode}\n"
        f"- 文件大小: {os.path.getsize(image_path) / 1024:.1f} KB"
    )
    if exif:
        info += f"\n- EXIF: {dict(exif)}"
    return f"## 基础图像信息\n\n{info}\n\n[OCR 不可用] 未检测到文字。"


def _run_ocr(image_path: str) -> str:
    """OCR 链：easyocr → pytesseract → 基础信息。"""
    ocr_errors: list[str] = []

    for name, fn in [("easyocr", _ocr_easyocr), ("pytesseract", _ocr_tesseract)]:
        try:
            result = fn(image_path)
            if result:
                return result
            ocr_errors.append(f"{name}: 未检测到文字")
        except ImportError:
            ocr_errors.append(f"{name}: 未安装")
        except Exception as e:
            ocr_errors.append(f"{name}: {e}")

    # 最后兜底
    try:
        return _image_basic_info(image_path)
    except ImportError:
        return f"[OCR 不可用] Pillow 未安装。请运行: pip install easyocr pillow\n\n调试: {'; '.join(ocr_errors)}"
    except Exception as e:
        return f"[OCR 不可用] 所有方案均失败。\n\n调试: {'; '.join(ocr_errors)}; Pillow: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 核心 API
# ═══════════════════════════════════════════════════════════════════════════════

def describe_image(
    path_or_url: str,
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> str:
    """描述单张图片。自动选择厂商，无 API key 时降级 OCR。"""
    # 解析为 URL
    if _is_url(path_or_url):
        image_url = path_or_url
    elif os.path.isfile(path_or_url):
        image_url = _encode_data_url(path_or_url)
    else:
        raise FileNotFoundError(f"文件不存在: {path_or_url}")

    final_prompt = prompt or IMAGE_PROMPT

    # 尝试多模态 API
    detected = _detect_provider(provider_name)
    if detected:
        name, provider, default_model = detected
        use_model = model or os.environ.get("VISION_MODEL") or default_model
        print(f"[vision] 使用 {name} / {use_model}", file=sys.stderr)
        return provider.describe_image(image_url, final_prompt, use_model)

    # OCR 兜底
    print("[vision] 未检测到多模态 API key，进入 OCR 兜底模式", file=sys.stderr)
    if _is_url(path_or_url):
        ocr = (
            "[OCR 不可用] 远程 URL 无法 OCR。\n"
            "请下载图片到本地后重试，或配置多模态 API key 以获取完整视觉描述。"
        )
    else:
        ocr = _run_ocr(path_or_url)

    guide = _provider_env_guide()
    return ocr + OCR_FALLBACK_NOTE + "\n" + guide


def describe_video(
    path_or_url: str,
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_frames: int = 6,
    provider_name: Optional[str] = None,
) -> str:
    """描述视频：提取关键帧 → 逐帧描述 → 汇总。视频必须有多模态 API。"""
    detected = _detect_provider(provider_name)
    if not detected:
        guide = _provider_env_guide()
        return (
            "⚠️ 视频描述需要多模态 API key，OCR 无法处理视频。\n\n" + guide
        )

    name, provider, default_model = detected
    use_model = model or os.environ.get("VISION_MODEL") or default_model
    print(f"[vision] 使用 {name} / {use_model} 描述视频", file=sys.stderr)

    # URL 直接传（部分厂商支持视频 URL 的原生处理）
    if _is_url(path_or_url):
        return provider.describe_image(
            path_or_url,
            prompt or VIDEO_URL_PROMPT,
            use_model,
        )

    # 本地视频：抽帧 → 逐帧描述 → 汇总
    frames = _extract_keyframes(path_or_url, max_frames=max_frames)
    if not frames:
        raise RuntimeError("视频关键帧提取失败，请确认 ffmpeg 已安装。")

    frame_descriptions: list[str] = []
    for i, frame_path in enumerate(frames):
        frame_url = _encode_data_url(frame_path)
        fp = VIDEO_FRAME_PROMPT.format(frame=i + 1, total=len(frames))
        try:
            desc = provider.describe_image(frame_url, fp, use_model)
            frame_descriptions.append(f"[帧 {i+1}/{len(frames)}] {desc}")
        except Exception as e:
            frame_descriptions.append(f"[帧 {i+1}/{len(frames)}] 描述失败: {e}")

    # 汇总
    combined = "\n\n".join(frame_descriptions)
    summary = provider.describe_text(
        combined,
        VIDEO_SUMMARY_PROMPT.format(total=len(frames), descriptions=combined),
        use_model,
    )
    return summary


def describe_media(
    path_or_url: str,
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_video_frames: int = 6,
    provider_name: Optional[str] = None,
) -> str:
    """自动检测媒体类型并描述。

    path_or_url 可以是：
      - 本地文件路径（含 TUI 粘贴的临时图片，无扩展名也支持）
      - 远程 http/https URL
      - "-" 从标准输入读取（适用于管道输入）
    """
    # 标准输入
    if path_or_url == "-":
        from tempfile import NamedTemporaryFile
        data = sys.stdin.buffer.read()
        with NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(data)
            path_or_url = tf.name

    if _is_url(path_or_url):
        return describe_image(
            path_or_url, prompt=prompt, model=model, provider_name=provider_name,
        )

    if not os.path.isfile(path_or_url):
        raise FileNotFoundError(f"文件不存在: {path_or_url}")

    if _is_image(path_or_url):
        return describe_image(
            path_or_url, prompt=prompt, model=model, provider_name=provider_name,
        )
    elif _is_video(path_or_url):
        return describe_video(
            path_or_url, prompt=prompt, model=model,
            max_frames=max_video_frames, provider_name=provider_name,
        )
    else:
        raise ValueError(
            f"不支持的媒体类型: {_guess_mime(path_or_url)}。"
            "支持: PNG/JPG/GIF/WEBP/BMP (图片)，MP4/AVI/MOV/MKV/WEBM (视频)。"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="多厂商多模态图片/视频描述 + OCR 兜底",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python vision_describe.py photo.jpg\n"
            "  python vision_describe.py photo.jpg --provider openai --model gpt-4o-mini\n"
            "  python vision_describe.py video.mp4 --max-frames 10\n"
            "  python vision_describe.py --list-providers"
        ),
    )
    parser.add_argument("files", nargs="*", help="图片/视频的文件路径或 URL，支持多个。"
                        "使用 \"-\" 从标准输入读取")
    parser.add_argument("--provider", default=None,
                        help=f"指定厂商 ({_provider_names()})，默认自动检测第一个已配置的")
    parser.add_argument("--model", default=None,
                        help="指定模型。优先级: --model > VISION_MODEL 环境变量 > 厂商默认值")
    parser.add_argument("--prompt", default=None, help="自定义描述提示词")
    parser.add_argument("--max-frames", type=int, default=6, help="视频最大关键帧数（默认 6）")
    parser.add_argument("--list-providers", action="store_true",
                        help="列出所有厂商配置状态后退出")

    args = parser.parse_args()

    if args.list_providers:
        print("多模态 API 厂商状态：\n")
        for line in _provider_status():
            print(line)
        vision_model = os.environ.get("VISION_MODEL")
        if vision_model:
            print(f"\n  VISION_MODEL = {vision_model}  (将覆盖厂商默认模型)")
        detected = _detect_provider()
        if detected:
            default = os.environ.get("VISION_MODEL") or detected[2]
            print(f"\n当前将自动选用: {detected[0]} / {default}")
        else:
            print("\n未配置任何多模态 API key，图片将使用 OCR 兜底，视频不可用。")
            print(_provider_env_guide())
        return

    if not args.files:
        parser.print_help()
        sys.exit(1)

    exit_code = 0
    for i, file in enumerate(args.files):
        if len(args.files) > 1:
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(args.files)}] {file}")
            print(f"{'='*60}\n")
        try:
            result = describe_media(
                file,
                prompt=args.prompt,
                model=args.model,
                max_video_frames=args.max_frames,
                provider_name=args.provider,
            )
            print(result)
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
