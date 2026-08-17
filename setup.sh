#!/usr/bin/env bash
# Bill Matcher 一键安装脚本
# 用法:  ./setup.sh
# 功能:  1) 检查 ollama 并拉取视觉模型
#        2) 创建 Python venv 并安装后端依赖
set -e
cd "$(dirname "$0")"

echo "==> [1/3] 检查 ollama 视觉模型..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "!! 未检测到 ollama。请先安装: https://ollama.com/download"
  echo "   然后运行:  ollama pull qwen2.5vl:7b"
  exit 1
fi
if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "!! ollama 服务未运行。请打开 Ollama 应用，或运行:  ollama serve"
  echo "   然后重新运行本脚本。"
  exit 1
fi
if ! ollama list | grep -q "qwen2.5vl:7b"; then
  echo "    正在拉取 qwen2.5vl:7b (~5GB，首次较慢)..."
  ollama pull qwen2.5vl:7b
fi
echo "    ✓ 视觉模型就绪"

echo "==> [2/3] 创建 Python 虚拟环境..."
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
# 安装依赖（PaddleOCR 体积较大，可加 --no-cache 避免缓存占用）
echo "==> [3/3] 安装后端依赖（首次约几分钟）..."
env -u PYTHONPATH backend/.venv/bin/pip install --quiet -r backend/requirements.txt
echo ""
echo "=============================================="
echo " 安装完成！启动方式:"
echo "   ./run.sh"
echo "   然后打开浏览器访问  http://localhost:8000"
echo "=============================================="
