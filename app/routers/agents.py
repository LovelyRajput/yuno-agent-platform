"""REST endpoints for agent CRUD + single-agent runs."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.agents.tools import available_tool_names
from app.agents.workflow import execute_single_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=List[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).order_by(models.Agent.id.desc()).all()


@router.post("", response_model=schemas.AgentOut, status_code=201)
def create_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    agent = models.Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/tools", response_model=List[str])
def list_available_tools():
    return available_tool_names()


@router.get("/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=schemas.AgentOut)
def update_agent(agent_id: int, payload: schemas.AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    db.delete(agent)
    db.commit()


@router.post("/{agent_id}/run", response_model=schemas.RunOut)
async def run_single_agent(
    agent_id: int,
    payload: schemas.RunRequest,
    db: Session = Depends(get_db),
):
    agent = db.query(models.Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    run = await execute_single_agent(db, agent, payload.input, trigger=payload.trigger)
    return run
