#!/usr/bin/env bash
# Full setup for HypnosTTS on Lightning.ai (Ubuntu, L4 GPU)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== [1/5] System packages ==="
sudo apt-get update -y
sudo apt-get install -y ffmpeg nodejs npm

echo "=== [2/5] Python dependencies ==="
pip install -e . --quiet
pip install \
  fastapi uvicorn[standard] aiosqlite \
  python-dotenv httpx \
  langgraph langchain-openai langchain-community \
  tavily-python \
  diffusers accelerate transformers \
  pillow \
  --quiet

echo "=== [3/5] Frontend build ==="
cd "$ROOT/app/frontend"
npm install --silent
npx vite build --silent
cd "$ROOT"

echo "=== [4/5] Data directory ==="
mkdir -p app/data

echo "=== [5/5] Done ==="
echo "Run with: python run_app.py"
