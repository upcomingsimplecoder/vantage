"""Text utilities: normalization, domain canonicalization, hashing, cheap
embeddings, and fuzzy matching. These power entity resolution.

The canonical key for a company is its ROOT DOMAIN:
strip scheme, www, subdomains, and paths so acme.com == www.acme.com/careers.
"""
from __future__ import annotations

import hashlib
import math
import re
from urllib.parse import urlparse

_LEGAL_SUFFIXES = {
    "inc", "inc.", "llc", "l.l.c", "ltd", "ltd.", "limited", "corp", "corp.",
    "corporation", "co", "co.", "company", "gmbh", "ag", "sa", "srl", "bv",
    "plc", "labs", "technologies", "technology", "software", "systems", "ai",
}

# Common multi-tenant / free hosts we should NOT treat as a company's own domain.
_GENERIC_HOSTS = {
    "github.com", "github.io", "linkedin.com", "twitter.com", "x.com",
    "medium.com", "producthunt.com", "ycombinator.com", "notion.site",
    "substack.com", "youtube.com", "crunchbase.com", "wikipedia.org",
    "google.com", "facebook.com", "angel.co", "wellfound.com",
}


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and legal suffixes, collapse whitespace."""
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s&.-]", " ", s)
    tokens = [t for t in re.split(r"\s+", s) if t]
    while tokens and tokens[-1].strip(".") in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens).strip()


def canonical_domain(url_or_domain: str | None) -> str | None:
    """Reduce any URL/host to a canonical registrable-ish root domain."""
    if not url_or_domain:
        return None
    raw = url_or_domain.strip().lower()
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    host = urlparse(raw).netloc or urlparse(raw).path
    host = host.split("@")[-1].split(":")[0]  # strip creds/port
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return None
    if host in _GENERIC_HOSTS:
        return None
    # Reduce sub.sub.acme.co.uk -> acme.co.uk ; sub.acme.com -> acme.com
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def content_hash(source_url: str | None, title: str, text: str) -> str:
    basis = f"{(source_url or '').strip()}|{title.strip()}|{normalize_name(text)[:1000]}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def domain_from_text(text: str) -> str | None:
    """Best-effort extraction of a company domain mentioned in free text."""
    m = re.search(r"\b([a-z0-9][a-z0-9-]{1,63}\.(?:com|io|ai|co|dev|app|xyz|tech|health|so|net|org))\b",
                  text.lower())
    if not m:
        return None
    return canonical_domain(m.group(1))


# Fuzzy string similarity (token + character)
def _bigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def similarity(a: str, b: str) -> float:
    """Dice coefficient over character bigrams of normalized names. 0..1."""
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ba, bb = _bigrams(a), _bigrams(b)
    inter = len(ba & bb)
    return 2 * inter / (len(ba) + len(bb)) if (ba or bb) else 0.0


# Cheap deterministic embedding (hashed bag-of-words)
# In production this is text-embedding-3-small into pgvector. Here we use a
# 128-dim hashed TF vector so semantic-ish search works offline & deterministically.
_EMBED_DIM = 128
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed(text: str) -> list[float]:
    vec = [0.0] * _EMBED_DIM
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if len(tok) < 3:
            continue
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % _EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))  # inputs already unit-normalized
