"""
feature_honesty.py

A deterministic belt-and-suspenders check for the destination-phase honesty rule
in PromptBuilder ("only credit a trail with a feature if that feature is in THAT
trail's Tags"). The prompt is the primary guard; at temperature 0.4 the model can
still assert a draw — "features a lake", "has a waterfall" — that appears on none
of the trails it's presenting. This module flags that case so it can be logged
(and, once its false-positive rate is measured against live Groq output, promoted
to a user-facing correction).

Pure module — no DB / Redis / Groq / HTTP — so it's cheap to call per turn and
unit-testable with no server (imports only the pure TripInputParser vocabulary).

Intentionally COARSE: it checks whether a claimed feature is absent from *every*
presented card, not whether it was cross-attributed to the wrong trail. That
whole-result check is the unambiguous, safe signal (the model naming a draw no
option has). It is *not* used to rewrite prose, because the honesty prompt tells
the model to disclose absence too ("no confirmed waterfall on this one, but…") —
that legitimate phrasing also contains the keyword, so an affirmative-vs-negative
distinction would be needed before mutating output.
"""

from __future__ import annotations

import re

from AI.TripInputParser import FEATURE_KEYWORD_MAP

# Concrete "draws" a user asks to see and would verify before committing to a
# drive. Deliberately excludes the descriptive terrain tags in
# FEATURE_KEYWORD_MAP (forest / lowland / montane / subalpine / seasonal /
# viewpoint) — those are either ever-present, or (like "view") so common in prose
# that scanning for them is pure noise.
VERIFIABLE_FEATURES: tuple[str, ...] = (
    "waterfall", "lake", "summit", "canyon", "glacier",
    "meadow", "beach", "cave", "hot_spring", "river",
)

# Prose-claim detectors: any keyword phrase for the feature, on word boundaries.
_CLAIM_RES: dict[str, re.Pattern] = {
    feat: re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in FEATURE_KEYWORD_MAP[feat]) + r")\b",
        re.IGNORECASE,
    )
    for feat in VERIFIABLE_FEATURES
}

# A feature is "backed" by a card whose tag equals the canonical key or any of its
# synonym keywords (so a `stream`-tagged trail backs a "river" mention, and
# `falls`/`cascade` back "waterfall") — same vocabulary, single-sourced.
_BACKING_TAGS: dict[str, frozenset[str]] = {
    feat: frozenset({feat, *(k.lower() for k in FEATURE_KEYWORD_MAP[feat])})
    for feat in VERIFIABLE_FEATURES
}


def unbacked_feature_claims(prose: str, cards: list[dict]) -> list[str]:
    """Canonical features the prose mentions that NO presented card carries.

    prose  — the assistant's destination-phase reply text.
    cards  — the option cards being rendered (dicts with a "tags" list).

    Returns the sorted list of canonical feature keys that were claimed but are
    absent from every card's tags. Empty when there are no cards or no claims.
    """
    if not prose or not cards:
        return []

    # Redact each trail's NAME from the prose before scanning. A trail called
    # "Avery Creek" or "Lake Johnson Trail" would otherwise trip the river/lake
    # detector on its name alone — exactly the "never infer a feature from the
    # NAME" case the honesty rule targets. Only prose that names a feature
    # *outside* a trail name should count as a claim.
    scan = prose
    present: set[str] = set()
    for card in cards:
        name = str(card.get("name") or "").strip()
        if name:
            scan = re.sub(re.escape(name), " ", scan, flags=re.IGNORECASE)
        for tag in (card.get("tags") or []):
            present.add(str(tag).lower())

    unbacked: list[str] = []
    for feat, claim_re in _CLAIM_RES.items():
        if claim_re.search(scan) and not (_BACKING_TAGS[feat] & present):
            unbacked.append(feat)
    return sorted(unbacked)
