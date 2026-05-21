---
name: vision-skill
description: >
  多厂商多模态图片/视频描述，无 API key 时自动 OCR 兜底，让纯文本模型理解视觉内容。
  Multi-provider multimodal image & video description with zero-config OCR fallback.
  MUST trigger when a user attaches images (png/jpg/gif/webp/bmp), videos (mp4/avi/mov/mkv/webm),
  image/video URLs, types /vision, or when [Image #N] / [Video #N] appears in the chat.
  Do NOT try to Read image files directly — you cannot parse binary data. Run the vision
  script instead. Cross-platform: works on Claude Code, OpenAI Codex, OpenCode, and OpenClaw.
when_to_use: 用户附带图片(png/jpg/gif/webp/bmp)、视频(mp4/avi/mov/mkv/webm)、图片/视频URL、要求描述图片/截图/照片/视频、输入 /vision、消息中出现 [Image#N] 或 [Video#N]
allowed-tools: Bash(python *)
---

## ⚠️ 强制规则

**对话中出现 `[Image #N]` 或 `[Video #N]` 时，立即停止一切操作，直接运行脚本获取媒体描述。禁止在此之前调用 Read 或其他工具去读取文件——你无法解析二进制图片/视频数据，脚本是你唯一的视觉入口。**

## 执行命令

先确认 Python 可用（`python3` 或 `python`），然后运行 `${CLAUDE_SKILL_DIR}/scripts/vision_describe.py`，传入用户文件路径或 URL 作为参数。

参数：`--provider openai` | `--model gpt-4o-mini` | `--prompt "重点关注文字"` | `--max-frames 10` | `--list-providers` | stdin 用 `-`
行为：自动检测已配置 API key 的厂商 → 调用视觉模型 → 输出描述。无 key 时图片自动 OCR 兜底，视频则提示配置。
超时：默认 90s，可通过 `VISION_TIMEOUT=120` 环境变量调整。

## 无 API key 时引导

所有厂商均未配置时，主动提示用户（三种方式任选）：

1. `export ZHIPU_API_KEY="xxx"` 临时生效
2. 写入 `.claude/settings.local.json` → `{ "env": { "ZHIPU_API_KEY": "xxx" } }`
3. 写入 `~/.claude/settings.json` 全局生效

脚本输出是你理解媒体内容的唯一依据，描述之外不编造内容。OCR 结果需告知用户仅提取了文字。
