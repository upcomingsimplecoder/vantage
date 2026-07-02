"""Re-score every company against every thesis using the configured provider.

Run with the live LLM env vars set to upgrade the demo from heuristic to a live
model. Old scores are preserved as prior versions (scoring never overwrites), so
the audit ledger shows the heuristic -> LLM upgrade history.

Resilience: local proxies/upstreams can rate-limit under a burst of sequential
LLM calls. This script paces requests and, when a score silently falls back to
the heuristic provider while live mode is on, retries with exponential backoff.

Usage:
    python rescore.py                 # all theses
    python rescore.py --thesis 2      # only the Nth thesis (1-indexed)
    VANTAGE_RESCORE_PACE=3 python rescore.py    # 3s between calls
"""
from __future__ import annotations

import argparse
import os
import time

from sqlalchemy import select

from vantage.config import get_settings
from vantage.db import SessionLocal
from vantage import models
from vantage.services import scoring


def _score_with_retry(db, company, thesis, *, live: bool, retries: int, pace: float):
    """Score one company; if live mode silently fell back to heuristic, retry."""
    attempt = 0
    while True:
        score = scoring.score_company(db, company, thesis)
        fell_back = live and score.model_name == "heuristic"
        if not fell_back or attempt >= retries:
            return score, attempt
        attempt += 1
        backoff = pace * (2 ** attempt)  # 2x, 4x, 8x the pacing interval
        print(f"      fell back to heuristic; retry {attempt}/{retries} after {backoff:.0f}s")
        time.sleep(backoff)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thesis", type=int, default=None,
                    help="1-indexed thesis to score (default: all)")
    ap.add_argument("--retries", type=int, default=4)
    args = ap.parse_args()

    pace = float(os.getenv("VANTAGE_RESCORE_PACE", "2.5"))
    s = get_settings()
    live = s.uses_live_llm
    print(f"AI mode: {s.ai_mode}  |  pacing {pace}s  |  retries {args.retries}")

    db = SessionLocal()
    try:
        companies = db.scalars(select(models.Company)).all()
        theses = list(db.scalars(select(models.Thesis)).all())
        if args.thesis is not None:
            theses = [theses[args.thesis - 1]]

        total = len(companies) * len(theses)
        print(f"Scoring {len(companies)} companies x {len(theses)} theses = {total} runs\n")
        n = live_ct = fb_ct = 0
        for thesis in theses:
            for company in companies:
                t0 = time.time()
                try:
                    score, retried = _score_with_retry(
                        db, company, thesis, live=live, retries=args.retries, pace=pace)
                    n += 1
                    if score.model_name == "heuristic" and live:
                        fb_ct += 1
                    elif score.model_name != "heuristic":
                        live_ct += 1
                    dt = time.time() - t0
                    tag = f", {retried} retr" if retried else ""
                    print(f"[{n:2d}/{total}] {company.name:24s} x {thesis.name[:30]:30s} "
                          f"-> {score.overall_score:5.1f}  ({score.model_name}, {dt:4.1f}s{tag})")
                except Exception as exc:  # noqa: BLE001
                    print(f"[!!] {company.name}: {exc}")
                time.sleep(pace)  # be gentle on the upstream between calls
        print(f"\nDone. {n} scores written. live={live_ct}, heuristic_fallback={fb_ct}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
