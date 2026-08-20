"""
Agent run endpoints.

POST /runs        -> execute the support agent for a given asset + query,
                     logging every tool it actually touched, then compute
                     and store the declared-vs-observed diff.
GET  /runs         -> list past runs with their declared/observed comparison.
GET  /runs/{id}    -> full detail for a single run.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import AIAsset, AgentRun, RunDataAccessEvent
from app.services.agent_runner import run_support_agent

router = APIRouter()


class RunIn(BaseModel):
    asset_id: uuid.UUID
    query: str


@router.post("")
def execute_run(payload: RunIn, db: Session = Depends(get_db)):
    asset = db.query(AIAsset).filter(AIAsset.id == payload.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="AI asset not found")

    run = AgentRun(asset_id=asset.id, status="running")
    db.add(run)
    db.flush()

    # Execute the agent — every tool it actually calls gets recorded as it
    # happens, not reconstructed afterward from logs.
    events = run_support_agent(payload.query)

    for source in events.tool_accesses:
        db.add(RunDataAccessEvent(run_id=run.id, source_name=source))

    run.status = "success"
    run.model = events.model
    run.input_tokens = events.input_tokens
    run.output_tokens = events.output_tokens

    db.commit()
    db.refresh(run)

    declared = set(asset.declared_data_sources)
    observed = set(events.tool_accesses)
    unexpected = observed - declared

    return {
        "run_id": run.id,
        "asset": asset.name,
        "declared_data_sources": sorted(declared),
        "observed_data_sources": sorted(observed),
        "unexpected_access": sorted(unexpected),
        "has_unexpected_access": len(unexpected) > 0,
        "model": run.model,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
    }


@router.get("")
def list_runs(asset_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(AgentRun)
    if asset_id:
        query = query.filter(AgentRun.asset_id == asset_id)
    runs = query.order_by(AgentRun.started_at.desc()).limit(50).all()

    out = []
    for run in runs:
        asset = db.query(AIAsset).filter(AIAsset.id == run.asset_id).first()
        events = db.query(RunDataAccessEvent).filter(RunDataAccessEvent.run_id == run.id).all()
        observed = set(e.source_name for e in events)
        declared = set(asset.declared_data_sources) if asset else set()
        unexpected = observed - declared

        out.append({
            "run_id": run.id,
            "asset": asset.name if asset else None,
            "started_at": run.started_at,
            "status": run.status,
            "declared_data_sources": sorted(declared),
            "observed_data_sources": sorted(observed),
            "unexpected_access": sorted(unexpected),
            "has_unexpected_access": len(unexpected) > 0,
            "model": run.model,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
        })
    return out