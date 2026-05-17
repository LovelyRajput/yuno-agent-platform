"""Tests for workflow execution (uses mocked agent runtime — no API calls)."""
from __future__ import annotations

import pytest

from app import models
from app.agents.workflow import execute_workflow, execute_single_agent


@pytest.mark.asyncio
async def test_workflow_executes_two_agents_in_order(mock_runtime, db):
    a1 = models.Agent(name="Step1", system_prompt="...")
    a2 = models.Agent(name="Step2", system_prompt="...")
    db.add_all([a1, a2]); db.commit(); db.refresh(a1); db.refresh(a2)

    wf = models.Workflow(
        name="two-step",
        graph={
            "start": "s1",
            "nodes": {
                "s1": {"agent_id": a1.id, "prompt_template": "{{input}}", "next": "s2"},
                "s2": {"agent_id": a2.id, "prompt_template": "{{input}}", "next": None},
            },
        },
    )
    db.add(wf); db.commit(); db.refresh(wf)

    run = await execute_workflow(db, wf, "hello")
    assert run.status == "completed"
    # The output should be the second agent's reply (chained from the first)
    assert "Step2" in run.output

    msgs = db.query(models.Message).filter_by(run_id=run.id).all()
    # At least: user input + 2 agent messages
    senders = [m.sender for m in msgs]
    assert "user" in senders
    agent_msgs = [m for m in msgs if m.sender == "agent"]
    assert len(agent_msgs) == 2


@pytest.mark.asyncio
async def test_single_agent_run_persists_messages(mock_runtime, db):
    agent = models.Agent(name="Solo", system_prompt="...")
    db.add(agent); db.commit(); db.refresh(agent)
    run = await execute_single_agent(db, agent, "ping")
    assert run.status == "completed"
    assert "Solo" in run.output
    msgs = db.query(models.Message).filter_by(run_id=run.id).all()
    assert any(m.sender == "user" for m in msgs)
    assert any(m.sender == "agent" for m in msgs)


@pytest.mark.asyncio
async def test_workflow_branches_on_output(mock_runtime, db):
    """Branch when the classifier output contains a keyword."""
    classifier = models.Agent(name="Classifier")
    branch_a = models.Agent(name="BranchA")
    branch_b = models.Agent(name="BranchB")
    db.add_all([classifier, branch_a, branch_b]); db.commit()
    for a in (classifier, branch_a, branch_b): db.refresh(a)

    wf = models.Workflow(
        name="branching",
        graph={
            "start": "classify",
            "nodes": {
                "classify": {
                    "agent_id": classifier.id,
                    "prompt_template": "{{input}}",
                    "next": "default",
                    "branches": [{"if_contains": "Classifier", "to": "alt"}],
                },
                "default": {"agent_id": branch_a.id, "prompt_template": "{{input}}", "next": None},
                "alt":     {"agent_id": branch_b.id, "prompt_template": "{{input}}", "next": None},
            },
        },
    )
    db.add(wf); db.commit(); db.refresh(wf)

    run = await execute_workflow(db, wf, "go")
    # Mocked classifier output includes "Classifier" so we should route to BranchB
    assert "BranchB" in run.output
