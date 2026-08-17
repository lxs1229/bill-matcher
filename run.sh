#!/usr/bin/env bash
# 启动 Bill Matcher。 用法: ./run.sh  然后打开 http://localhost:8000
set -e
cd "$(dirname "$0")"

# 依赖检查 / 安装
if [ ! -d backend/.venv ]; then
  echo "创建虚拟环境并安装依赖..."
  python3 -m venv backend/.venv
  env -u PYTHONPATH backend/.venv/bin/pip install --quiet -r backend/requirements.txt
fi

echo "启动:  http://localhost:8000   (Ctrl+C 停止)"
cd backend
exec env -u PYTHONPATH .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
