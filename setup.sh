#!/usr/bin/env bash
# Single-command setup script for Yuno AI Agent Orchestration Platform
set -e

echo "================================================================="
echo "  Yuno AI Agent Orchestration Platform — Setup"
echo "================================================================="

# Detect python
PYTHON=${PYTHON:-python3}
if ! command -v $PYTHON &> /dev/null; then
    PYTHON=python
fi

echo ""
echo "[1/4] Creating virtual environment..."
$PYTHON -m venv .venv

echo ""
echo "[2/4] Activating venv and installing dependencies..."
# shellcheck disable=SC1091
source .venv/bin/activate || source .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[3/4] Setting up .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  -> Created .env from template. EDIT IT with your API keys before running!"
else
    echo "  -> .env already exists. Skipping."
fi

echo ""
echo "[4/4] Initializing database and seeding workflow templates..."
$PYTHON -m app.seed

echo ""
echo "================================================================="
echo "  SETUP COMPLETE!"
echo "================================================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env and fill in ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN"
echo "  2. Run: ./run.sh"
echo "  3. Open: http://localhost:8000"
echo ""
