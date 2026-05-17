"""REST endpoints for browsing run history and messages."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=List[schemas.RunOut])
def list_runs(
    limit: int = Query(50, le=200),
    workflow_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Run).order_by(models.Run.id.desc())
    if workflow_id is not None:
        q = q.filter(models.Run.workflow_id == workflow_id)
    if agent_id is not None:
        q = q.filter(models.Run.agent_id == agent_id)
    return q.limit(limit).all()


@router.get("/{run_id}", response_model=schemas.RunDetailOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    messages = (
        db.query(models.Message)
        .filter_by(run_id=run_id)
        .order_by(models.Message.id.asc())
        .all()
    )
    detail = schemas.RunDetailOut.model_validate(run)
    detail.messages = [schemas.MessageOut.model_validate(m) for m in messages]
    return detail


@router.get("/{run_id}/messages", response_model=List[schemas.MessageOut])
def get_run_messages(run_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Message)
        .filter_by(run_id=run_id)
        .order_by(models.Message.id.asc())
        .all()
    )
