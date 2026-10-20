"""Concept lexicon used by the local-fallback provider for service tags and embeddings.

The vector is the L2-normalised count of concept mentions over a fixed concept order, so it is
deterministic and comparable across runs. It is a stand-in for Titan embeddings when no AWS
credentials are available; it is never presented as a Bedrock result.
"""

from __future__ import annotations

import math
import re

# Fixed order: the embedding dimension index of each concept. Append only (never reorder).
CONCEPTS: list[str] = [
    "service_desk",
    "desktop_device_support",
    "m365_admin",
    "networking",
    "cybersecurity",
    "cloud",
    "web_design",
    "seo",
    "hosting",
]

# Display labels, used to build canonical capability text from tags.
CONCEPT_LABELS: dict[str, str] = {
    "service_desk": "service desk",
    "desktop_device_support": "desktop/device support",
    "m365_admin": "Microsoft 365 administration",
    "networking": "networking",
    "cybersecurity": "cybersecurity",
    "cloud": "cloud services",
    "web_design": "web design",
    "seo": "SEO",
    "hosting": "web hosting",
}

PHRASES: dict[str, str] = {
    # service_desk
    "service desk": "service_desk",
    "help desk": "service_desk",
    "helpdesk": "service_desk",
    "user assistance": "service_desk",
    "user support": "service_desk",
    "end-user support": "service_desk",
    "it support": "service_desk",
    # desktop_device_support
    "device lifecycle": "desktop_device_support",
    "desktop": "desktop_device_support",
    "device support": "desktop_device_support",
    "device management": "desktop_device_support",
    "end-user computing": "desktop_device_support",
    # m365_admin
    "microsoft 365": "m365_admin",
    "m365": "m365_admin",
    "office 365": "m365_admin",
    "tenant administration": "m365_admin",
    # networking
    "network": "networking",
    "networking": "networking",
    "network support": "networking",
    "network cabling": "networking",
    "network installation": "networking",
    # cybersecurity
    "cybersecurity": "cybersecurity",
    "cyber security": "cybersecurity",
    "information security": "cybersecurity",
    # cloud
    "cloud": "cloud",
    "azure": "cloud",
    # web_design
    "web design": "web_design",
    "website design": "web_design",
    # seo
    "seo": "seo",
    "search engine optimisation": "seo",
    "search engine optimization": "seo",
    # hosting
    "hosting": "hosting",
    "wordpress hosting": "hosting",
}

# Longest phrases first so "network cabling" is one mention, not "network" + leftovers.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![a-z0-9])" + re.escape(p) + r"s?(?![a-z0-9])"), c)
    for p, c in sorted(PHRASES.items(), key=lambda kv: (-len(kv[0]), kv[0]))
]


def concept_counts(text: str) -> dict[str, int]:
    """Count non-overlapping concept mentions in text (case-insensitive)."""
    remaining = (text or "").lower()
    counts = dict.fromkeys(CONCEPTS, 0)
    for pattern, concept in _PATTERNS:
        def _consume(m: re.Match[str], concept: str = concept) -> str:
            counts[concept] += 1
            return " " * len(m.group(0))

        remaining = pattern.sub(_consume, remaining)
    return counts


def tags(text: str) -> list[str]:
    """Concepts mentioned in text, in the fixed concept order."""
    counts = concept_counts(text)
    return [c for c in CONCEPTS if counts[c] > 0]


def embed(text: str) -> list[float]:
    """L2-normalised concept-count vector (all zeros when no concept is mentioned)."""
    counts = concept_counts(text)
    vec = [float(counts[c]) for c in CONCEPTS]
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def capability_text_from_tags(concepts: list[str]) -> str:
    """Canonical capability text from tags.

    e.g. 'Service desk, desktop/device support, Microsoft 365 administration'.
    """
    text = ", ".join(CONCEPT_LABELS[c] for c in CONCEPTS if c in concepts)
    return text[:1].upper() + text[1:]
