"""Investment memo generation.

Assembles a first-pass memo from the canonical company graph: profile + latest
score + cited evidence + interactions. Every claim traces to a signal. Works
offline (heuristic composition); a live LLM would draft richer prose from the
same structured inputs.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from . import scoring


def generate_memo(db: Session, company: models.Company, thesis: models.Thesis) -> dict:
    latest = scoring.latest_scores_for_thesis(db, thesis.id).get(company.id)
    if latest is None:
        latest = scoring.score_company(db, company, thesis)

    signals = db.scalars(select(models.SignalCompany).where(
        models.SignalCompany.company_id == company.id)).all()
    sig_objs = [db.get(models.Signal, l.signal_id) for l in signals]
    sig_objs = [s for s in sig_objs if s]
    interactions = db.scalars(select(models.Interaction).where(
        models.Interaction.company_id == company.id
    ).order_by(models.Interaction.occurred_at.desc())).all()

    people = []
    for link in db.scalars(select(models.CompanyPerson).where(
            models.CompanyPerson.company_id == company.id)).all():
        p = db.get(models.Person, link.person_id)
        if p:
            people.append(f"{p.full_name} ({link.role or link.relationship_type})")

    def cite(ev: list[dict]) -> list[dict]:
        return [{"claim": e.get("claim"), "source": e.get("source"),
                 "url": e.get("url"), "weight": e.get("weight", "medium")} for e in ev]

    bull = cite(latest.positive_evidence)
    bear = cite(latest.negative_evidence)

    memo = {
        "company": company.name,
        "domain": company.domain,
        "thesis": thesis.name,
        "generated_by": latest.model_name,
        "prompt_version": get_settings().prompt_version,
        "recommendation": _recommendation(latest.overall_score, latest.confidence_label),
        "overall_score": latest.overall_score,
        "confidence": latest.confidence_label,
        "sections": {
            "overview": company.description or "No description on file; enrichment pending.",
            "thesis_fit": {
                "score": latest.fit_score,
                "matched_criteria": latest.matched_criteria,
                "explanation": latest.explanation,
            },
            "why_now": latest.why_now or "No acute catalyst detected.",
            "bull_case": bull or [{"claim": "Insufficient positive evidence captured yet."}],
            "bear_case": bear or [{"claim": "No material red flags captured yet."}],
            "traction": {"score": latest.traction_score,
                         "signals": [s.title for s in sig_objs
                                     if s.signal_kind in {"hiring", "funding", "traction", "launch"}][:6]},
            "team": {"score": latest.team_score, "people": people or ["Unknown; research needed."]},
            "risks": [e.get("claim") for e in latest.negative_evidence] +
                     [f"Open question: {m}" for m in latest.missing_data],
            "questions_for_founder": _founder_questions(company, latest),
            "recommended_next_action": latest.recommended_next_action,
        },
        "evidence_ledger": [
            {"id": s.id[:8], "kind": s.signal_kind, "title": s.title,
             "source": s.source_name or s.source_type, "url": s.source_url}
            for s in sig_objs
        ],
        "interactions": [
            {"type": i.interaction_type, "summary": i.summary,
             "sentiment": i.sentiment, "at": i.occurred_at.isoformat()}
            for i in interactions
        ],
    }
    return memo


def _recommendation(score: float, confidence: str) -> str:
    if score >= 72:
        return "PURSUE: prioritize outreach"
    if score >= 58:
        return "WATCH: add to pipeline, set alerts"
    if score >= 45:
        return "MONITOR: revisit on next catalyst"
    return "PASS for now: below thesis bar"


def _founder_questions(company: models.Company, score: models.CompanyScore) -> list[str]:
    qs = [
        "What is current ARR and last-12-months growth rate?",
        "Net revenue retention and gross margin?",
        "What share of revenue is top-10 customer concentration?",
    ]
    if "hiring" in (score.why_now or "").lower():
        qs.append("The recent GTM hiring: what is driving it, and is sales efficiency holding?")
    if score.deal_accessibility_score < 45:
        qs.append("What is the current cap-table situation and appetite for growth capital?")
    for m in score.missing_data[:2]:
        qs.append(f"Clarify: {m}")
    return qs
