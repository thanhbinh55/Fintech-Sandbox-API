#!/usr/bin/env bash
set -e

# Change to script directory
cd "$(dirname "$0")"

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "=========================================================="
echo "🚀 FINTECH SANDBOX API — STARTING UP"
echo "=========================================================="
echo "👉 Local API URL:  http://localhost:8000"
echo "👉 Swagger UI:     http://localhost:8000/docs"
echo "👉 Health Check:   http://localhost:8000/health"
echo "=========================================================="

# Run uvicorn using the project's python environment
exec .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
