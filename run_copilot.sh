#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "=========================================================="
echo "🎙️  MOMO VOICE AI FINANCIAL COPILOT — STARTING UP"
echo "=========================================================="
echo "👉 Web UI URL:     http://localhost:7860"
echo "👉 Sandbox API:    http://localhost:8000/v1"
echo "👉 Health Check:   http://localhost:7860/health"
echo "=========================================================="

export PYTHONPATH="voice_copilot"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 7860 --app-dir voice_copilot --reload

