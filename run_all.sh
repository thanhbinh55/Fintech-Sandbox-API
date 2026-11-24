#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "=========================================================="
echo "🌟 MOMO TECH CONTEST 2026 — FULL SYSTEM LAUNCHER"
echo "=========================================================="
echo "👉 1. Backend Core (Sandbox API): http://localhost:8000"
echo "      - Swagger Docs:             http://localhost:8000/docs"
echo "👉 2. Frontend & AI (Voice Copilot): http://localhost:7860"
echo "      - Giao diện Web có Micro:    http://localhost:7860"
echo "=========================================================="

cleanup() {
  echo ""
  echo "Đang dừng các tiến trình..."
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start Backend Sandbox
echo "Đang khởi động Fintech Sandbox API (cổng 8000)..."
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

sleep 2

# Start Frontend Voice Copilot
echo "Đang khởi động MoMo Voice AI Copilot (cổng 7860)..."
export PYTHONPATH="voice_copilot"
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 7860 --app-dir voice_copilot
