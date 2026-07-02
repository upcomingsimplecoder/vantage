"""Entity resolution: the layered, precision-biased cascade.

Given an extracted company mention (name + optional domain + context), find the
canonical Company or create one. Bias: better a possible duplicate (reviewable)
than corrupting a canonical profile with wrong evidence.

Cascade:  domain -> alias -> exact normalized name -> fuzzy name -> embedding -> create
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from . import text

FUZZY_THRESHOLD = 0.86      # accept as same entity above this
EMBED_THRESHOLD = 0.82      # semantic backstop


def resolve_company(
    db: Session, *, name: str, domain: str | None = None,
    context: str = "", description: str = "",
) -> tuple[models.Company, str, bool]:
    """Return (company, resolver_method, created)."""
    dom = text.canonical_domain(domain) or text.domain_from_text(context)
    norm = text.normalize_name(name)

    # 1) domain (the strongest key)
    if dom:
        hit = db.scalar(select(models.Company).where(models.Company.domain == dom))
        if hit:
            return hit, "domain_match", False

    # 2) alias table
    if dom:
        alias = db.scalar(select(models.CompanyAlias).where(models.CompanyAlias.alias == dom))
        if alias:
            return alias.company, "alias_match", False
    if norm:
        alias = db.scalar(select(models.CompanyAlias).where(models.CompanyAlias.alias == norm))
        if alias:
            return alias.company, "alias_match", False

    # 3) exact normalized-name match
    if norm:
        hit = db.scalar(select(models.Company).where(models.Company.normalized_name == norm))
        if hit:
            if dom and not hit.domain:  # enrich canonical with newly-learned domain
                hit.domain = dom
                _add_alias(db, hit, dom, "domain")
            return hit, "name_match", False

    # 4) fuzzy name + 5) embedding backstop (scan is fine at prototype scale)
    candidates = db.scalars(select(models.Company)).all()
    best, best_score, method = None, 0.0, ""
    q_emb = text.embed(f"{name} {description} {context}")
    for c in candidates:
        s = text.similarity(name, c.name)
        if s > best_score:
            best, best_score, method = c, s, "fuzzy_name_match"
    if best and best_score >= FUZZY_THRESHOLD:
        if dom and not best.domain:
            best.domain = dom
            _add_alias(db, best, dom, "domain")
        return best, method, False

    # embedding backstop for renamed/rephrased entities
    best, best_emb = None, 0.0
    for c in candidates:
        if c.embedding:
            e = text.cosine(q_emb, c.embedding)
            if e > best_emb:
                best, best_emb = c, e
    if best and best_emb >= EMBED_THRESHOLD:
        return best, "embedding_match", False

    # 6) create new canonical company
    company = models.Company(
        name=name.strip(), normalized_name=norm, domain=dom,
        website_url=(f"https://{dom}" if dom else None),
        description=description or None,
        embedding=text.embed(f"{name} {description}"),
        source_confidence=0.6 if dom else 0.4,
    )
    db.add(company)
    db.flush()
    _add_alias(db, company, norm, "name")
    if dom:
        _add_alias(db, company, dom, "domain")
    return company, "created", True


def link_signal(db: Session, signal: models.Signal, company: models.Company,
                method: str, *, relation: str = "about", confidence: float = 0.8,
                evidence: str | None = None) -> None:
    exists = db.scalar(select(models.SignalCompany).where(
        models.SignalCompany.signal_id == signal.id,
        models.SignalCompany.company_id == company.id))
    if exists:
        return
    db.add(models.SignalCompany(
        signal_id=signal.id, company_id=company.id, relation_type=relation,
        confidence=confidence, resolver_method=method,
        evidence=evidence or (signal.title[:200] if signal.title else None)))


def _add_alias(db: Session, company: models.Company, alias: str, alias_type: str) -> None:
    if not alias:
        return
    dup = db.scalar(select(models.CompanyAlias).where(
        models.CompanyAlias.company_id == company.id,
        models.CompanyAlias.alias == alias))
    if not dup:
        db.add(models.CompanyAlias(company_id=company.id, alias=alias, alias_type=alias_type))
