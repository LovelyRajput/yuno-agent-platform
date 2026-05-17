"""Pytest fixtures: in-memory SQLite + mocked agent runtime so tests need no API key."""
from __future__ import annotations

import os
import sys
import pathlib
import pytest
from unittest.mock import patch, AsyncMock

# Make the project importable when running `pytest` from project root
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Force tests to use an in-memory DB before any app modules are imported
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-only")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database, models  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch):
    """Use a fresh in-memory SQLite for every test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSession)
    database.Base.metadata.create_all(bind=engine)
    yield
    database.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """A DB session for tests that don't go through FastAPI."""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient with the patched DB."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_runtime():
    """Mock out the agent runtime so we don't make real LLM calls."""
    async def fake_run(db, agent, user_input, run, inter_agent_context=None):
        # Persist a fake "agent" message so message-delivery tests pass
        from app.agents.runtime import _persist_message
        _persist_message(db, run.id, agent, "agent", f"[mocked reply from {agent.name}] {user_input}")
        return f"[mocked reply from {agent.name}] {user_input}"
    with patch("app.agents.workflow.run_agent", new=AsyncMock(side_effect=fake_run)):
        yield
