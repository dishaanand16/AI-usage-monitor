"""
Prompt capture endpoints.

POST /prompts   -> sanitize a raw prompt and store ONLY the sanitized
                   version + PII detection metadata. Raw text is never
                   persisted. Respects the asset's monitoring_enabled flag.
GET  /prompts    -> list/search sanitized prompts, optionally filtered
                   by asset.
GET  /prompts/pii-summary -> aggregate PII detection counts per asset
                   (the "which AI assets receive the most PII" governance
                   insight mentioned in the brief).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.models import AIAsset, Prompt, PIIDetection
from app.services.pii_sanitizer import sanitize_prompt

router = APIRouter()


class PromptIn(BaseModel):
    asset_id: uuid.UUID
    raw_text: str


class PromptOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    sanitized_text: str
    detections: dict

    class Config:
        from_attributes = True


@router.post("", response_model=PromptOut)
def capture_prompt(payload: PromptIn, db: Session = Depends(get_db)):
    asset = db.query(AIAsset).filter(AIAsset.id == payload.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="AI asset not found")

    if not asset.monitoring_enabled:
        # Respect the required "ability to enable or disable prompt
        # monitoring" toggle — we do not capture or store anything.
        raise HTTPException(
            status_code=403,
            detail="Monitoring is disabled for this asset; prompt was not captured.",
        )

    result = sanitize_prompt(payload.raw_text)

    prompt = Prompt(asset_id=asset.id, sanitized_text=result.sanitized_text)
    db.add(prompt)
    db.flush()  # get prompt.id before commit

    for entity_type, count in result.detections.items():
        db.add(PIIDetection(prompt_id=prompt.id, entity_type=entity_type, count=count))

    db.commit()
    db.refresh(prompt)

    return PromptOut(
        id=prompt.id,
        asset_id=prompt.asset_id,
        sanitized_text=prompt.sanitized_text,
        detections=result.detections,
    )


@router.get("")
def list_prompts(asset_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Prompt)
    if asset_id:
        query = query.filter(Prompt.asset_id == asset_id)
    prompts = query.order_by(Prompt.created_at.desc()).limit(100).all()

    out = []
    for p in prompts:
        detections = db.query(PIIDetection).filter(PIIDetection.prompt_id == p.id).all()
        out.append({
            "id": p.id,
            "asset_id": p.asset_id,
            "sanitized_text": p.sanitized_text,
            "created_at": p.created_at,
            "detections": {d.entity_type: d.count for d in detections},
        })
    return out


@router.get("/pii-summary")
def pii_summary(db: Session = Depends(get_db)):
    """Aggregate PII detection counts grouped by asset — surfaces which
    AI assets users most frequently submit personal information to."""
    rows = (
        db.query(
            AIAsset.name,
            PIIDetection.entity_type,
            func.sum(PIIDetection.count).label("total"),
        )
        .join(Prompt, Prompt.asset_id == AIAsset.id)
        .join(PIIDetection, PIIDetection.prompt_id == Prompt.id)
        .group_by(AIAsset.name, PIIDetection.entity_type)
        .all()
    )
    return [{"asset": r[0], "entity_type": r[1], "total": r[2]} for r in rows]