# Vantage

**An AI deal-sourcing operating system for growth investors.**
Surface the companies your firm should know about before everyone else does.

Vantage sits above the data vendors as an intelligence and prioritization layer. It ingests
signals from across the internet, resolves them to companies, scores each company against a
specific investment thesis with cited evidence, surfaces the non-obvious "why now," and drafts a
first-pass investment memo. It is designed to compound in value as the firm captures more
proprietary data.

> This repository is a working prototype that thinks the problem through end to end: a real backend
> engine (entity resolution, versioned evidence-cited scoring, memo generation) and a polished
> investor-facing UI. It runs fully offline with zero API keys. See
> [What's real vs. illustrative](#whats-real-vs-illustrative) for an honest boundary.

## Quickstart

Requires Python 3.11+. No API keys. No external services. No Docker.

```bash
git clone <repo-url> vantage && cd vantage
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m vantage.seed                                  # builds SQLite DB: 13 companies, 2 theses, 33 signals, 26 scores
uvicorn vantage.main:app --reload --port 8077
```

Open **http://127.0.0.1:8077**. The Deal Radar is live.

The banner reads *"AI engine: heuristic (deterministic, offline)."* This is intentional. With no key
configured, Vantage scores companies with a deterministic heuristic engine that produces genuine,
evidence-cited output. Add an OpenAI key (see [Configuration](#configuration)) and the same pipeline
routes through a live LLM instead. One env var, no code change.

## Product tour

The value is in the judgment, not the interface. A short tour of the loop:

**1. Deal Radar (`/`).** A ranked feed of companies scored against the active thesis, each with a
tier-colored Vantage score, a plain-English *why now*, and evidence chips. Switch the thesis in the
top-right dropdown and the entire ranking re-orders. The same company scores differently against a
different mandate. Scoring is thesis-relative, not a universal "good company" number.

**2. A non-obvious result: open Aperture Health.** Keyword matching would bury this company. Vantage
ranks it near the top, not because it matches thesis keywords, but because it detected a
hiring-velocity spike (three hiring signals in a short window: implementation engineers, enterprise
CSMs, a VP of Sales) that reads as a go-to-market scale-up before it is obvious. The **Why now** card
makes this the centerpiece, and the evidence ledger below traces every point of the score to a
specific signal with its source.

**3. Score decomposition (same page).** The overall score breaks into seven sub-scores: fit,
traction, timing, team, novelty, deal accessibility, and a subtracted risk score. Every positive and
negative claim cites its source signal, so an investor can audit why the system flagged a deal.

**4. Investment memo (`Generate Investment Memo`).** One click turns the score into a first-pass
memo: a PURSUE/WATCH recommendation, a bull case and a bear case (each with cited sources), and
diligence questions for the founder. It compresses the first hours of associate research into a
sourced, inspectable brief.

**5. Pipeline (`/pipeline`) and Jobs (`/api/jobs`).** A Kanban board tracks each company through the
deal lifecycle. Logging a note re-scores the company, so the firm's own judgment feeds the loop. The
Jobs and AI-outputs ledgers record every scoring run with versioned, auditable provenance.

## What's real vs. illustrative

This is a proof of mechanism, not a finished product, and the boundary is stated plainly.

| Layer | Status in this prototype |
|---|---|
| Backend architecture (schema, services, API, UI) | **Real.** Production patterns throughout. |
| Entity resolution (signal to canonical company) | **Real.** 6-step matching cascade (exact domain, normalized name, alias, fuzzy, and more). |
| Scoring engine | **Real logic.** Deterministic heuristic over actual signal features, not random, not hardcoded per company. |
| Evidence citations | **Real.** Every score claim links to the signal that produced it. |
| Score aggregation | **Real.** Versioned, auditable weighted formula owned by the backend, not the model. |
| Investment memo generation | **Real.** Assembled from the company's own scored evidence. |
| Live LLM scoring path | **Real but optional.** Wired for OpenAI; falls back to heuristic on any error. |
| The company and signal data | **Synthetic.** 13 fabricated-but-realistic companies and 33 signals, engineered to demonstrate the mechanics (for example Aperture's hiring-velocity story). No real companies are scraped or labeled. |

**Why synthetic data?** Fabricating signals about real companies would be both amateurish and legally
reckless (ToS/CFAA exposure). The production system plugs into real signal sources and the firm's
proprietary data, which is a deployment concern deliberately out of scope here. The mechanism is what
this prototype demonstrates.

## Architecture

```
Signals (hiring, funding, launches, news)
   │
   ▼  ingestion.py ──► entity_resolution.py   (6-step match cascade → canonical company graph)
   │
   ▼  scoring.py  ◄── ai.py (HeuristicProvider | LiveLLMProvider)
   │   - provider proposes evidence-cited SUB-SCORES
   │   - backend owns the deterministic weighted AGGREGATION (versioned)
   │   - writes an immutable score row + ai_outputs ledger + job_run
   ▼
SQLite (canonical graph: companies, signals, theses, scores, interactions, people, CRM, audit)
   │
   ▼  main.py (FastAPI) ──► JSON API + server-rendered UI (Deal Radar, Profile, Memo, Pipeline)
```

**Design principles that show up in the code:**

- **The model proposes; the backend decides.** The AI (heuristic or LLM) returns structured
  sub-scores with evidence. The final number comes from a deterministic, versioned weighted formula
  in `scoring.py`, so aggregation is auditable and judgment is separable from mechanism.
- **Scores are immutable and versioned.** Re-scoring never overwrites; it appends a new row. The
  profile shows score history. Every score carries `prompt_version` and `formula_version`.
- **No score without cited evidence.** Every claim references its source signal.
- **Provider abstraction.** `heuristic` (offline default) and `live LLM` sit behind one interface,
  and the live path falls back to heuristic on any error.
- **Zero-setup by default.** SQLite plus the heuristic engine means clone and run. WAL mode and
  `busy_timeout` are set for real concurrency under uvicorn's threadpool.

### Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0
- **Storage:** SQLite (WAL mode), swappable for Postgres via `VANTAGE_DATABASE_URL`
- **UI:** server-rendered Jinja2 with a single hand-written stylesheet (dark, no build step)
- **AI:** pluggable provider; deterministic heuristic default, OpenAI optional

## Configuration

Everything is env-overridable, and all defaults make the app run with zero setup. Copy `.env.example`
to `.env` only if you want to change something.

| Env var | Default | Purpose |
|---|---|---|
| `VANTAGE_DATABASE_URL` | `sqlite:///./vantage.db` | Swap in Postgres, and so on. |
| `VANTAGE_LLM_PROVIDER` | `heuristic` | Set to `openai` for live LLM scoring. |
| `VANTAGE_LLM_API_KEY` | *(unset)* | Required only when provider is `openai`. |
| `VANTAGE_LLM_MODEL` | `gpt-4o-mini` | Live model name. |
| `VANTAGE_PROMPT_VERSION` | `p0-2024.06` | Stamped onto every score for provenance. |
| `VANTAGE_SCORE_FORMULA_VERSION` | `v1` | Stamped onto every score for provenance. |

**To enable live LLM scoring:**

```bash
export VANTAGE_LLM_PROVIDER=openai
export VANTAGE_LLM_API_KEY=sk-...
python -m vantage.seed          # re-score through the live model
```

The UI banner will switch to `live:openai:gpt-4o-mini`. No other change required.

## API surface

The UI is a thin skin over a JSON API. Every screen has a machine-readable equivalent.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness and current AI mode. |
| `GET` | `/api/companies?thesis_id=&min_score=&status=` | Ranked companies for a thesis. |
| `GET` | `/api/companies/{id}?thesis_id=` | Full company with decomposed score and evidence. |
| `GET` | `/api/companies/{id}/memo?thesis_id=` | Generated investment memo (JSON). |
| `GET` | `/api/theses` | All investment theses. |
| `POST` | `/api/scoring/run?thesis_id=` | Re-score every company against a thesis. |
| `GET` | `/api/jobs` | Recent job runs (provenance ledger). |
| `GET` | `/api/ai-outputs` | Every AI judgment, versioned and auditable. |

```bash
# Try it:
curl -s localhost:8077/api/health
curl -s "localhost:8077/api/companies" | python -m json.tool | head -40
```

## Project layout

```
vantage/
├── main.py                 # FastAPI app: JSON API + server-rendered UI (routes)
├── config.py               # env-overridable settings; zero-setup defaults
├── db.py                   # SQLAlchemy engine, session, WAL/pragma hardening
├── models.py               # canonical company graph (companies, signals, theses, scores, ...)
├── seed.py / seed_data.py  # reset, load synthetic corpus, ingest, score
├── services/
│   ├── ingestion.py        # signal intake
│   ├── entity_resolution.py# 6-step signal-to-company match cascade
│   ├── ai.py               # HeuristicProvider + LiveLLMProvider behind one interface
│   ├── scoring.py          # deterministic versioned aggregation formula
│   ├── memo.py             # investment-memo assembly
│   └── text.py             # normalization + lightweight embedding/cosine
├── templates/              # Jinja2 (radar, company, memo, theses, pipeline)
└── static/app.css          # single hand-written dark theme, no build step

docs/
├── 01_VISION.md            # north star, moat, long-term vision
├── 02_ROADMAP.md           # phased build plan
└── 03_TECH_SPEC.md         # full architecture, API, data model
```

## Reproducibility

`python -m vantage.seed` is deterministic. It resets the database and rebuilds the same 33 signals,
13 companies, and 26 scores every time, with zero duplicate companies (entity resolution verified).
Delete `vantage.db*` and re-seed any time for a clean slate.

---

*Vantage is designed from day one so its value compounds with every signal captured and every
decision recorded: the technological backbone of a firm's sourcing edge.*
