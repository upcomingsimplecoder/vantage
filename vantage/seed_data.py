"""Curated corpus: realistic but synthetic.

These companies are illustrative and do not represent real businesses; signals
are fabricated for demonstration. This is deliberate: fabricating signals about
real companies would be misleading and is the exact trap to avoid. The pipeline
that processes this corpus is real and runs identically on live sources.

The data is engineered to produce an interesting ranking spread against the
'Vertical AI for compliance-heavy industries' thesis, including one non-obvious
winner (Aperture) that rises on signal VELOCITY rather than obvious keywords.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .services.ingestion import RawSignal

_NOW = datetime.now(timezone.utc)


def _ago(days: int) -> datetime:
    return _NOW - timedelta(days=days)


# Theses
THESES = [
    {
        "name": "Vertical AI for compliance-heavy industries",
        "description": (
            "AI-native workflow software that automates regulatory, compliance, and "
            "back-office operations in regulated verticals (healthcare, fintech, "
            "insurance, legal). B2B SaaS, early enterprise traction, clear founder-"
            "market fit. We back durable revenue with strong retention, not hype."),
        "target_sectors": ["healthcare", "fintech", "insurance", "legal", "compliance"],
        "positive_keywords": ["compliance", "regulatory", "workflow", "automation",
                              "audit", "enterprise", "SOC 2", "HIPAA", "AI-native"],
        "negative_keywords": ["consumer app", "chatbot wrapper", "agency", "crypto token"],
        "stage_preference": "series_a",
        "geography_preference": ["US", "North America"],
        "revenue_band": "$3M-$30M ARR",
    },
    {
        "name": "Developer infrastructure with usage-led growth",
        "description": (
            "Developer-first infrastructure and tooling companies with bottoms-up, "
            "usage-based distribution and open-source-led adoption."),
        "target_sectors": ["developer tools", "infrastructure", "data", "security"],
        "positive_keywords": ["open source", "developer", "API", "usage-based",
                              "infrastructure", "self-serve"],
        "negative_keywords": ["services", "consulting"],
        "stage_preference": "seed",
        "geography_preference": ["US", "Europe"],
        "revenue_band": "$1M-$15M ARR",
    },
]


# Companies + their signals
# Each entry: company metadata + list of (title, kind, source, days_ago, meta)
def _c(name, domain, desc, sectors, model, city, emp, signals):
    return {"name": name, "domain": domain, "description": desc, "sectors": sectors,
            "business_model": model, "hq_city": city, "employee_count": emp,
            "signals": signals}


COMPANIES = [
    _c("Attestable AI", "attestable.ai",
       "AI-native SOC 2 and HIPAA compliance automation platform for healthcare software vendors. Continuously monitors controls and auto-generates audit evidence.",
       ["healthcare", "compliance"], "B2B SaaS", "Boston", 48, [
           ("Attestable AI hiring 5 enterprise account executives", "hiring", "Greenhouse", 12, {"open_roles": 11, "eng_roles": 4}),
           ("Attestable launches automated HIPAA audit-evidence engine", "launch", "Company blog", 20, {}),
           ("Attestable AI raises $14M Series A led by Bessemer", "funding", "TechCrunch", 34, {}),
           ("Former Datadog compliance lead joins Attestable as VP Eng", "exec_hire", "LinkedIn (public post)", 26, {}),
       ]),
    _c("Aperture Health", "aperturehealth.io",
       "Workflow automation for payer-provider prior-authorization. Uses AI to route and pre-adjudicate authorization requests under regulatory SLAs.",
       ["healthcare", "insurance"], "B2B SaaS", "Nashville", 31, [
           ("Aperture Health hiring implementation engineers (x4)", "hiring", "Lever", 6, {"open_roles": 9, "eng_roles": 3}),
           ("Aperture Health hiring enterprise CSMs and RevOps", "hiring", "Lever", 18, {"open_roles": 6}),
           ("Aperture adds SOC 2 Type II and expands to 3 new payers", "traction", "Company blog", 9, {}),
           ("Aperture Health hiring VP of Sales", "hiring", "Greenhouse", 24, {"open_roles": 5}),
       ]),
    _c("Lexroom", "lexroom.ai",
       "AI paralegal workflow for regulatory filings at mid-market law firms. Drafts, checks, and tracks compliance-sensitive documents.",
       ["legal", "compliance"], "B2B SaaS", "New York", 22, [
           ("Lexroom launches automated regulatory-filing checker", "launch", "Product Hunt", 15, {}),
           ("Lexroom signs first AmLaw 100 pilot", "traction", "Company blog", 11, {}),
           ("Lexroom hiring 2 backend engineers", "hiring", "Greenhouse", 21, {"open_roles": 3, "eng_roles": 2}),
       ]),
    _c("Ledgerly", "ledgerly.com",
       "Automated audit and controls monitoring for fintech and banking-as-a-service companies. Continuous compliance for money-movement workflows.",
       ["fintech", "compliance"], "B2B SaaS", "San Francisco", 65, [
           ("Ledgerly raises $40M Series B", "funding", "Axios Pro Rata", 8, {}),
           ("Ledgerly hiring across GTM after Series B", "hiring", "Greenhouse", 5, {"open_roles": 18}),
           ("Ledgerly named a leader in continuous-controls monitoring", "news", "Industry report", 30, {}),
       ]),
    _c("Verano Insurance Tech", "verano.io",
       "AI-driven compliance and filing automation for insurance carriers navigating state-by-state regulatory requirements.",
       ["insurance", "compliance"], "B2B SaaS", "Chicago", 27, [
           ("Verano automates multi-state insurance rate filings", "launch", "Company blog", 22, {}),
           ("Verano hiring compliance solutions engineer", "hiring", "Lever", 28, {"open_roles": 2}),
       ]),
    _c("Consentr", "consentr.com",
       "Consent and data-privacy management platform. Consumer-facing privacy dashboard plus a light B2B API.",
       ["compliance"], "B2B SaaS", "Austin", 19, [
           ("Consentr launches consumer privacy app", "launch", "Product Hunt", 40, {}),
           ("Consentr featured in privacy newsletter", "news", "Newsletter", 33, {}),
       ]),
    _c("Cobalt Compliance", "cobaltcompliance.co",
       "Compliance consulting firm offering managed SOC 2 readiness services with a lightweight tracking portal.",
       ["compliance"], "Services", "Denver", 40, [
           ("Cobalt Compliance grows managed-services team", "hiring", "Company site", 26, {"open_roles": 4}),
           ("Cobalt publishes SOC 2 readiness guide", "news", "Company blog", 50, {}),
       ]),
    _c("Nimbus Records", "nimbusrecords.health",
       "Cloud EHR for specialty clinics with built-in regulatory reporting. Older codebase, steady but slow growth.",
       ["healthcare"], "B2B SaaS", "Portland", 55, [
           ("Nimbus Records adds state reporting module", "launch", "Company blog", 120, {}),
           ("Nimbus hiring support staff", "hiring", "Indeed", 60, {"open_roles": 2}),
       ]),
    _c("Streamline Legal", "streamlinelegal.com",
       "Document-automation agency building custom legal workflows for enterprises. Services-heavy, project-based revenue.",
       ["legal"], "Agency", "Atlanta", 34, [
           ("Streamline Legal wins enterprise services contract", "traction", "Company blog", 45, {}),
       ]),
    _c("Fathom Underwriting", "fathomuw.ai",
       "AI underwriting workbench for commercial insurers with embedded compliance checks against filing rules.",
       ["insurance", "fintech"], "B2B SaaS", "New York", 24, [
           ("Fathom Underwriting hiring ML engineers (x3)", "hiring", "Lever", 14, {"open_roles": 7, "eng_roles": 3}),
           ("Fathom launches compliance-aware underwriting copilot", "launch", "Company blog", 19, {}),
           ("Fathom hiring enterprise AE", "hiring", "Greenhouse", 27, {"open_roles": 4}),
       ]),
    # Dev-infra thesis companies
    _c("Quill Data", "quilldata.dev",
       "Open-source data pipeline framework with a usage-based cloud offering. Strong developer adoption.",
       ["developer tools", "data"], "Usage-based", "Remote", 21, [
           ("Quill Data crosses 12k GitHub stars", "traction", "GitHub", 10, {}),
           ("Quill Data hiring developer-experience engineers", "hiring", "Greenhouse", 16, {"open_roles": 5, "eng_roles": 4}),
           ("Quill Data launches self-serve cloud", "launch", "Product Hunt", 22, {}),
       ]),
    _c("Portcall", "portcall.sh",
       "Developer infrastructure for secure API gateways. Open-source core, self-serve cloud.",
       ["developer tools", "security", "infrastructure"], "Usage-based", "Berlin", 15, [
           ("Portcall open-sources its API gateway core", "launch", "Hacker News", 13, {}),
           ("Portcall hiring backend engineers", "hiring", "Lever", 20, {"open_roles": 4, "eng_roles": 3}),
       ]),
    _c("Ember Metrics", "embermetrics.io",
       "Usage-based observability for data teams. Developer-first, API-led.",
       ["developer tools", "data", "infrastructure"], "Usage-based", "Toronto", 18, [
           ("Ember Metrics announces API-first observability", "launch", "Company blog", 25, {}),
           ("Ember Metrics hiring solutions engineer", "hiring", "Greenhouse", 30, {"open_roles": 2}),
       ]),
]


def build_seed_signals() -> list[RawSignal]:
    raws: list[RawSignal] = []
    for c in COMPANIES:
        meta_base = {"sectors": c["sectors"], "business_model": c["business_model"],
                     "hq_city": c["hq_city"], "employee_count": c["employee_count"]}
        for title, kind, source, days, meta in c["signals"]:
            m = dict(meta_base)
            m.update(meta)
            raws.append(RawSignal(
                title=title, source_type="api" if source in {"Greenhouse", "Lever"} else "news",
                source_name=source, source_url=f"https://{c['domain']}",
                raw_text=f"{title}. {c['description']}",
                signal_kind=kind, company_name=c["name"], company_domain=c["domain"],
                company_description=c["description"], published_at=_ago(days), metadata=m))
    return raws


PEOPLE = {
    "Attestable AI": [("Maya Chen", "Co-founder & CEO", "founder"),
                      ("Devon Ruiz", "VP Engineering (ex-Datadog)", "executive")],
    "Aperture Health": [("Priya Natarajan", "Co-founder & CEO", "founder"),
                        ("Tom Becker", "Co-founder & CTO", "founder")],
    "Lexroom": [("Sarah Okonkwo", "Founder & CEO", "founder")],
    "Fathom Underwriting": [("James Whitfield", "Co-founder & CEO", "founder")],
}


# Starting pipeline state: as if the firm has been working the top of the list
# for a few weeks. Applied AFTER scoring so it is purely presentational and does
# not shift any score. Each note: (days_ago, sentiment, summary).
# stage values must be members of STAGES in main.py.
PIPELINE_STATE = {
    "Attestable AI": {
        "stage": "meeting_scheduled",
        "notes": [
            (2, "positive", "Intro call booked via Bessemer partner for next week. "
                            "Maya (CEO) responsive; deep on healthcare compliance. "
                            "Want ARR, NRR, and logo data before the call."),
            (9, "positive", "Strongest fit on the thesis: $14M Series A, live HIPAA "
                            "audit-evidence engine, and 5 enterprise AE reqs open."),
        ],
    },
    "Aperture Health": {
        "stage": "contacted",
        "notes": [
            (4, "positive", "Cold outreach sent to Priya. Hiring velocity is the "
                            "tell: 4 implementation-engineer reqs in a short window "
                            "reads as live enterprise deployments, not just funding."),
        ],
    },
    "Ledgerly": {
        "stage": "prioritized",
        "notes": [
            (6, "neutral", "Prioritized post-Series B. $40M round likely limits "
                           "near-term entry; keep warm and re-evaluate next raise."),
        ],
    },
    "Lexroom": {
        "stage": "prioritized",
        "notes": [
            (7, "neutral", "AmLaw 100 pilot is the signal to watch. Re-evaluate on "
                           "pilot-to-paid conversion before advancing."),
        ],
    },
    "Fathom Underwriting": {"stage": "watching", "notes": []},
    "Verano Insurance Tech": {"stage": "watching", "notes": []},
    "Quill Data": {
        "stage": "watching",
        "notes": [
            (5, "positive", "Top of the dev-infra thesis: OSS traction plus a new "
                            "self-serve usage-based cloud is the monetization catalyst."),
        ],
    },
}
