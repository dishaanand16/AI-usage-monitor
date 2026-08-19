"""
SQLAlchemy models mirroring backend/migrations/001_init.sql.

Kept intentionally simple (no ORM relationships/cascades beyond what's
needed) since the migration file is the source of truth for schema —
these models just give the FastAPI layer a typed way to read/write rows.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AIAsset(Base):
    __tablename__ = "ai_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    declared_data_sources = Column(ARRAY(String), nullable=False, default=list)
    monitoring_enabled = Column(Boolean, nullable=False, default=True)
    retention_days = Column(Integer, nullable=False, default=90)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("ai_assets.id"), nullable=False)
    sanitized_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class PIIDetection(Base):
    __tablename__ = "pii_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=1)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("ai_assets.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="running")
    model = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)


class RunDataAccessEvent(Base):
    __tablename__ = "run_data_access_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    source_name = Column(String, nullable=False)
    accessed_at = Column(DateTime(timezone=True), default=datetime.utcnow)