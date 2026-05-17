"""Central configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (project root)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama-3.3-70b-versatile")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/platform.db")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))


def has_anthropic_key() -> bool:
    return bool(ANTHROPIC_API_KEY) and ANTHROPIC_API_KEY.startswith("sk-ant-")


def has_telegram_token() -> bool:
    return bool(TELEGRAM_BOT_TOKEN) and ":" in TELEGRAM_BOT_TOKEN


def has_groq_key() -> bool:
    return bool(GROQ_API_KEY) and GROQ_API_KEY.startswith("gsk_")
