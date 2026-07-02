"""Ingestion service: SourceConnector interface and connectors.

Each connector yields RawSignal dicts. The pipeline dedups (content_hash),
persists immutable Signal rows, extracts company mentions, resolves entities,
and links evidence. RSS is real/live; the seeded connector loads a curated,
realistic corpus so ingestion is deterministic and reproducible: mock the
scale, never the substance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from . import entity_resolution as er
from . import text


@dataclass
class RawSignal:
    title: str
    source_type: str
    source_name: str = ""
    source_url: str | None = None
    raw_text: str = ""
    signal_kind: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    company_description: str | None = None
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


class SourceConnector:
    name = "base"

    def fetch(self) -> list[RawSignal]:  # pragma: no cover - interface
        raise NotImplementedError


class RSSConnector(SourceConnector):
    """Live RSS/news connector (used when online). Best-effort, never fatal."""
    name = "rss"

    def __init__(self, url: str, source_name: str = "rss") -> None:
        self.url = url
        self.source_name = source_name

    def fetch(self) -> list[RawSignal]:
        try:
            import feedparser  # local import so offline demo needn't parse feeds
            feed = feedparser.parse(self.url)
        except Exception:
            return []
        out = []
        for e in feed.entries[:25]:
            out.append(RawSignal(
                title=getattr(e, "title", "")[:300],
                source_type="news", source_name=self.source_name,
                source_url=getattr(e, "link", None),
                raw_text=getattr(e, "summary", "")[:2000],
                signal_kind="news"))
        return out


class SeedConnector(SourceConnector):
    """Loads a curated realistic corpus from a list of RawSignal dicts."""
    name = "seed"

    def __init__(self, raw_signals: list[RawSignal]) -> None:
        self._signals = raw_signals

    def fetch(self) -> list[RawSignal]:
        return self._signals


# Pipeline
def ingest(db: Session, connector: SourceConnector) -> dict:
    """Run a connector end-to-end: dedup -> persist -> extract -> resolve -> link."""
    run = models.JobRun(job_type="ingest_source", entity_type="source",
                        entity_id=connector.name, status="running")
    db.add(run)
    db.flush()
    created_signals = created_companies = linked = duplicates = 0
    try:
        for raw in connector.fetch():
            chash = text.content_hash(raw.source_url, raw.title, raw.raw_text)
            if db.scalar(select(models.Signal).where(models.Signal.content_hash == chash)):
                duplicates += 1
                continue
            signal = models.Signal(
                source_type=raw.source_type, source_name=raw.source_name or connector.name,
                source_url=raw.source_url, title=raw.title, raw_text=raw.raw_text,
                signal_kind=raw.signal_kind, published_at=raw.published_at,
                content_hash=chash, signal_metadata=raw.metadata,
                processing_status="processed")
            db.add(signal)
            db.flush()
            created_signals += 1

            # Extraction: seeded signals carry an explicit company; RSS uses text.
            name = raw.company_name
            domain = raw.company_domain
            if not name and raw.raw_text:
                domain = domain or text.domain_from_text(raw.raw_text)
            if not name and not domain:
                signal.processing_status = "ignored"
                continue

            company, method, was_created = er.resolve_company(
                db, name=name or (domain or "Unknown"), domain=domain,
                context=f"{raw.title} {raw.raw_text}",
                description=raw.company_description or "")
            if was_created:
                created_companies += 1
                _enrich_from_signal(company, raw)
            elif raw.company_description and not company.description:
                _enrich_from_signal(company, raw)

            er.link_signal(db, signal, company, method,
                           evidence=raw.title, confidence=0.85 if domain else 0.7)
            linked += 1

            # Temporal ledger: record any numeric metric the signal carries.
            for mk in ("headcount", "open_roles", "eng_roles"):
                if mk in raw.metadata:
                    db.add(models.CompanyMetric(
                        company_id=company.id, metric_name=mk,
                        value=float(raw.metadata[mk]),
                        captured_at=raw.published_at or datetime.now(timezone.utc)))

        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.job_metadata = {"signals": created_signals, "companies": created_companies,
                            "linked": linked, "duplicates": duplicates}
        db.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    return {"signals": created_signals, "companies": created_companies,
            "linked": linked, "duplicates": duplicates}


def _enrich_from_signal(company: models.Company, raw: RawSignal) -> None:
    if raw.company_description and not company.description:
        company.description = raw.company_description
    meta = raw.metadata or {}
    if meta.get("sectors") and not company.sectors:
        company.sectors = meta["sectors"]
    if meta.get("business_model") and not company.business_model:
        company.business_model = meta["business_model"]
    if meta.get("hq_city") and not company.hq_city:
        company.hq_city = meta["hq_city"]
    if meta.get("employee_count") and company.employee_count is None:
        company.employee_count = meta["employee_count"]
    company.embedding = text.embed(f"{company.name} {company.description or ''} "
                                   f"{' '.join(company.sectors or [])}")
