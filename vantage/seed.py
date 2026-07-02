"""Seed orchestrator: build the dataset deterministically.

Idempotent-ish: drops and recreates for a clean demo. Loads theses, runs the
seed corpus through the REAL ingestion pipeline, attaches people, then scores
every company against every active thesis.
"""
from __future__ import annotations

from sqlalchemy import select

from . import models, seed_data
from .db import Base, SessionLocal, engine, init_db
from .services import scoring
from .services.ingestion import SeedConnector, ingest
from .services.text import normalize_name


def seed(reset: bool = True) -> dict:
    if reset:
        Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        # Theses
        for t in seed_data.THESES:
            db.add(models.Thesis(
                name=t["name"], description=t["description"],
                target_sectors=t["target_sectors"],
                positive_keywords=t["positive_keywords"],
                negative_keywords=t["negative_keywords"],
                stage_preference=t.get("stage_preference"),
                geography_preference=t.get("geography_preference", []),
                revenue_band=t.get("revenue_band")))
        db.commit()

        # Ingest the curated corpus through the real pipeline
        stats = ingest(db, SeedConnector(seed_data.build_seed_signals()))

        # Attach people to their resolved companies
        for cname, people in seed_data.PEOPLE.items():
            company = db.scalar(select(models.Company).where(
                models.Company.normalized_name == normalize_name(cname)))
            if not company:
                continue
            for full_name, title, rel in people:
                person = models.Person(full_name=full_name,
                                       normalized_name=normalize_name(full_name),
                                       title=title)
                db.add(person)
                db.flush()
                db.add(models.CompanyPerson(company_id=company.id, person_id=person.id,
                                            role=title, relationship_type=rel))
        db.commit()

        # Score every company against every active thesis
        theses = db.scalars(select(models.Thesis).where(models.Thesis.active.is_(True))).all()
        companies = db.scalars(select(models.Company)).all()
        scored = 0
        for thesis in theses:
            for company in companies:
                scoring.score_company(db, company, thesis)
                scored += 1

        # Apply a realistic starting pipeline state (stages + a few notes), as if
        # the firm has worked the top of the list for a few weeks. This runs AFTER
        # scoring so it is purely presentational and never shifts a score.
        from datetime import timedelta, timezone
        from datetime import datetime as _dt
        now = _dt.now(timezone.utc)
        staged = notes_added = 0
        for cname, state in seed_data.PIPELINE_STATE.items():
            company = db.scalar(select(models.Company).where(
                models.Company.normalized_name == normalize_name(cname)))
            if not company:
                continue
            company.status = state["stage"]
            staged += 1
            for days_ago, sentiment, summary in state.get("notes", []):
                db.add(models.Interaction(
                    company_id=company.id, interaction_type="note",
                    summary=summary, sentiment=sentiment,
                    occurred_at=now - timedelta(days=days_ago)))
                notes_added += 1
        db.commit()

        return {**stats, "theses": len(theses), "companies_total": len(companies),
                "scores": scored, "staged": staged, "notes": notes_added}
    finally:
        db.close()


if __name__ == "__main__":
    import json
    print(json.dumps(seed(), indent=2))
