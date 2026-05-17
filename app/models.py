"""SQLAlchemy ORM models for agents, workflows, runs, and messages."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.database import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Agent(Base):
    """A configurable AI agent. The fundamental unit of the platform."""
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), default="assistant")
    system_prompt: Mapped[str] = mapped_column(Text, default="You are a helpful AI agent.")
    model: Mapped[str] = mapped_column(String(120), default="claude-3-5-sonnet-20241022")

    # Behavior config
    tools: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["web_search", "calculator"]
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)

    # Guardrails / limits
    max_iterations: Mapped[int] = mapped_column(Integer, default=6)
    guardrails: Mapped[str] = mapped_column(Text, default="")

    # Channels (e.g. ["telegram"]). At most one agent should be the telegram entry point.
    channels: Mapped[list] = mapped_column(JSON, default=list)

    # Optional schedule (cron-like string, informational only for the MVP)
    schedule: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Workflow(Base):
    """A directed sequence of agent steps with conditions and feedback loops."""
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    # graph: list of nodes, each {id, agent_id, name, next: [...], condition: "..."}
    graph: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Run(Base):
    """A single execution of a workflow (or single agent)."""
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workflows.id"), nullable=True)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)
    trigger: Mapped[str] = mapped_column(String(60), default="manual")  # manual, telegram, schedule
    status: Mapped[str] = mapped_column(String(30), default="running")  # running, completed, failed
    input: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="run", cascade="all, delete-orphan"
    )


class Message(Base):
    """A single message in a run — human input, agent output, inter-agent, or tool call."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)
    sender: Mapped[str] = mapped_column(String(60), default="agent")  # user, agent, tool, system, inter-agent
    sender_name: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # tool name, tokens, etc.
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped["Run"] = relationship("Run", back_populates="messages")


class TelegramChat(Base):
    """Persisted Telegram chat -> agent binding so we route replies correctly."""
    __tablename__ = "telegram_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)
    last_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
