#!/usr/bin/env bash
# Bill Matcher 一键安装脚本
# 用法:  ./setup.sh
# 说明:  视觉识别默认用云端 API(在 config.yaml 里填)；
#        本地 ollama 是可选方案，装了自动识别，不装也不影响安装。
set -e
cd "$(dirname "$0")"

echo "==> [1/2] 创建 Python 虚拟环境..."
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi

echo "==> [2/2] 安装后端依赖（首次约几分钟）..."
env -u PYTHONPATH backend/.venv/bin/pip install --quiet -r backend/requirements.txt

# 可选: 检查 ollama（本地视觉模型，装了更好用，不装也能用云端 API）
if command -v ollama >/dev/null 2>&1 && ! ollama list 2>/dev/null | grep -q "qwen2.5vl:7b"; then
  echo ""
  echo ">> 检测到 ollama，可选拉取本地视觉模型 qwen2.5vl:7b (~5GB)..."
  ollama pull qwen2.5vl:7b || echo "   (拉取失败可跳过，不影响云端 API 使用)"
fi

echo ""
echo "=============================================="
echo " 安装完成！下一步:"
echo "  1) 编辑 config.yaml，填入视觉/分类 AI 的 API"
echo "  2) ./run.sh 启动，浏览器打开 http://localhost:8000"
echo "=============================================="
