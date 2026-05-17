"""Multi-agent workflow orchestrator.

A workflow's `graph` field is a dict of the shape:
    {
        "start": "node_id",
        "nodes": {
            "node_id": {
                "agent_id": 1,
                "name": "Researcher",
                "prompt_template": "Find information about: {{input}}",
                "next": "next_node_id" | null,
                # optional conditional branching:
                # "branches": [
                #   {"if_contains": "yes", "to": "approve_node"},
                #   {"if_contains": "no",  "to": "reject_node"}
                # ],
                # optional feedback loop (re-runs the same node up to N times):
                # "loop_until_contains": "DONE",
                # "max_loops": 3
            },
            ...
        }
    }

Execution is async and persists every step. Agent-to-agent communication is the
output text of node N being passed as input + upstream context to node N+1.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.agents.runtime import run_agent
from app.events import emit


def _render(template: str, variables: dict) -> str:
    """Tiny {{var}} template renderer — no Jinja overhead for this hot path."""
    out = template or ""
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


async def execute_workflow(
    db: Session,
    workflow: models.Workflow,
    user_input: str,
    trigger: str = "manual",
) -> models.Run:
    """Execute a workflow end-to-end. Returns the completed Run row."""
    run = models.Run(
        workflow_id=workflow.id,
        trigger=trigger,
        status="running",
        input=user_input,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    emit("run_start", run_id=run.id, workflow_id=workflow.id, workflow_name=workflow.name)

    graph = workflow.graph or {}
    nodes = graph.get("nodes", {})
    current_id: Optional[str] = graph.get("start")

    if not current_id or current_id not in nodes:
        run.status = "failed"
        run.output = "Workflow has no valid start node."
        run.finished_at = datetime.utcnow()
        db.commit()
        emit("run_failed", run_id=run.id, reason="no_start_node")
        return run

    last_output = user_input
    upstream_context: Optional[str] = None
    visited_count: dict[str, int] = {}
    safety_step_limit = 25  # absolute cap to prevent runaway loops

    try:
        steps = 0
        while current_id and steps < safety_step_limit:
            steps += 1
            node = nodes.get(current_id)
            if not node:
                break

            agent_id = node.get("agent_id")
            if not agent_id:
                emit("node_skipped", run_id=run.id, node_id=current_id, reason="no_agent")
                current_id = node.get("next")
                continue

            agent = db.query(models.Agent).filter_by(id=agent_id).first()
            if not agent:
                emit("node_skipped", run_id=run.id, node_id=current_id, reason="agent_not_found")
                current_id = node.get("next")
                continue

            # Build the prompt for this node
            template = node.get("prompt_template") or "{{input}}"
            node_input = _render(template, {"input": last_output, "original": user_input})

            emit(
                "node_start", run_id=run.id, node_id=current_id,
                agent_id=agent.id, agent_name=agent.name,
            )

            output = await run_agent(
                db, agent, node_input, run,
                inter_agent_context=upstream_context,
            )
            last_output = output
            upstream_context = f"({agent.name} said): {output}"

            emit("node_done", run_id=run.id, node_id=current_id, output=output[:500])

            # Handle feedback loops
            visited_count[current_id] = visited_count.get(current_id, 0) + 1
            max_loops = node.get("max_loops", 1)
            loop_until = node.get("loop_until_contains")
            if loop_until and visited_count[current_id] < max_loops and loop_until.lower() not in output.lower():
                # repeat this node
                continue

            # Handle conditional branches
            branches = node.get("branches") or []
            next_id = node.get("next")
            for br in branches:
                cond = br.get("if_contains", "")
                if cond and cond.lower() in output.lower():
                    next_id = br.get("to")
                    break

            current_id = next_id

        run.status = "completed"
        run.output = last_output
        run.finished_at = datetime.utcnow()
        db.commit()
        emit("run_done", run_id=run.id, output=last_output[:500],
             total_tokens=run.total_tokens, total_cost_usd=run.total_cost_usd)
    except Exception as e:
        run.status = "failed"
        run.output = f"ERROR: {e}"
        run.finished_at = datetime.utcnow()
        db.commit()
        emit("run_failed", run_id=run.id, error=str(e))
        raise

    return run


async def execute_single_agent(
    db: Session,
    agent: models.Agent,
    user_input: str,
    trigger: str = "manual",
) -> models.Run:
    """Run a single agent (no workflow). Useful for the Telegram bot and quick tests."""
    run = models.Run(
        agent_id=agent.id,
        trigger=trigger,
        status="running",
        input=user_input,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    emit("run_start", run_id=run.id, agent_id=agent.id, agent_name=agent.name)

    try:
        output = await run_agent(db, agent, user_input, run)
        run.status = "completed"
        run.output = output
        run.finished_at = datetime.utcnow()
        db.commit()
        emit("run_done", run_id=run.id, output=output[:500],
             total_tokens=run.total_tokens, total_cost_usd=run.total_cost_usd)
    except Exception as e:
        run.status = "failed"
        run.output = f"ERROR: {e}"
        run.finished_at = datetime.utcnow()
        db.commit()
        emit("run_failed", run_id=run.id, error=str(e))
    return run
