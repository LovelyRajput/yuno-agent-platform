"""REST endpoints for workflow CRUD + execution."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.agents.workflow import execute_workflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=List[schemas.WorkflowOut])
def list_workflows(db: Session = Depends(get_db)):
    return db.query(models.Workflow).order_by(models.Workflow.id.desc()).all()


@router.post("", response_model=schemas.WorkflowOut, status_code=201)
def create_workflow(payload: schemas.WorkflowCreate, db: Session = Depends(get_db)):
    wf = models.Workflow(**payload.model_dump())
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=schemas.WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter_by(id=workflow_id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=schemas.WorkflowOut)
def update_workflow(workflow_id: int, payload: schemas.WorkflowUpdate, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter_by(id=workflow_id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(wf, k, v)
    db.commit()
    db.refresh(wf)
    return wf


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.Workflow).filter_by(id=workflow_id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    db.delete(wf)
    db.commit()


@router.post("/{workflow_id}/run", response_model=schemas.RunOut)
async def run_workflow(
    workflow_id: int,
    payload: schemas.RunRequest,
    db: Session = Depends(get_db),
):
    wf = db.query(models.Workflow).filter_by(id=workflow_id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    run = await execute_workflow(db, wf, payload.input, trigger=payload.trigger)
    return run
