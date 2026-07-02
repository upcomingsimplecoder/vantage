# Vantage: Vision

> **An AI deal-sourcing operating system for growth investors.**
> Surface the companies your firm should know about before everyone else does.

## 1. The one-sentence thesis

Existing tools tell you who exists. Vantage tells you who matters, why now, for a specific thesis,
and what to do next. It gets smarter every day the firm uses it.

## 2. The problem

A growth equity firm's edge is proprietary sourcing: seeing the right company, at the right moment,
before the auction. Today that work is done by analysts stitching together PitchBook, Grata,
Sourcescrub, LinkedIn, news alerts, conference lists, and a CRM that is really a spreadsheet. Three
structural problems:

1. **Databases answer the wrong question.** They answer "who exists?" An investor needs "who is
   compelling, right now, for my specific mandate?" That is a judgment problem, not a search problem.
2. **Signals decay and disappear.** A hiring surge, a new CFO, a launched security page, a stale
   funding round: these "why now" signals are the alpha, and no static database captures the change
   over time that reveals them.
3. **Knowledge doesn't compound.** Every passed deal, partner note, and founder call is institutional
   memory that evaporates into inboxes. The firm re-learns the same market every quarter.

## 3. The product

Vantage sits above the data vendors as an intelligence and prioritization layer. One core loop:

```
   Define a thesis  ─►  Ingest internet signals  ─►  Resolve to companies
        ▲                                                     │
        │                                                     ▼
   Feedback sharpens ◄─  Pipeline + CRM workflow  ◄─  AI-score vs thesis
   the thesis                                          (with cited evidence)
```

Every morning an investor opens Vantage the way they open email, and sees:

> *Good morning. Here's what changed in your market.*
> *7 new companies match your "Vertical AI for compliance" thesis. 4 watchlist companies moved.
> 3 deals need follow-up. 2 now have a warm-intro path.*

They review ranked opportunities, each with a plain-English "why now," a transparent score they can
click through to the source evidence, an estimated stage, and a suggested next action. One click adds
a company to the pipeline. One click drafts the founder outreach. One click generates a first-pass
investment memo. The note taken after a founder call becomes permanent institutional memory and feeds
the next recommendation.

## 4. Why it wins (the "why not just buy PitchBook?" answer)

An in-house platform is only worth building if it does what a bought database structurally cannot:

| Bought database | Vantage |
|---|---|
| Generic filters | Encodes the firm's actual thesis: revenue bands, ownership targets, founder types, exclusion rules |
| "Company exists" | "Company matters now": timing signals such as hiring inflection, new CFO, stale round, regulatory tailwind |
| Static snapshot | Temporal history: velocity and momentum competitors starting tomorrow cannot backfill |
| Black-box or no scoring | Evidence-cited, confidence-scored judgment an investor can trust and audit |
| Read-only research | Workflow-native: pushes to CRM, assigns outreach, tracks status, reminds follow-up |
| Same data everyone buys | Compounds with every note, pass, memo, and outcome the firm produces |

Positioning: Vantage does not replace the data vendors. It turns their data, plus the open internet
and the firm's own memory, into investor-grade prioritization with timing and rationale.

## 5. The moat: why it compounds

The defensibility is not the raw data (a commodity) and not the model (everyone has the same API). It
is two things competitors cannot copy:

1. **The temporal ledger.** A snapshot of "Acme has 50 employees" is worthless. "Acme's engineering
   hiring velocity is up 300% in 4 weeks while its traffic grew 20%" is alpha, and it can only be
   computed by someone who has been recording Acme every week for months. Every day Vantage runs, the
   cold-start gap against a new entrant grows by one day.
2. **The proprietary judgment loop.** Every thesis tuning ("less services-heavy"), every pass reason,
   every "founder was strong" note trains a private model of this firm's taste and this firm's
   winning patterns. The system learns which signals actually led to deals. That knowledge belongs to
   the firm and cannot be replicated.

## 6. The long-term vision

The MVP realizes one slice. The destination is a genuine competitive advantage:

- **The Agentic Analyst.** An always-on research associate that, given a thesis, autonomously
  assembles a target long-list, drafts the first-pass evaluation with citations, and flags the three
  non-obvious companies a human would have missed. It does the analyst's first-pass job overnight, at
  the scale of the entire internet.
- **The Warm-Intro Graph.** A relationship map across the firm's collective network (every partner's
  LinkedIn, portfolio founders, past deals, advisors) so that next to every target sits "Best path
  in: your partner Sarah, to ex-colleague, to the founder." Sourcing is half access; this
  operationalizes the firm's most valuable and least-organized asset.
- **The "About-to-Raise" Predictor.** A model trained on the firm's own temporal ledger that scores
  the probability a company enters a financing or transaction window in the next 90 days, so the firm
  arrives before the banker does. This cannot be built without the historical data Vantage
  accumulates from day one.
- **Thesis Auto-Discovery.** The system notices emerging clusters of companies with shared traction
  signals that match no existing thesis, and proposes the next thesis to the partners. The platform
  stops answering the firm's questions and starts asking better ones.
- **The Compounding Memory.** Every interaction, memo, and outcome makes every future recommendation
  sharper. In year three the firm's junior analyst, armed with Vantage, out-sources a competitor's
  whole team, because the tool carries years of institutional judgment that no new hire and no vendor
  can.

## 7. What success looks like

- **Month 1:** An investor finds one company they didn't know, through Vantage, and takes a real
  meeting.
- **Month 6:** The morning Deal Radar replaces the inbox-and-spreadsheet scan. Sourcing becomes
  thesis-disciplined instead of driven by partner whim.
- **Year 1:** A closed investment is traceably attributable to a Vantage-surfaced signal. The
  temporal ledger is deep enough to power the first predictive models.
- **Year 3:** The platform is the firm's sourcing operating system and a line item in the fund's
  competitive advantage: a strategic asset that compounds.

---

*Vantage is the technological backbone of the firm's sourcing edge, designed from day one so that its
value grows with every signal captured and every decision recorded.*
