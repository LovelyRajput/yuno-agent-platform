"""Pydantic schemas for the REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    role: str = "assistant"
    system_prompt: str = "You are a helpful AI agent."
    model: str = "claude-3-5-sonnet-20241022"
    tools: List[str] = Field(default_factory=list)
    memory_enabled: bool = True
    max_tokens: int = 1024
    temperature: float = 0.7
    max_iterations: int = 6
    guardrails: str = ""
    channels: List[str] = Field(default_factory=list)
    schedule: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[List[str]] = None
    memory_enabled: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    max_iterations: Optional[int] = None
    guardrails: Optional[str] = None
    channels: Optional[List[str]] = None
    schedule: Optional[str] = None


class AgentOut(AgentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    is_template: bool = False
    graph: dict = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_template: Optional[bool] = None
    graph: Optional[dict] = None


class WorkflowOut(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    agent_id: Optional[int]
    sender: str
    sender_name: str
    content: str
    meta: dict
    tokens_in: int
    tokens_out: int
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: Optional[int]
    agent_id: Optional[int]
    trigger: str
    status: str
    input: str
    output: str
    total_tokens: int
    total_cost_usd: float
    started_at: datetime
    finished_at: Optional[datetime]


class RunRequest(BaseModel):
    """Body for POST /workflows/{id}/run or /agents/{id}/run"""
    input: str = ""
    trigger: str = "manual"


class RunDetailOut(RunOut):
    messages: List[MessageOut] = []
