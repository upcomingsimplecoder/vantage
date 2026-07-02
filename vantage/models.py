"""SQLAlchemy data model for Vantage: the canonical company graph.

Faithful to docs/03_TECH_SPEC.md, trimmed to what the Phase-0 demo exercises.
Everything attaches to the canonical Company entity. Raw signals are immutable;
AI judgments (scores, ai_outputs) are versioned, never overwritten.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Canonical target company
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sectors: Mapped[list] = mapped_column(JSON, default=list)
    business_model: Mapped[str | None] = mapped_column(String, nullable=True)
    hq_city: Mapped[str | None] = mapped_column(String, nullable=True)
    hq_country: Mapped[str | None] = mapped_column(String, nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Deal workflow state
    status: Mapped[str] = mapped_column(String, default="discovered", index=True)
    source_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    # Embedding stored as JSON list here; pgvector column in production.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    aliases = relationship("CompanyAlias", back_populates="company", cascade="all, delete-orphan")
    signal_links = relationship("SignalCompany", back_populates="company", cascade="all, delete-orphan")
    scores = relationship("CompanyScore", back_populates="company", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="company", cascade="all, delete-orphan")
    people_links = relationship("CompanyPerson", back_populates="company", cascade="all, delete-orphan")
    metrics = relationship("CompanyMetric", back_populates="company", cascade="all, delete-orphan")


class CompanyAlias(Base):
    __tablename__ = "company_aliases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    alias: Mapped[str] = mapped_column(String, index=True)
    alias_type: Mapped[str] = mapped_column(String)  # name|domain|social_handle|linkedin
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

    company = relationship("Company", back_populates="aliases")


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    prior_companies: Mapped[list] = mapped_column(JSON, default=list)

    company_links = relationship("CompanyPerson", back_populates="person")


class CompanyPerson(Base):
    __tablename__ = "company_people"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id"))
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    relationship_type: Mapped[str] = mapped_column(String, default="founder")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

    company = relationship("Company", back_populates="people_links")
    person = relationship("Person", back_populates="company_links")


# Immutable raw evidence
class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String)  # rss|news|github|job_post|web_page|manual|api
    source_name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    signal_kind: Mapped[str | None] = mapped_column(String, nullable=True)  # hiring|funding|launch|traction|exec_hire|news
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    content_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    signal_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    processing_status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company_links = relationship("SignalCompany", back_populates="signal", cascade="all, delete-orphan")


class SignalCompany(Base):
    __tablename__ = "signal_companies"
    __table_args__ = (UniqueConstraint("signal_id", "company_id", name="uq_signal_company"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    relation_type: Mapped[str] = mapped_column(String, default="about")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    resolver_method: Mapped[str] = mapped_column(String)  # domain_match|alias_match|name_match|llm_match|manual
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    signal = relationship("Signal", back_populates="company_links")
    company = relationship("Company", back_populates="signal_links")


# Investor mandate
class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    target_sectors: Mapped[list] = mapped_column(JSON, default=list)
    positive_keywords: Mapped[list] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[list] = mapped_column(JSON, default=list)
    stage_preference: Mapped[str | None] = mapped_column(String, nullable=True)
    geography_preference: Mapped[list] = mapped_column(JSON, default=list)
    revenue_band: Mapped[str | None] = mapped_column(String, nullable=True)
    scoring_config: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    scores = relationship("CompanyScore", back_populates="thesis", cascade="all, delete-orphan")


# Versioned AI judgment
class CompanyScore(Base):
    __tablename__ = "company_scores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    thesis_id: Mapped[str] = mapped_column(ForeignKey("theses.id"))
    overall_score: Mapped[float] = mapped_column(Float)
    fit_score: Mapped[float] = mapped_column(Float)
    traction_score: Mapped[float] = mapped_column(Float)
    timing_score: Mapped[float] = mapped_column(Float)
    team_score: Mapped[float] = mapped_column(Float)
    novelty_score: Mapped[float] = mapped_column(Float)
    deal_accessibility_score: Mapped[float] = mapped_column(Float, default=50.0)
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    confidence_label: Mapped[str] = mapped_column(String, default="medium")
    explanation: Mapped[str] = mapped_column(Text, default="")
    why_now: Mapped[str | None] = mapped_column(Text, nullable=True)
    positive_evidence: Mapped[list] = mapped_column(JSON, default=list)
    negative_evidence: Mapped[list] = mapped_column(JSON, default=list)
    missing_data: Mapped[list] = mapped_column(JSON, default=list)
    matched_criteria: Mapped[list] = mapped_column(JSON, default=list)
    recommended_next_action: Mapped[str | None] = mapped_column(String, nullable=True)
    model_name: Mapped[str] = mapped_column(String, default="heuristic")
    prompt_version: Mapped[str] = mapped_column(String, default="p0")
    formula_version: Mapped[str] = mapped_column(String, default="v1")
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    company = relationship("Company", back_populates="scores")
    thesis = relationship("Thesis", back_populates="scores")


# CRM
class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    interaction_type: Mapped[str] = mapped_column(String, default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="demo-user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    company = relationship("Company", back_populates="interactions")


# The moat table: temporal snapshots (velocity is the alpha)
class CompanyMetric(Base):
    __tablename__ = "company_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    metric_name: Mapped[str] = mapped_column(String)  # headcount|open_roles|eng_roles|traffic_proxy
    value: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    company = relationship("Company", back_populates="metrics")


# Production-credibility ledgers
class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class AIOutput(Base):
    """Anti-black-box ledger: every AI judgment stored as a versioned artifact."""
    __tablename__ = "ai_outputs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    task_type: Mapped[str] = mapped_column(String)  # extraction|enrichment|scoring|memo
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    input_hash: Mapped[str] = mapped_column(String)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
