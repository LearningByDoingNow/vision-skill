---
name: vision
description: 多厂商多模态图片/视频描述，无 API key 时自动 OCR 兜底。让纯文本模型理解视觉内容。
when_to_use: 用户附带图片(png/jpg/gif/webp/bmp)、视频(mp4/avi/mov/mkv/webm)、图片/视频URL、要求描述图片/截图/照片/视频、输入 /vision、消息中出现 [Image # 或 [Video #
allowed-tools: Bash(.venv/bin/python *)
---

## ⚠️ 强制规则

**对话中出现 `[Image #N]` 或 `[Video #N]` 时，必须先执行下方的 Shell 命令获取媒体描述，然后再回答问题。绝不跳过脚本直接回复。**

你无法直接查看图片或视频。这些 `[Image #N]` / `[Video #N]` 是你仅有的视觉入口——你没有绕过它们的任何能力。

## 输入来源

| 输入方式 | 触发场景 |
|----------|----------|
| TUI 粘贴/拖入图片 | 对话中出现 `[Image #N]`，脚本参数为该临时文件路径 |
| 本地图片/视频文件 | `/vision photo.jpg` 或 `/vision video.mp4` |
| 远程 URL | `/vision https://example.com/photo.jpg` |
| 多个文件 | `/vision img1.jpg img2.png` |
| stdin 管道 | `/vision` 配合管道输入 |

> 即使文件无扩展名（TUI 临时文件），脚本也通过文件头魔数自动识别图片/视频类型。

## API 状态检测

```!
echo "=== 多模态 API 配置状态 ==="
for var in ZHIPU_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY; do
  if [ -n "${(P)var}" ]; then
    echo "$var: 已配置 ✓"
  else
    echo "$var: 未配置 ✗"
  fi
done
if [ -n "$VISION_MODEL" ]; then
  echo "VISION_MODEL: $VISION_MODEL (覆盖厂商默认模型)"
fi
```

## 执行命令

```bash
.venv/bin/python ${CLAUDE_SKILL_DIR}/scripts/vision_describe.py $ARGUMENTS
```

行为：
- 自动检测第一个已配置 API key 的厂商，使用其默认模型
- 若设置了 `VISION_MODEL` 环境变量，则覆盖厂商默认模型
- 模型优先级：`--model 参数` > `VISION_MODEL 环境变量` > 厂商默认值
- 图片无 API key → 自动 OCR 兜底（easyocr > pytesseract > 基础图像信息）
- 视频无 API key → 提示用户配置（视频无法 OCR）
- 支持同时传入多个文件，逐个描述
- TUI 粘贴的临时图片无扩展名也能识别（文件头魔数检测）
- API 超时默认 90s（保护上限，非固定延迟），可通过 `VISION_TIMEOUT=120` 自定义

参数：
- 指定厂商：`--provider openai`（可选：zhipu/openai/anthropic/google）
- 指定模型：`--model gpt-4o-mini`（也可设置 VISION_MODEL 环境变量）
- 自定义描述要求：`--prompt "重点关注文字内容"`
- 视频更多帧：`--max-frames 10`（默认 6）
- 查看所有厂商状态：`--list-providers`
- 从标准输入读取：使用 `-` 作为文件参数

## 输出处理

- 脚本输出是你理解媒体内容的唯一依据
- 基于描述回答用户问题，不超出描述范围补充不存在的内容
- 脚本执行失败时如实报告错误
- OCR 兜底结果：告知用户仅提取了文字，建议配置 API key

## 引导用户配置

若环境检测显示所有 API key 均为"未配置"，主动提示：
1. 当前只能使用 OCR 提取图片文字，无法理解场景/物体/人物/色彩等
2. 配置任一 API key 即可获得完整的视觉理解能力：

```
export ZHIPU_API_KEY="your-key"     # 智谱 GLM (glm-4.6v)
export OPENAI_API_KEY="your-key"    # OpenAI GPT-4o
export ANTHROPIC_API_KEY="your-key" # Anthropic Claude
export GOOGLE_API_KEY="your-key"    # Google Gemini
export VISION_MODEL="gpt-4o-mini"   # （可选）覆盖默认模型
```

3. 也可将 key 和 model 写入 `.claude/settings.local.json` 的 `env` 字段
4. 一键安装依赖：`pip install -r .claude/skills/vision/auto_config/requirements.txt`

## 约束

- **对话中有 `[Image #N]` 或 `[Video #N]` 必须先跑脚本**，不跑脚本就回复 = 违规
- API key 缺失时主动降级 OCR，告知局限性，引导配置
- 默认返回中文描述；需其他语言通过 `--prompt` 指定
- 视频本地文件依赖 ffmpeg，未安装则告知用户
