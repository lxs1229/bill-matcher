#!/usr/bin/env bash
# 启动 Bill Matcher。 用法: ./run.sh  然后打开 http://localhost:8000
set -e
cd "$(dirname "$0")"

# 检查 ollama（收据视觉识别需要）
if command -v ollama >/dev/null 2>&1; then
  if ! curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "!! 提示: ollama 服务未运行。收据识别将不可用。"
    echo "   请打开 Ollama 应用或运行:  ollama serve"
    echo "   （如果只要用 PDF 账单解析，可忽略继续。）"
  fi
else
  echo "!! 未检测到 ollama。收据识别不可用。安装见 https://ollama.com"
fi

# 依赖检查 / 安装
if [ ! -d backend/.venv ]; then
  echo "创建虚拟环境并安装依赖..."
  python3 -m venv backend/.venv
  env -u PYTHONPATH backend/.venv/bin/pip install --quiet -r backend/requirements.txt
fi

echo "启动:  http://localhost:8000   (Ctrl+C 停止)"
cd backend
exec env -u PYTHONPATH .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
