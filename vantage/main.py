"""Vantage: FastAPI app.

Exposes the JSON API surface (companies, theses, signals, scoring, CRM, jobs)
and serves a polished server-rendered UI (Deal Radar, Company Profile, Thesis
Manager, Pipeline). Zero external services; zero API keys by default.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .db import get_db, init_db
from .services import memo as memo_svc
from .services import scoring

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Vantage", description="AI deal-sourcing OS for growth investors", version="0.1.0")
templates = Jinja2Templates(directory=str(BASE / "templates"))
_static = BASE / "static"
_static.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


def asset_version() -> str:
    """Cache-busting token from the CSS mtime so browsers fetch fresh styles
    after every change/deploy. Cheap, deterministic, no build step."""
    try:
        return str(int((_static / "app.css").stat().st_mtime))
    except OSError:
        return "0"


# Expose to every template so <link>/<script> tags can append ?v=...
templates.env.globals["asset_version"] = asset_version

STAGES = ["discovered", "watching", "prioritized", "contacted",
          "meeting_scheduled", "diligence", "passed", "invested"]
STAGE_LABELS = {
    "discovered": "Discovered", "watching": "Watching", "prioritized": "Prioritized",
    "contacted": "Contacted", "meeting_scheduled": "Meeting", "diligence": "Diligence",
    "passed": "Passed", "invested": "Invested",
}


@app.on_event("startup")
def _startup() -> None:
    init_db()


# helpers
def _active_thesis(db: Session, thesis_id: str | None) -> models.Thesis | None:
    """Resolve the working thesis. A stale/invalid thesis_id (e.g. an old
    bookmark after a reseed) falls back to the default active thesis rather
    than silently returning None and gutting score-dependent panels."""
    if thesis_id:
        found = db.get(models.Thesis, thesis_id)
        if found:
            return found
    return db.scalars(select(models.Thesis).where(models.Thesis.active.is_(True))).first()


def _radar_rows(db: Session, thesis: models.Thesis, *, min_score: float = 0.0,
                sector: str | None = None, limit: int = 100) -> list[dict]:
    latest = scoring.latest_scores_for_thesis(db, thesis.id)
    rows = []
    for company_id, score in latest.items():
        if score.overall_score < min_score:
            continue
        company = db.get(models.Company, company_id)
        if not company:
            continue
        if sector and sector.lower() not in [s.lower() for s in (company.sectors or [])]:
            continue
        rows.append({"company": company, "score": score,
                     "signal_count": len(company.signal_links)})
    rows.sort(key=lambda r: r["score"].overall_score, reverse=True)
    return rows[:limit]


def _score_color(v: float) -> str:
    return "hot" if v >= 70 else "warm" if v >= 55 else "cool"


# UI ROUTES
@app.get("/", response_class=HTMLResponse)
def deal_radar(request: Request, thesis_id: str | None = None,
               min_score: float = 0.0, sector: str | None = None,
               db: Session = Depends(get_db)):
    theses = db.scalars(select(models.Thesis).order_by(models.Thesis.created_at)).all()
    if not theses:
        return templates.TemplateResponse("empty.html", {"request": request,
                                          "settings": get_settings()})
    thesis = _active_thesis(db, thesis_id) or theses[0]
    rows = _radar_rows(db, thesis, min_score=min_score, sector=sector)
    # Digest line
    fresh = [r for r in rows if r["score"].overall_score >= 55]
    movers = [r for r in rows if any("momentum" in (e.get("claim", "").lower())
              for e in r["score"].positive_evidence)]
    followups = db.scalar(select(func.count()).select_from(models.Interaction)) or 0
    return templates.TemplateResponse("radar.html", {
        "request": request, "theses": theses, "thesis": thesis, "rows": rows,
        "digest": {"matches": len(fresh), "movers": len(movers), "followups": followups},
        "min_score": min_score, "sector": sector or "",
        "score_color": _score_color, "stage_labels": STAGE_LABELS,
        "settings": get_settings()})


@app.get("/companies/{company_id}", response_class=HTMLResponse)
def company_profile(company_id: str, request: Request, thesis_id: str | None = None,
                    db: Session = Depends(get_db)):
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(404, "company not found")
    thesis = _active_thesis(db, thesis_id)
    score = None
    if thesis:
        score = scoring.latest_scores_for_thesis(db, thesis.id).get(company_id)
        if score is None:  # self-heal: score on demand if this pair was never computed
            score = scoring.score_company(db, company, thesis)
    signals = sorted(
        [s for s in (db.get(models.Signal, l.signal_id) for l in company.signal_links) if s],
        key=lambda s: (s.published_at or s.discovered_at), reverse=True)
    people = []
    for link in company.people_links:
        p = db.get(models.Person, link.person_id)
        if p:
            people.append({"name": p.full_name, "title": p.title or link.role})
    interactions = sorted(company.interactions, key=lambda i: i.occurred_at, reverse=True)
    history = db.scalars(select(models.CompanyScore).where(
        models.CompanyScore.company_id == company_id,
        models.CompanyScore.thesis_id == (thesis.id if thesis else "")
    ).order_by(models.CompanyScore.scored_at.desc())).all()
    return templates.TemplateResponse("company.html", {
        "request": request, "company": company, "thesis": thesis, "score": score,
        "signals": [s for s in signals if s], "people": people,
        "interactions": interactions, "history": history,
        "theses": db.scalars(select(models.Thesis)).all(),
        "stages": STAGES, "stage_labels": STAGE_LABELS,
        "score_color": _score_color, "settings": get_settings()})


@app.get("/theses", response_class=HTMLResponse)
def theses_page(request: Request, db: Session = Depends(get_db)):
    theses = db.scalars(select(models.Thesis).order_by(models.Thesis.created_at)).all()
    counts = {}
    for t in theses:
        counts[t.id] = len(scoring.latest_scores_for_thesis(db, t.id))
    return templates.TemplateResponse("theses.html", {
        "request": request, "theses": theses, "counts": counts,
        "settings": get_settings()})


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request, thesis_id: str | None = None,
                  db: Session = Depends(get_db)):
    thesis = _active_thesis(db, thesis_id)
    latest = scoring.latest_scores_for_thesis(db, thesis.id) if thesis else {}
    board = {s: [] for s in STAGES}
    for company in db.scalars(select(models.Company)).all():
        board.setdefault(company.status, []).append({
            "company": company, "score": latest.get(company.id)})
    for s in board:
        board[s].sort(key=lambda r: (r["score"].overall_score if r["score"] else 0), reverse=True)
    return templates.TemplateResponse("pipeline.html", {
        "request": request, "board": board, "stages": STAGES,
        "stage_labels": STAGE_LABELS, "thesis": thesis,
        "theses": db.scalars(select(models.Thesis)).all(),
        "score_color": _score_color, "settings": get_settings()})


@app.get("/companies/{company_id}/memo", response_class=HTMLResponse)
def memo_page(company_id: str, request: Request, thesis_id: str | None = None,
              db: Session = Depends(get_db)):
    company = db.get(models.Company, company_id)
    thesis = _active_thesis(db, thesis_id)
    if not company or not thesis:
        raise HTTPException(404, "not found")
    m = memo_svc.generate_memo(db, company, thesis)
    return templates.TemplateResponse("memo.html", {
        "request": request, "memo": m, "company": company, "thesis": thesis,
        "settings": get_settings()})


# UI form actions
@app.post("/companies/{company_id}/status")
def set_status(company_id: str, status: str = Form(...), thesis_id: str = Form(""),
               db: Session = Depends(get_db)):
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(404)
    company.status = status
    db.add(models.Interaction(company_id=company_id, interaction_type="status_change",
                              summary=f"Moved to {STAGE_LABELS.get(status, status)}"))
    db.commit()
    ref = f"/companies/{company_id}" + (f"?thesis_id={thesis_id}" if thesis_id else "")
    return RedirectResponse(ref, status_code=303)


@app.post("/companies/{company_id}/notes")
def add_note(company_id: str, summary: str = Form(...), sentiment: str = Form("neutral"),
             thesis_id: str = Form(""), db: Session = Depends(get_db)):
    company = db.get(models.Company, company_id)
    if not company:
        raise HTTPException(404)
    db.add(models.Interaction(company_id=company_id, interaction_type="note",
                              summary=summary, sentiment=sentiment))
    db.commit()
    # Re-score so the note visibly feeds the loop
    thesis = _active_thesis(db, thesis_id or None)
    if thesis:
        scoring.score_company(db, company, thesis)
    ref = f"/companies/{company_id}" + (f"?thesis_id={thesis_id}" if thesis_id else "")
    return RedirectResponse(ref, status_code=303)


# JSON API
@app.get("/api/health")
def health():
    return {"status": "ok", "ai_mode": get_settings().ai_mode}


@app.get("/api/companies")
def api_companies(thesis_id: str | None = None, min_score: float = 0.0,
                  status: str | None = None, db: Session = Depends(get_db)):
    thesis = _active_thesis(db, thesis_id)
    if not thesis:
        return {"companies": []}
    rows = _radar_rows(db, thesis, min_score=min_score)
    out = []
    for r in rows:
        c, s = r["company"], r["score"]
        if status and c.status != status:
            continue
        out.append({
            "id": c.id, "name": c.name, "domain": c.domain, "status": c.status,
            "sectors": c.sectors, "overall_score": s.overall_score,
            "confidence": s.confidence_label, "why_now": s.why_now,
            "recommended_next_action": s.recommended_next_action,
            "signal_count": r["signal_count"]})
    return {"thesis": thesis.name, "count": len(out), "companies": out}


@app.get("/api/companies/{company_id}")
def api_company(company_id: str, thesis_id: str | None = None, db: Session = Depends(get_db)):
    c = db.get(models.Company, company_id)
    if not c:
        raise HTTPException(404)
    thesis = _active_thesis(db, thesis_id)
    s = scoring.latest_scores_for_thesis(db, thesis.id).get(company_id) if thesis else None
    return {
        "id": c.id, "name": c.name, "domain": c.domain, "description": c.description,
        "sectors": c.sectors, "status": c.status, "employee_count": c.employee_count,
        "score": None if not s else {
            "overall": s.overall_score, "fit": s.fit_score, "traction": s.traction_score,
            "timing": s.timing_score, "team": s.team_score, "novelty": s.novelty_score,
            "deal_accessibility": s.deal_accessibility_score, "risk": s.risk_score,
            "confidence": s.confidence, "confidence_label": s.confidence_label,
            "why_now": s.why_now, "explanation": s.explanation,
            "positive_evidence": s.positive_evidence, "negative_evidence": s.negative_evidence,
            "missing_data": s.missing_data, "matched_criteria": s.matched_criteria,
            "recommended_next_action": s.recommended_next_action,
            "model": s.model_name, "prompt_version": s.prompt_version,
            "formula_version": s.formula_version, "scored_at": s.scored_at.isoformat()},
        "signals": [{"id": sig.id[:8], "title": sig.title, "kind": sig.signal_kind,
                     "resolver": l.resolver_method}
                    for l, sig in ((l, db.get(models.Signal, l.signal_id))
                                   for l in c.signal_links) if sig],
    }


@app.get("/api/companies/{company_id}/memo")
def api_memo(company_id: str, thesis_id: str | None = None, db: Session = Depends(get_db)):
    c = db.get(models.Company, company_id)
    thesis = _active_thesis(db, thesis_id)
    if not c or not thesis:
        raise HTTPException(404)
    return memo_svc.generate_memo(db, c, thesis)


@app.get("/api/theses")
def api_theses(db: Session = Depends(get_db)):
    return {"theses": [{"id": t.id, "name": t.name, "description": t.description,
                        "target_sectors": t.target_sectors, "active": t.active}
                       for t in db.scalars(select(models.Thesis)).all()]}


@app.post("/api/scoring/run")
def api_run_scoring(thesis_id: str | None = None, db: Session = Depends(get_db)):
    thesis = _active_thesis(db, thesis_id)
    if not thesis:
        raise HTTPException(404, "no thesis")
    n = 0
    for company in db.scalars(select(models.Company)).all():
        scoring.score_company(db, company, thesis)
        n += 1
    return {"thesis": thesis.name, "scored": n}


@app.get("/api/jobs")
def api_jobs(limit: int = 20, db: Session = Depends(get_db)):
    runs = db.scalars(select(models.JobRun).order_by(
        models.JobRun.started_at.desc()).limit(limit)).all()
    return {"jobs": [{"type": r.job_type, "status": r.status, "entity": r.entity_id,
                      "metadata": r.job_metadata, "error": r.error} for r in runs]}


@app.get("/api/ai-outputs")
def api_ai_outputs(limit: int = 20, db: Session = Depends(get_db)):
    """The anti-black-box ledger: every AI judgment, versioned and auditable."""
    rows = db.scalars(select(models.AIOutput).order_by(
        models.AIOutput.created_at.desc()).limit(limit)).all()
    return {"ai_outputs": [{"task": r.task_type, "model": r.model,
                            "prompt_version": r.prompt_version, "input_hash": r.input_hash,
                            "confidence": r.confidence, "output": r.output_json}
                           for r in rows]}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api"):
        return JSONResponse({"error": "not found"}, status_code=404)
    return HTMLResponse("<h1>404</h1><a href='/'>← Back to Deal Radar</a>", status_code=404)
