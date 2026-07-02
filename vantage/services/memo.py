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
from . import ai, scoring


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
            # Cited risks live in bull/bear above; this list carries only the
            # open questions (missing data) so the template does not repeat them.
            "risks": [f"Open question: {m}" for m in latest.missing_data],
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

    # When a live LLM is configured, draft richer narrative prose from the same
    # structured evidence. Structured fields remain the reliable fallback.
    provider = ai.get_provider()
    if isinstance(provider, ai.LiveLLMProvider):
        prose = provider.draft_memo_prose(_memo_context(memo, company, thesis, sig_objs))
        if prose:
            memo["narrative"] = prose
            memo["generated_by"] = provider.name
            if prose.get("overview"):
                memo["sections"]["overview"] = _as_text(prose["overview"])
            if prose.get("why_now"):
                memo["sections"]["why_now"] = _as_text(prose["why_now"])
            if prose.get("questions_for_founder"):
                memo["sections"]["questions_for_founder"] = _as_str_list(
                    prose["questions_for_founder"]) or memo["sections"]["questions_for_founder"]
            if prose.get("bull_summary"):
                memo["sections"]["bull_summary"] = _as_text(prose["bull_summary"])
            if prose.get("bear_summary"):
                memo["sections"]["bear_summary"] = _as_text(prose["bear_summary"])

    return memo


def _as_text(value) -> str:
    """Coerce an LLM field to display text. Models sometimes return a structured
    object (e.g. {"statement": ..., "drivers": [...]}) where a string was asked
    for; flatten it rather than stringifying a raw dict into the UI."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        head = value.get("statement") or value.get("summary") or value.get("text") or ""
        drivers = value.get("drivers") or value.get("points") or []
        if isinstance(drivers, list) and drivers:
            tail = " " + " ".join(str(d) for d in drivers)
            return (str(head) + tail).strip()
        return str(head).strip()
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def _as_str_list(value) -> list[str]:
    """Coerce an LLM field to a list of display strings."""
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(_as_text(item))
            else:
                out.append(str(item))
        return [s for s in out if s.strip()]
    if isinstance(value, str):
        return [value]
    return []


def _memo_context(memo: dict, company: models.Company, thesis: models.Thesis,
                  sig_objs: list) -> str:
    """Compact, factual context block for the memo-drafting LLM call."""
    bull = "\n".join(f"- {e.get('claim')} [{e.get('source')}]"
                     for e in memo["sections"]["bull_case"] if e.get("claim"))
    risk_lines = [f"- {e.get('claim')} [{e.get('source')}]"
                  for e in memo["sections"]["bear_case"] if e.get("claim")]
    risk_lines += [f"- {r}" for r in memo["sections"]["risks"]]
    risks = "\n".join(risk_lines) or "- none captured"
    sigs = "\n".join(f"- ({s.signal_kind}) {s.title}" for s in sig_objs[:12]) or "- none"
    s = memo["sections"]
    return (
        f"THESIS: {thesis.name}\n{thesis.description}\n\n"
        f"COMPANY: {company.name} ({company.domain})\n"
        f"{company.description}\nSectors: {', '.join(company.sectors or [])}\n\n"
        f"OVERALL SCORE: {memo['overall_score']}/100 ({memo['confidence']} confidence)\n"
        f"THESIS FIT: {s['thesis_fit']['score']}/100; "
        f"matched: {', '.join(s['thesis_fit']['matched_criteria']) or 'none'}\n"
        f"WHY NOW (heuristic): {s['why_now']}\n\n"
        f"POSITIVE EVIDENCE:\n{bull or '- none captured'}\n\n"
        f"RISKS / OPEN QUESTIONS:\n{risks}\n\n"
        f"SIGNAL TIMELINE:\n{sigs}\n\n"
        "Write the memo JSON now."
    )


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
    # Add clarifications for missing data, but skip anything already implicitly
    # covered by the standard questions above (revenue, retention, growth).
    covered = {"arr", "revenue", "retention", "growth", "churn", "margin"}
    for m in score.missing_data:
        if not any(term in m.lower() for term in covered):
            qs.append(f"Clarify: {m}")
        if len(qs) >= 7:
            break
    return qs
