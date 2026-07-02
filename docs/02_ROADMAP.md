# Vantage: Roadmap

A phased plan from a two-week prototype to a compounding strategic asset. Each phase is shippable and
each earns the right to the next.

## Guiding principles

1. **One deep working loop beats twelve stubs.** Depth on the thesis, score, evidence, action loop,
   always.
2. **Every score cites its evidence.** No number without a clickable source. This is the trust
   foundation.
3. **Mock the scale, never the substance.** Real logic and real signal structure; fake the volume,
   not the mechanism.
4. **Deterministic ranking, LLM judgment.** The backend owns the formula; the LLM produces sub-scores
   and rationale. Auditable, versioned, never a black box.
5. **The wedge is sourcing; the retention is workflow; the moat is time.** Start recording history on
   day one.

## Phase 0: Prototype (Weeks 1-2)

**Goal:** a flawless vertical slice that proves the core loop end to end.

**Scope, the core loop end to end:**

- Define a real, defensible investment thesis (structured: sector, stage, revenue band, geography,
  positive and negative signals, exclusions).
- Ingest a curated set of sources (3-5 that will not break: RSS/news, Hacker News Algolia API,
  GitHub, an ATS endpoint, manual URL/CSV import). Seed with a representative company dataset.
- Entity resolution v1: domain-anchored, precision over recall.
- LLM enrichment: what the company does, sector, business model, traction/hiring/funding signals,
  each traced to a source signal.
- Evidence-cited scoring against the thesis: sub-scores (fit, traction, timing, team, novelty, risk)
  plus a deterministic aggregate plus confidence and missing-data flags.
- Deal Radar (ranked feed), Company Profile (score breakdown, evidence, signals timeline), Thesis
  Manager, Pipeline board.
- One-click investment memo generated from evidence, with citations and "why now / risks / questions
  for the founder / suggested next action."
- CRM note-taking that visibly feeds back into the loop.

**Deliverables:**

- Clean repo with an excellent README (architecture, explicit "what's real vs. illustrative," design
  tradeoffs, "how I'd productionize").
- A short build-notes and decisions doc.
- Optionally a hosted demo, only if it runs a deterministic seeded path flawlessly.

**Explicitly deferred:** web-scale crawling, LinkedIn scraping, real email/calendar sync,
multi-tenant auth/RBAC, custom ML models, autonomous agents, portfolio analytics, automated outreach.

**Success test:** it surfaces one non-obvious company, scores it with transparent clickable evidence,
and outputs a memo an analyst would actually use.

## Phase 1: Foundation, first real users inside the firm (Months 1-2)

**Goal:** the loop runs on live data daily; 2-3 investors adopt the morning Deal Radar.

- Harden ingestion into scheduled, idempotent jobs (Dagster/Prefect or Redis-worker cron) with
  retry/backoff and a visible `job_runs` audit table.
- Expand sources: Product Hunt, more ATS boards (Greenhouse/Lever JSON), SEC/EDGAR, news APIs, GitHub
  events. Prefer official or licensed APIs.
- Begin the temporal ledger: snapshot key metrics on a schedule so velocity and momentum become
  computable. This is the moat clock; start it immediately.
- Entity-resolution v2: alias table, fuzzy plus embedding plus LLM adjudication for the ambiguous
  middle band, and a human merge-review queue.
- Pipeline/CRM: full stage board, notes, meeting templates, next-action reminders, AI note
  summarization and action-item extraction.
- Saved searches and thesis-based alerts (in-app plus a tight daily email digest).
- Basic auth for a single firm; Sentry plus structured logging.

**Success test:** a partner takes a real founder meeting sourced through Vantage; the daily digest
becomes habit.

## Phase 2: Intelligence, it gets visibly smarter (Months 3-6)

**Goal:** momentum signals and feedback learning make recommendations demonstrably sharper than a
saved search.

- **Momentum metrics live:** hiring velocity, headcount deltas, traffic proxies (CrUX/BigQuery),
  tech-stack changes, role-mix shifts (for example a spike in enterprise AE roles suggesting a move
  upmarket).
- **Feedback learning:** "more/less like this" and structured pass-reasons tune thesis weights; the
  system learns the firm's taste.
- **Negative-signal detection:** layoffs, exec churn, bad reviews, stalled hiring, pricing
  complaints. Dealability and risk, not just hype.
- **Warm-Intro Graph v1:** ingest the firm's collective network (with consent) and surface the
  best-path-in per target.
- Semantic discovery: "find companies like Stripe circa 2016" over the company embedding space.
- Thesis coverage analytics: where is the firm over- or under-sourcing?

**Success test:** an investor says the recommendations feel personalized to the firm, and a warm
intro sourced by Vantage converts to a meeting.

## Phase 3: Compounding asset (Months 6-18)

**Goal:** proprietary data loops that competitors structurally cannot replicate.

- **"About-to-Raise" predictor** trained on the firm's own temporal ledger: probability of a
  financing or transaction window in the next 90 days.
- **Agentic Analyst:** given a thesis, autonomously assembles the long-list overnight, drafts
  first-pass evaluations with citations, flags the non-obvious few. Human-in-the-loop review.
- **Thesis auto-discovery:** detect emerging clusters that match no current thesis and propose the
  next one to the partners.
- Attribution: trace closed deals back to originating signals; measure sourcing ROI.
- Full investment-memo builder integrated with IC workflow; comparables and market-size assist.
- Scale story executed as needed: split ingestion workers by source, partition signals by date,
  materialized views for rankings, Temporal for long-running or human-in-the-loop workflows, object
  storage for documents.

**Success test:** a closed investment is attributable to a Vantage signal; the predictive model beats
the firm's baseline sourcing timing.

## Sequencing logic

```
Phase 0  ──►  proves the LOOP
Phase 1  ──►  proves DAILY ADOPTION     + starts the moat clock (temporal ledger)
Phase 2  ──►  proves it gets SMARTER    (momentum + feedback learning)
Phase 3  ──►  proves it's a WEAPON      (prediction + agentic + attribution)
```

Each phase de-risks the next. Phase 0's job is not to be complete. It is to prove the core loop
creates investment-judgment leverage, and to establish the judgment about what to build, simulate,
and skip.
