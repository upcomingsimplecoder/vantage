# Vantage: Technical Specification

Architecture for a system operated by one engineer yet credibly production-grade. Optimized to ship a
compelling working slice in about two weeks while telling a story that scales.

## 1. Design tenets

1. **Canonical company graph.** Everything (signals, people, interactions, scores, notes, theses)
   attaches to one canonical `Company` entity. That is what makes the data compound.
2. **Raw evidence is immutable.** Signals are never overwritten. AI outputs are stored as versioned
   artifacts and promoted into canonical fields only through explicit enrichment steps. No silent
   model mutation of source-of-truth data.
3. **Deterministic ranking, LLM judgment.** The LLM produces structured sub-scores, rationale, and
   evidence IDs. The backend owns the weighted aggregation formula, which is versioned and auditable.
   No score without cited evidence.
4. **Precision over recall in entity resolution.** Better to create a possible duplicate (reviewable
   later) than to corrupt a canonical profile with wrong evidence.
5. **Modular monolith.** Clean domain-service boundaries, not microservices. Idempotent jobs,
   auditable runs, a schema that can grow.
6. **Production-grade is not overbuilt.** No Kafka, K8s, Spark, Neo4j, Pinecone, or custom agent
   framework for the MVP.

## 2. Stack

**Frontend:** Next.js / React, TailwindCSS, shadcn/ui, TanStack Query (React Flow later for workflow
viz)

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2

**Data:** Postgres 16, pgvector (semantic search, no separate vector DB), Redis (broker plus light
cache)

**Jobs:** Dramatiq (or Celery) on Redis, idempotent background workers

**AI:** OpenAI/Anthropic via the LiteLLM abstraction, Instructor/Pydantic structured outputs,
embeddings `text-embedding-3-small`

**Infra:** Docker Compose (local/demo), Vercel (frontend) plus Render/Railway (API and worker) plus
Neon/Supabase (Postgres) plus Upstash (Redis) for a hosted demo

**Observability:** Sentry, structured JSON logs, `job_runs` table (Langfuse for LLM tracing later)

### Why this stack

- **Python/FastAPI:** the strongest ecosystem for AI/data workflows; Pydantic pairs cleanly with LLM
  structured outputs.
- **Postgres:** a canonical relational source of truth with constraints, JSONB flexibility,
  full-text search, and pgvector in one system.
- **pgvector:** avoids the operational burden of a separate vector DB; vectors are for retrieval,
  while identity lives in relational tables.
- **Redis workers:** separate request latency from enrichment and scoring without the weight of
  Kafka/Temporal until workflows actually demand it.

## 3. Architecture

```
   Next.js (Vercel)
        │  HTTPS / JSON
        ▼
   FastAPI  ──────────────►  Postgres 16 + pgvector   (source of truth)
        │   enqueue jobs           ▲
        ▼                          │ read/write
   Redis  ◄────────────────  Dramatiq workers  ──►  External sources + LLM APIs
                                 (ingest, resolve, enrich, embed, score, memo)
```

**Backend module layout**

```
app/
  api/         companies, theses, signals, scoring, interactions, search, jobs
  core/        config, db, security, logging
  models/      company, person, signal, thesis, score, interaction, workflow, job
  schemas/     pydantic request/response + LLM output schemas
  services/
    ingestion/            SourceConnector implementations
    entity_resolution.py
    enrichment.py
    scoring.py
    embeddings.py
    crm.py
    memo.py
  workers/     tasks.py   (idempotent job definitions)
  llm/         client (LiteLLM), prompts (versioned), schemas
```

**Domain services (modules, not microservices):** Ingestion, EntityResolution, Enrichment,
Embedding, Scoring, Memo, CRM. Clean boundaries, easy to explain, trivial to later peel into separate
deployables.

## 4. Data model

The core entity is `companies`; everything else is either raw evidence, a normalized entity, a human
interaction, an AI-derived judgment, or workflow state.

**`companies`**: canonical target. `id, name, normalized_name, domain (unique), website_url,
description, founded_year, hq_city, hq_country, employee_count, linkedin_url, crunchbase_url,
github_url, status, source_confidence, created_at, updated_at`
`status in {discovered, watching, prioritized, contacted, meeting_scheduled, diligence, passed,
invested}`

**`company_aliases`**: entity resolution. `id, company_id, alias, alias_type in
{name,domain,social_handle,linkedin,crunchbase}, source, confidence`

**`people`**: `id, full_name, normalized_name, linkedin_url, email, title, location, timestamps`

**`company_people`**: M2M. `company_id, person_id, role, relationship_type in
{founder,executive,employee,investor,advisor,contact}, confidence, source_signal_id`

**`signals`**: immutable raw evidence. `id, source_type in
{rss,news,linkedin,github,job_post,web_page,manual,api}, source_name, source_url, title, raw_text,
published_at, discovered_at, content_hash (unique), metadata jsonb, embedding vector,
processing_status in {pending,processed,failed,ignored}, created_at`

**`signal_companies`**: links evidence to companies. `signal_id, company_id, relation_type in
{mentioned,about,competitor,customer,investor,partner}, confidence, resolver_method in
{domain_match,alias_match,embedding_match,llm_match,manual}, evidence`

**`theses`**: investor mandate. `id, name, description, target_sectors[], positive_keywords[],
negative_keywords[], stage_preference, geography_preference[], revenue_band, scoring_config jsonb,
embedding vector, active, timestamps`

**`company_scores`**: point-in-time, versioned (never overwritten). `id, company_id, thesis_id,
overall_score, fit_score, traction_score, timing_score, team_score, novelty_score, risk_score,
confidence, explanation, positive_evidence jsonb, negative_evidence jsonb, model_name, prompt_version,
scored_at`

**`score_factors`**: auditability. `id, company_score_id, factor_name, score, weight, rationale,
supporting_signal_ids[]`. Powers the "why did this rank highly?" UI panel.

**`interactions`**: CRM. `id, company_id, person_id, interaction_type in
{note,email,call,meeting,intro,task,status_change}, occurred_at, summary, raw_notes, sentiment,
next_steps, created_by, created_at`

**`company_metrics`** *(the moat table, start recording day one)*: temporal snapshots. `id,
company_id, metric_name (for example headcount, open_roles, eng_roles, traffic_proxy), value,
captured_at`. Velocity is the derivative over these rows. This is what a new entrant cannot backfill.

**`job_runs`**: production credibility. `id, job_type, entity_type, entity_id, status in
{queued,running,succeeded,failed}, started_at, finished_at, error, metadata jsonb`

**`ai_outputs`**: anti-black-box ledger. `id, entity_type, entity_id, task_type, model,
prompt_version, input_hash, output_json, confidence, created_at`

*Optional or later:* `meetings`, `deal_workflows`, `tasks`, `source_configs`, `documents`.

## 5. The pipeline

```
Ingest ─► Dedup ─► Extract ─► Resolve ─► Enrich ─► Embed ─► Thesis-match ─► Score ─► CRM/workflow update
```

**Ingestion.** `SourceConnector` interface (`fetch() -> list[RawSignal]`). MVP connectors: RSS/news,
ManualUrl, CsvImport, GithubSearch, WebPage, HackerNews (Algolia), ATS (Greenhouse/Lever JSON).
Prefer APIs; keep raw crawling under 10% of volume; use Firecrawl/ScrapingBee when JS rendering is
unavoidable. Consider `dlt` for schema-inference on messy JSON endpoints so pipelines do not crash
when a startup changes its structure.

**Dedup.** `content_hash = sha256(source_url + title + normalized_text[:1000])`, unique index, skip
duplicates.

**Extract** (LLM structured output). Per signal to `{companies[], people[], sectors[],
traction_events[], funding_events[], hiring_signals[], summary, relevance}`. Deterministic fallback:
domain parsing, regex for emails/domains, alias-table lookup.

**Resolve** (layered cascade, precision-biased):

1. Exact domain match, then 2. exact alias match, then 3. normalized-name exact, then 4. fuzzy name
   (Jaro-Winkler / TF-IDF), then 5. embedding similarity, then 6. LLM adjudication for the ambiguous
   60-85% band ("Do these records represent the same corporate entity? boolean"), else 7. create a
   new company. Canonical key throughout: the root domain (strip `www`, subdomains, paths).

**Enrich.** Per resolved company to `{short_description, long_description, sectors, business_model,
customer_segments, traction_signals, funding_signals, hiring_signals, risks, confidence}`. Written to
canonical fields plus `ai_outputs`.

**Embed.** Signals, companies, theses to pgvector. Uses: thesis-to-company similarity, evidence
retrieval for scoring, semantic search, dedup candidate detection.

**Score.** For each active thesis by company: retrieve top signals attached to the company, top
thesis-relevant signals, and latest interactions, build context, the LLM returns structured
sub-scores plus rationale plus evidence IDs, validate with Pydantic (retry once, else mark failed and
store raw), the backend computes the deterministic aggregate, store as a new `company_scores`
version.

```
overall = 0.30*fit + 0.20*traction + 0.15*timing + 0.15*team
        + 0.10*novelty + 0.10*deal_accessibility − 0.15*risk
```

The LLM proposes sub-scores and evidence; the formula is owned, versioned, and auditable by the
backend. Scores carry confidence and missing-data flags, with no fake precision such as "87.4/100."

**Memo.** Company plus top signals plus interactions plus scores to a structured investment memo:
overview, thesis fit, why now, bull/bear, comparables, risks, questions for the founder, recommended
next action, with citations to signal IDs.

## 6. AI layer discipline

- Structured outputs validated by Pydantic; one retry on failure; raw output stored on hard failure.
- Every output stamped with `model`, `prompt_version`, `input_hash`, `confidence`, written to
  `ai_outputs`.
- No score without evidence IDs. The model does not silently mutate core data. AI outputs are
  versioned artifacts, promoted into canonical fields only through explicit enrichment.
- Not "agents" first. Deterministic pipelines with LLM calls at specific decision points. Agentic
  autonomy is a Phase 3 concern, gated on the eval loop working.

## 7. API surface (resource-oriented)

```
GET  /health
Companies:   GET /companies (filters: thesis_id,status,min_score,sector,search,sort),
             POST /companies, GET/PATCH /companies/{id},
             GET /companies/{id}/{signals|scores|interactions|memo}
Signals:     GET /signals, POST /signals/{manual|import-url|import-csv},
             GET /signals/{id}, POST /signals/{id}/process
Theses:      GET/POST /theses, GET/PATCH /theses/{id}, POST /theses/{id}/rescore
Scoring:     POST /companies/{id}/score, POST /scoring/run, GET /scores, GET /scores/{id}
Search:      GET /search?q=, POST /search/semantic
CRM:         GET/POST /interactions, PATCH /interactions/{id},
             GET /pipeline, PATCH /companies/{id}/status
Jobs:        GET /jobs, GET /jobs/{id}, POST /jobs/{id}/retry
Demo (flagged ENABLE_DEMO_ENDPOINTS): POST /demo/seed, POST /demo/run-pipeline, GET /dashboard/summary
```

Auth: single-user/single-firm for MVP (simple JWT). RBAC deferred until selling to multiple firms.

## 8. Jobs, idempotency, orchestration

Dramatiq/Celery on Redis. Job types: `ingest_source, process_signal, resolve_signal_entities,
enrich_company, embed_signal, embed_company, score_company, generate_memo, snapshot_metrics`.

**Idempotency guarantees:** the same signal processed twice yields no duplicate company (content_hash
plus unique constraints plus precision-biased resolution); scoring always creates a new version
rather than mutating. Every run is recorded in `job_runs` (queued to running to succeeded/failed),
retryable and auditable.

**Scale migration path (documented, not built):** split ingestion workers by source, partition
`signals` by `discovered_at`, materialized views (`company_latest_scores`, `thesis_rankings`,
`pipeline_summary`), Temporal when workflows become long-running or human-in-the-loop or need durable
compensation, object storage for raw documents, queue backpressure.

## 9. Frontend: MVP screens

Nav: Deal Radar, Theses, Pipeline, Companies, Alerts, Notes. Build these four first (they show the
full loop):

1. **Deal Radar** (home): ranked company cards, each with a one-line description, thesis-match chip,
   score badge, "why now" signal chips, stage estimate, warm-intro availability, suggested next
   action. Filters: thesis/stage/geo/sector/signal-type/score/new-since-last-visit. Card actions:
   save, dismiss, add-to-pipeline, draft-outreach, find-intro, create-memo, not-a-fit (reason).
   Editorial, not database-like.
2. **Company Profile:** snapshot, AI investment summary (why it matters, why now, bull, bear,
   comparables), thesis-match (matched plus missing criteria plus confidence), signals timeline,
   people and network, pipeline activity, memo starter. Answers "should I spend time on this?" not
   just "what is this?"
3. **Thesis Manager:** structured thesis config plus "more/less like this" feedback that tunes
   weights. Makes it smarter than a saved search.
4. **Pipeline board:** Kanban across the deal stages; cards show owner, thesis, score, last activity,
   next action, risk flags. Action-oriented views: "high-score untouched," "stale deals."

**Critical UX rule: every AI claim shows its receipts.** `Score 87, High confidence, because: matches
7/9 thesis criteria, 42% headcount growth, 3 enterprise hiring signals, founder-market fit (prior
role), [click any to source signal]`. Investors forgive incomplete data if the system is honest about
confidence; they never forgive a black box. This is not a chatbot. AI is embedded in the workflow,
not a chat box bolted on top.

## 10. Two-week build plan

**Week 1, the engine**

- D1 Repo, FastAPI skeleton, Postgres schema, Alembic, Docker Compose, seed data
- D2 Companies/theses/signals APIs, Next.js shell, CRUD
- D3 Manual-URL plus RSS ingestion, content extraction, dedup
- D4 LLM structured extraction, entity resolution v1, company create/link
- D5 Embeddings, thesis matching, semantic search

**Week 2, the judgment plus the story**

- D6 Scoring pipeline, `company_scores`, evidence-backed rationale
- D7 Deal Radar UI, Company Profile, evidence panel
- D8 Interactions/CRM notes, pipeline board, next-action
- D9 Investment memo generation, "why this company?" panel, demo seed script
- D10 Polish, observability, error states, deploy

**Demo flow:** create thesis, "Run sourcing," the system ingests and resolves about 20 companies,
ranks the top 5, click one, see the score plus evidence plus signals plus founders plus risks plus
outreach angle plus generated memo, add a note ("met founder, strong velocity, need customer refs"),
and the score and pipeline update.

## 11. Deliberately deferred

Web-scale crawling, LinkedIn scraping (ToS/CFAA risk), real email/calendar sync, multi-tenant RBAC,
Kafka/streaming, a separate vector DB, a graph DB, custom ML models, autonomous agents, real-time
collaboration, portfolio analytics, automated outreach (AI drafts, a human sends).

## 12. Compliance and data provenance

- **No LinkedIn scraping.** Legitimate sources only: company sites, press, SEC/EDGAR, news APIs,
  GitHub, public ATS endpoints, licensed vendor APIs (Crunchbase, and others). Knowing where this
  line sits matters.
- Respect robots.txt and rate limits; prefer official APIs.
- Store links, short snippets, and derived analysis, not full copyrighted reproductions.
- Public professional info only on founders; no invasive people-dossiers (GDPR/CCPA).
- Secrets in env vars; `.env.example` committed, never real keys.
- The README states data provenance explicitly.

---

*The riskiest problem is not infrastructure scale. It is whether the scoring-and-evidence loop
actually creates investment-judgment leverage. This spec is built to prove that loop first, and to
scale only once it is proven.*
