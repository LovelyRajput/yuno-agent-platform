"""LangGraph agent runtime.

Each Agent row in the DB is materialised into a LangGraph ReAct-style executor
that can call tools, observe results, and iterate up to `max_iterations` times.
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app import models
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.agents.tools import get_tools
from app.events import emit


# Approximate Claude pricing per 1K tokens (input/output) for cost tracking.
# These are illustrative; update if Anthropic pricing changes.
PRICING_PER_1K = {
    "llama-3.3-70b-versatile": (0.0, 0.0),
    "llama-3.1-8b-instant": (0.0, 0.0),
}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICING_PER_1K.get(model, (0.003, 0.015))
    return (tokens_in / 1000) * p_in + (tokens_out / 1000) * p_out


def _build_executor(agent: models.Agent):
    """Compile a LangGraph ReAct executor for the given Agent row."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to .env and restart."
        )
    llm = ChatGroq(
        model=agent.model or DEFAULT_MODEL,
        api_key=GROQ_API_KEY,
        max_tokens=agent.max_tokens or 1024,
        temperature=agent.temperature if agent.temperature is not None else 0.7,
    )
    tools = get_tools(agent.tools or [])
    # create_react_agent handles the full reason->act->observe loop for us
    return create_react_agent(llm, tools)


def _persist_message(
    db: Session,
    run_id: int,
    agent: Optional[models.Agent],
    sender: str,
    content: str,
    meta: Optional[dict] = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> models.Message:
    msg = models.Message(
        run_id=run_id,
        agent_id=agent.id if agent else None,
        sender=sender,
        sender_name=agent.name if agent else sender,
        content=content,
        meta=meta or {},
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    emit(
        "message",
        run_id=run_id,
        message_id=msg.id,
        agent_id=msg.agent_id,
        sender=msg.sender,
        sender_name=msg.sender_name,
        content=msg.content[:2000],
        meta=msg.meta,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    return msg


async def run_agent(
    db: Session,
    agent: models.Agent,
    user_input: str,
    run: models.Run,
    inter_agent_context: Optional[str] = None,
) -> str:
    """Run an agent once with the given input. Returns the agent's final text reply.

    Persists every message (system, user, tool calls, tool results, agent reply) and
    emits live events to the monitor.
    """
    emit("agent_start", run_id=run.id, agent_id=agent.id, agent_name=agent.name)

    # Persist the input as a user message (or inter-agent message)
    if inter_agent_context:
        _persist_message(
            db, run.id, None, "inter-agent",
            f"-> {agent.name}: {user_input}",
            meta={"context": inter_agent_context},
        )
    else:
        _persist_message(db, run.id, None, "user", user_input)

    executor = _build_executor(agent)

    system_prompt = agent.system_prompt or "You are a helpful AI agent."
    if agent.guardrails:
        system_prompt += f"\n\nGuardrails:\n{agent.guardrails}"
    if inter_agent_context:
        system_prompt += f"\n\nUpstream context from previous agent:\n{inter_agent_context}"

    inputs = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]
    }

    config = {"recursion_limit": max(agent.max_iterations * 2, 4)}

    final_text = ""
    tokens_in_total = 0
    tokens_out_total = 0
    seen_message_ids: set[str] = set()

    try:
        async for event in executor.astream(inputs, config=config):
            # event is keyed by node name; values contain new messages
            for node_name, node_state in event.items():
                for m in node_state.get("messages", []):
                    mid = getattr(m, "id", None) or f"{node_name}:{id(m)}"
                    if mid in seen_message_ids:
                        continue
                    seen_message_ids.add(mid)

                    if isinstance(m, AIMessage):
                        # Track token usage from metadata when available
                        meta = getattr(m, "response_metadata", {}) or {}
                        usage = meta.get("usage", {}) or getattr(m, "usage_metadata", {}) or {}
                        t_in = usage.get("input_tokens", 0)
                        t_out = usage.get("output_tokens", 0)
                        tokens_in_total += t_in
                        tokens_out_total += t_out

                        # Tool calls in this AI message
                        tool_calls = getattr(m, "tool_calls", []) or []
                        if tool_calls:
                            for tc in tool_calls:
                                _persist_message(
                                    db, run.id, agent, "tool_call",
                                    f"{tc.get('name')}({tc.get('args')})",
                                    meta={"tool": tc.get("name"), "args": tc.get("args")},
                                )
                        text = m.content if isinstance(m.content, str) else str(m.content)
                        if text.strip():
                            _persist_message(
                                db, run.id, agent, "agent", text,
                                tokens_in=t_in, tokens_out=t_out,
                                meta={"node": node_name},
                            )
                            final_text = text
                    elif isinstance(m, ToolMessage):
                        _persist_message(
                            db, run.id, agent, "tool_result",
                            str(m.content),
                            meta={"tool": getattr(m, "name", "")},
                        )

    except Exception as e:
        _persist_message(db, run.id, agent, "system", f"ERROR: {e}")
        emit("agent_error", run_id=run.id, agent_id=agent.id, error=str(e))
        raise

    cost = _estimate_cost(agent.model or DEFAULT_MODEL, tokens_in_total, tokens_out_total)
    run.total_tokens += tokens_in_total + tokens_out_total
    run.total_cost_usd += cost
    db.commit()

    emit(
        "agent_done",
        run_id=run.id,
        agent_id=agent.id,
        agent_name=agent.name,
        tokens_in=tokens_in_total,
        tokens_out=tokens_out_total,
        cost_usd=round(cost, 6),
    )
    return final_text or ""
