"""Scoring service: owns the deterministic aggregation formula.

The AI provider proposes evidence-cited sub-scores; this module combines them
with a versioned, auditable weighted formula and persists a NEW score version
(never overwrites). It also writes the ai_outputs ledger row and a job_run.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from . import ai

# Deterministic weights (formula v1). Documented in the tech spec.
WEIGHTS = {
    "fit": 0.30, "traction": 0.20, "timing": 0.15,
    "team": 0.15, "novelty": 0.10, "deal_accessibility": 0.10,
}
RISK_WEIGHT = 0.15  # subtracted


def compute_overall(j: ai.Judgment) -> float:
    base = (
        WEIGHTS["fit"] * j.fit_score
        + WEIGHTS["traction"] * j.traction_score
        + WEIGHTS["timing"] * j.timing_score
        + WEIGHTS["team"] * j.team_score
        + WEIGHTS["novelty"] * j.novelty_score
        + WEIGHTS["deal_accessibility"] * j.deal_accessibility_score
    )
    overall = base - RISK_WEIGHT * j.risk_score
    return round(max(0.0, min(100.0, overall)), 1)


def score_company(db: Session, company: models.Company, thesis: models.Thesis) -> models.CompanyScore:
    settings = get_settings()
    provider = ai.get_provider()
    run = models.JobRun(job_type="score_company", entity_type="company",
                        entity_id=company.id, status="running")
    db.add(run)
    db.flush()
    try:
        signals = _signals_for(db, company)
        interactions = [
            {"summary": i.summary, "sentiment": i.sentiment}
            for i in db.scalars(select(models.Interaction).where(
                models.Interaction.company_id == company.id)).all()
        ]
        company_d = {
            "id": company.id, "name": company.name, "domain": company.domain,
            "description": company.description, "sectors": company.sectors or [],
            "business_model": company.business_model,
            "employee_count": company.employee_count,
        }
        thesis_d = {
            "name": thesis.name, "description": thesis.description,
            "target_sectors": thesis.target_sectors or [],
            "positive_keywords": thesis.positive_keywords or [],
            "negative_keywords": thesis.negative_keywords or [],
        }
        judgment = provider.score(company_d, thesis_d, signals, interactions)
        overall = compute_overall(judgment)

        score = models.CompanyScore(
            company_id=company.id, thesis_id=thesis.id, overall_score=overall,
            fit_score=judgment.fit_score, traction_score=judgment.traction_score,
            timing_score=judgment.timing_score, team_score=judgment.team_score,
            novelty_score=judgment.novelty_score,
            deal_accessibility_score=judgment.deal_accessibility_score,
            risk_score=judgment.risk_score, confidence=judgment.confidence,
            confidence_label=judgment.confidence_label,
            explanation=judgment.explanation, why_now=judgment.why_now,
            positive_evidence=judgment.positive_evidence,
            negative_evidence=judgment.negative_evidence,
            missing_data=judgment.missing_data,
            matched_criteria=judgment.matched_criteria,
            recommended_next_action=judgment.recommended_next_action,
            model_name=judgment.model_name, prompt_version=settings.prompt_version,
            formula_version=settings.score_formula_version,
        )
        db.add(score)
        db.flush()

        db.add(models.AIOutput(
            entity_type="company", entity_id=company.id, task_type="scoring",
            model=judgment.model_name, prompt_version=settings.prompt_version,
            input_hash=ai.input_hash(company.id, thesis.id, str(len(signals))),
            output_json={
                "overall": overall, "sub_scores": {
                    "fit": judgment.fit_score, "traction": judgment.traction_score,
                    "timing": judgment.timing_score, "team": judgment.team_score,
                    "novelty": judgment.novelty_score,
                    "deal_accessibility": judgment.deal_accessibility_score,
                    "risk": judgment.risk_score},
                "evidence_count": len(judgment.positive_evidence) + len(judgment.negative_evidence),
            },
            confidence=judgment.confidence))

        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.job_metadata = {"overall": overall, "signals": len(signals)}
        db.commit()
        db.refresh(score)
        return score
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


def latest_scores_for_thesis(db: Session, thesis_id: str) -> dict[str, models.CompanyScore]:
    """Most-recent score per company for a thesis (versioned history collapsed)."""
    rows = db.scalars(select(models.CompanyScore).where(
        models.CompanyScore.thesis_id == thesis_id
    ).order_by(models.CompanyScore.scored_at.desc())).all()
    latest: dict[str, models.CompanyScore] = {}
    for s in rows:
        latest.setdefault(s.company_id, s)
    return latest


def _signals_for(db: Session, company: models.Company) -> list[dict]:
    links = db.scalars(select(models.SignalCompany).where(
        models.SignalCompany.company_id == company.id)).all()
    out = []
    for link in links:
        s = db.get(models.Signal, link.signal_id)
        if s:
            out.append({
                "id": s.id, "title": s.title, "signal_kind": s.signal_kind,
                "source_type": s.source_type, "source_name": s.source_name,
                "source_url": s.source_url, "published_at": s.published_at,
            })
    return out
