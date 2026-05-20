#!/usr/bin/env bash
# vision skill 一键安装脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== vision skill 安装 ==="
echo ""

# 检查 Python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "错误: 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi

echo "Python: $($PYTHON --version)"

# 创建虚拟环境（如不存在）
if [ ! -d ".venv" ]; then
    echo ""
    echo ">>> 创建虚拟环境 .venv ..."
    $PYTHON -m venv .venv
else
    echo ""
    echo ">>> .venv 已存在，跳过创建"
fi

# 安装依赖
echo ""
echo ">>> 安装 Python 依赖 ..."
.venv/bin/pip install -r .claude/skills/vision/auto_config/requirements.txt --quiet

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步 — 配置 API key（至少一个）："
echo "  export ZHIPU_API_KEY=\"your-key\"      # 智谱 GLM"
echo "  export OPENAI_API_KEY=\"your-key\"     # OpenAI"
echo "  export ANTHROPIC_API_KEY=\"your-key\"  # Anthropic Claude"
echo "  export GOOGLE_API_KEY=\"your-key\"     # Google Gemini"
echo ""
echo "或写入 .claude/settings.local.json 的 env 字段（不会被 git 追踪）。"
echo ""
echo "可选系统依赖："
echo "  brew install ffmpeg        # 视频关键帧提取"
echo "  brew install tesseract     # pytesseract OCR 引擎"
