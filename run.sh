#!/usr/bin/env bash
# Start the platform (FastAPI + Telegram bot + agent runtime)
set -e

source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

echo "Starting Yuno AI Agent Orchestration Platform on http://localhost:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
