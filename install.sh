#!/usr/bin/env bash
# vision skill — 安装 Python 依赖
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ="$SCRIPT_DIR/auto_config/requirements.txt"

echo "=== vision skill — 安装依赖 ==="
echo ""

# 有激活的虚拟环境 → 直接用
if [ -n "${VIRTUAL_ENV:-}${CONDA_PREFIX:-}" ]; then
    if command -v uv &>/dev/null; then
        echo ">>> uv pip install ..."
        uv pip install -r "$REQ"
    else
        echo ">>> pip install ..."
        pip install -r "$REQ"
    fi
elif command -v uv &>/dev/null; then
    # uv 无虚拟环境 → 尝试 --system，失败则回退 pip
    echo ">>> uv pip install --system ..."
    uv pip install --system -r "$REQ" 2>/dev/null || {
        echo ">>> --system 失败，回退 pip3 install ..."
        pip3 install -r "$REQ"
    }
elif command -v pip3 &>/dev/null; then
    echo ">>> pip3 install ..."
    pip3 install -r "$REQ"
elif command -v pip &>/dev/null; then
    echo ">>> pip install ..."
    pip install -r "$REQ"
else
    echo "未检测到 pip，请先安装 Python 3.10+"
    exit 1
fi

echo ""
echo "=== 依赖安装完成 ==="
echo ""
echo "下一步 — 配置 API key（三选一）："
echo ""
echo "  方式一：环境变量（临时生效）"
echo "    export ZHIPU_API_KEY=\"your-key\""
echo "    export OPENAI_API_KEY=\"your-key\""
echo ""
echo "  方式二：项目级 settings（仅当前项目）"
echo "    编辑 .claude/settings.local.json，写入 env 字段"
echo ""
echo "  方式三：全局 settings（所有项目）"
echo "    编辑 ~/.claude/settings.json，写入 env 字段"
echo ""
echo "可选系统依赖："
echo "  brew install ffmpeg        # 视频关键帧提取"
echo "  brew install tesseract     # pytesseract OCR 引擎"
