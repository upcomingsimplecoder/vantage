"""AI provider abstraction.

Two providers behind one interface:
  - HeuristicProvider: deterministic, offline, no API key. Produces real
    evidence-cited scores from signal features.
  - LiveLLMProvider: calls OpenAI/Anthropic when a key is configured.

Design rule: the LLM (or heuristic) proposes structured sub-scores plus
evidence; the backend owns the deterministic aggregation formula (see
scoring.py). No score without cited evidence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from ..config import get_settings
from . import text


@dataclass
class Judgment:
    """Structured output of a scoring pass; mirrors the LLM JSON contract."""
    fit_score: float
    traction_score: float
    timing_score: float
    team_score: float
    novelty_score: float
    deal_accessibility_score: float
    risk_score: float
    confidence: float
    confidence_label: str
    explanation: str
    why_now: str
    positive_evidence: list[dict] = field(default_factory=list)
    negative_evidence: list[dict] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    matched_criteria: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    model_name: str = "heuristic"


# Signal-kind -> which sub-scores it lifts, and a human phrasing.
_KIND_WEIGHTS = {
    "funding":    {"traction": 12, "timing": 10, "novelty": 3},
    "hiring":     {"traction": 14, "timing": 12},
    "exec_hire":  {"team": 16, "timing": 14, "traction": 4},
    "launch":     {"novelty": 12, "traction": 8, "timing": 6},
    "traction":   {"traction": 16, "timing": 6},
    "news":       {"timing": 5, "novelty": 2},
}


class HeuristicProvider:
    """Deterministic scorer. Real logic over real signal features, not random."""

    name = "heuristic"

    def score(self, company: dict, thesis: dict, signals: list[dict],
              interactions: list[dict]) -> Judgment:
        pos: list[dict] = []
        neg: list[dict] = []
        matched: list[str] = []
        missing: list[str] = []

        # Fit: semantic + keyword overlap between company and thesis
        c_text = " ".join(filter(None, [
            company.get("name", ""), company.get("description", ""),
            company.get("business_model", ""), " ".join(company.get("sectors", []))]))
        t_text = " ".join(filter(None, [
            thesis.get("name", ""), thesis.get("description", ""),
            " ".join(thesis.get("target_sectors", [])),
            " ".join(thesis.get("positive_keywords", []))]))
        sem = text.cosine(text.embed(c_text), text.embed(t_text))  # 0..1

        pos_kw = [k for k in thesis.get("positive_keywords", [])
                  if k.lower() in c_text.lower()]
        neg_kw = [k for k in thesis.get("negative_keywords", [])
                  if k.lower() in c_text.lower()]
        sector_hit = [s for s in thesis.get("target_sectors", [])
                      if s.lower() in (x.lower() for x in company.get("sectors", []))]

        fit = 38 + sem * 45 + len(pos_kw) * 6 + len(sector_hit) * 7 - len(neg_kw) * 18
        fit = _clamp(fit)
        for k in pos_kw:
            matched.append(f"Thesis keyword matched: '{k}'")
            pos.append({"claim": f"Matches thesis keyword '{k}'", "weight": "medium",
                        "source": "company profile"})
        for s in sector_hit:
            matched.append(f"Target sector: {s}")
        for k in neg_kw:
            neg.append({"claim": f"Contains exclusion keyword '{k}'", "weight": "high",
                        "source": "company profile"})

        # Traction / timing / team / novelty from signals
        traction, timing, team, novelty = 42.0, 40.0, 45.0, 45.0
        recent_kinds: list[str] = []
        for sig in signals:
            kind = sig.get("signal_kind") or "news"
            recent_kinds.append(kind)
            w = _KIND_WEIGHTS.get(kind, {})
            traction += w.get("traction", 0)
            timing += w.get("timing", 0)
            team += w.get("team", 0)
            novelty += w.get("novelty", 0)
            if kind in {"funding", "hiring", "exec_hire", "launch", "traction"}:
                pos.append({
                    "claim": _signal_claim(kind, sig),
                    "weight": "high" if kind in {"exec_hire", "funding", "traction"} else "medium",
                    "source": sig.get("source_name") or sig.get("source_type"),
                    "signal_id": sig.get("id"),
                    "url": sig.get("source_url"),
                })

        # Velocity bonus: multiple hiring signals indicate momentum
        hiring_ct = recent_kinds.count("hiring")
        if hiring_ct >= 2:
            timing += 8
            traction += 6
            pos.append({"claim": f"Hiring momentum: {hiring_ct} recent hiring signals",
                        "weight": "high", "source": "temporal ledger"})

        traction, timing, team, novelty = map(_clamp, (traction, timing, team, novelty))

        # Deal accessibility & risk
        deal_access = 55.0
        if any(k == "funding" for k in recent_kinds):
            deal_access -= 20  # just raised, may be unavailable or pricey
            neg.append({"claim": "Recent funding may reduce deal availability / raise price",
                        "weight": "medium", "source": "signals"})
        risk = 30.0
        if len(neg_kw):
            risk += 22
        if not company.get("description"):
            risk += 8
            missing.append("No company description on file")
        if company.get("employee_count") is None:
            missing.append("Employee count unknown (revenue proxy)")
        if not any(k in recent_kinds for k in ("traction", "funding", "hiring")):
            missing.append("No hard traction signal yet")
            risk += 6
        deal_access, risk = _clamp(deal_access), _clamp(risk)

        # Confidence: driven by evidence volume & data completeness
        evidence_ct = len(pos) + len(neg)
        completeness = 1.0 - min(1.0, len(missing) * 0.2)
        confidence = _clamp((min(evidence_ct, 6) / 6 * 55) + completeness * 45) / 100
        conf_label = ("high" if confidence >= 0.7 else
                      "medium" if confidence >= 0.45 else "low")

        why_now = _why_now(recent_kinds, hiring_ct, sector_hit, thesis)
        next_action = _next_action(fit, traction, deal_access, bool(interactions))
        explanation = (
            f"Fit {fit:.0f} (semantic {sem:.2f}, {len(pos_kw)} kw, {len(sector_hit)} sector); "
            f"traction {traction:.0f}, timing {timing:.0f}, team {team:.0f} from "
            f"{len(signals)} signals; risk {risk:.0f}; deal access {deal_access:.0f}.")

        return Judgment(
            fit_score=fit, traction_score=traction, timing_score=timing,
            team_score=team, novelty_score=novelty,
            deal_accessibility_score=deal_access, risk_score=risk,
            confidence=round(confidence, 2), confidence_label=conf_label,
            explanation=explanation, why_now=why_now,
            positive_evidence=pos[:8], negative_evidence=neg[:6],
            missing_data=missing, matched_criteria=matched,
            recommended_next_action=next_action, model_name="heuristic")


class LiveLLMProvider:
    """Calls a real LLM. Used only when VANTAGE_LLM_PROVIDER + key are set.

    Falls back to the heuristic provider on any error.
    """

    def __init__(self, settings) -> None:
        self.settings = settings
        self.name = f"{settings.llm_provider}:{settings.llm_model}"
        self._fallback = HeuristicProvider()

    def score(self, company, thesis, signals, interactions) -> Judgment:
        try:
            return self._call(company, thesis, signals, interactions)
        except Exception as exc:  # noqa: BLE001
            j = self._fallback.score(company, thesis, signals, interactions)
            j.explanation = f"[LLM fallback: {exc}] " + j.explanation
            return j

    def _call(self, company, thesis, signals, interactions) -> Judgment:
        import httpx  # local import; only needed on the live path

        prompt = _build_scoring_prompt(company, thesis, signals)
        if self.settings.llm_provider == "openai":
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json={"model": self.settings.llm_model,
                      "messages": [{"role": "system", "content": _SYSTEM_PROMPT},
                                   {"role": "user", "content": prompt}],
                      "response_format": {"type": "json_object"}, "temperature": 0.2},
                timeout=60)
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
        else:
            raise RuntimeError(f"provider {self.settings.llm_provider} not wired in prototype")
        return _judgment_from_json(data, self.name)


def get_provider():
    s = get_settings()
    if s.llm_provider in {"openai", "anthropic"} and s.llm_api_key:
        return LiveLLMProvider(s)
    return HeuristicProvider()


def input_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# helpers
def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(max(lo, min(hi, x)), 1)


def _signal_claim(kind: str, sig: dict) -> str:
    title = (sig.get("title") or "").strip()
    return {
        "funding":   f"Funding signal: {title}",
        "hiring":    f"Hiring signal: {title}",
        "exec_hire": f"Executive hire: {title}",
        "launch":    f"Product launch: {title}",
        "traction":  f"Traction: {title}",
    }.get(kind, title)


def _why_now(kinds: list[str], hiring_ct: int, sector_hit: list[str], thesis: dict) -> str:
    bits = []
    if hiring_ct >= 2:
        bits.append(f"{hiring_ct} recent hiring signals indicate a go-to-market scaling window")
    if "exec_hire" in kinds:
        bits.append("a senior hire suggests the company is institutionalizing (transaction-readying)")
    if "funding" in kinds:
        bits.append("recent financing activity confirms momentum")
    if "launch" in kinds:
        bits.append("a new product launch is expanding surface area")
    if sector_hit:
        bits.append(f"squarely inside the '{sector_hit[0]}' target sector")
    if not bits:
        return "No acute timing catalyst detected yet; worth watching for a trigger."
    return "Why now: " + "; ".join(bits) + "."


def _next_action(fit: float, traction: float, deal_access: float, has_notes: bool) -> str:
    if fit >= 70 and traction >= 60 and deal_access >= 45:
        return "Find a warm intro to the founder and open a conversation this week."
    if fit >= 60:
        return "Add to watchlist and set a signal alert; revisit on next traction event."
    if has_notes:
        return "Log follow-up; confirm retention/margin before prioritizing."
    return "Monitor: insufficient conviction to prioritize outreach yet."


_SYSTEM_PROMPT = (
    "You are an investment-sourcing analyst. Score a company against a thesis. "
    "Return STRICT JSON with integer sub-scores 0-100 for keys: fit_score, "
    "traction_score, timing_score, team_score, novelty_score, "
    "deal_accessibility_score, risk_score; plus confidence (0-1), "
    "confidence_label, explanation, why_now, recommended_next_action, and arrays "
    "positive_evidence/negative_evidence (each item {claim, weight, source, signal_id}), "
    "missing_data, matched_criteria. Every score must be justified by evidence. "
    "Never invent facts not present in the provided signals.")


def _build_scoring_prompt(company: dict, thesis: dict, signals: list[dict]) -> str:
    sig_lines = "\n".join(
        f"- [{s.get('id','?')[:8]}] ({s.get('signal_kind')}) {s.get('title')} "
        f"from {s.get('source_name')}" for s in signals[:20]) or "- (no signals)"
    return (f"THESIS: {thesis.get('name')}\n{thesis.get('description')}\n"
            f"Target sectors: {thesis.get('target_sectors')}\n"
            f"Positive: {thesis.get('positive_keywords')}  "
            f"Negative: {thesis.get('negative_keywords')}\n\n"
            f"COMPANY: {company.get('name')} ({company.get('domain')})\n"
            f"{company.get('description')}\nSectors: {company.get('sectors')}\n\n"
            f"SIGNALS:\n{sig_lines}\n\nReturn the JSON now.")


def _judgment_from_json(d: dict, model: str) -> Judgment:
    g = lambda k, dv=0.0: float(d.get(k, dv))  # noqa: E731
    conf = float(d.get("confidence", 0.5))
    return Judgment(
        fit_score=g("fit_score"), traction_score=g("traction_score"),
        timing_score=g("timing_score"), team_score=g("team_score"),
        novelty_score=g("novelty_score"),
        deal_accessibility_score=g("deal_accessibility_score", 50),
        risk_score=g("risk_score"), confidence=conf,
        confidence_label=d.get("confidence_label",
                               "high" if conf >= 0.7 else "medium" if conf >= 0.45 else "low"),
        explanation=d.get("explanation", ""), why_now=d.get("why_now", ""),
        positive_evidence=d.get("positive_evidence", []),
        negative_evidence=d.get("negative_evidence", []),
        missing_data=d.get("missing_data", []),
        matched_criteria=d.get("matched_criteria", []),
        recommended_next_action=d.get("recommended_next_action", ""),
        model_name=model)
