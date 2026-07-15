"""
rigor.py

The trip "rigor tier" — a single ordinal band that expresses how much prep a
trip demands, derived from the trail's physical stats plus the requested
duration.  It turns the app's previously flat, always-on gear model into a
roughly-linear ramp: a flat 2-miler needs almost nothing; a committing day
needs the essentials; a multi-day outing needs full kit plus consumables.

Pure module — no DB / network / ingestion imports — so it's cheap to call per
candidate hike and trivial to unit-test.  Shared by:
  - GearGapAnalyzer  — casual tier suppresses the ten-essentials nag; multi-day
                       escalates shelter/sleep/consumables.
  - HikeSearchService — stamps each option card with its tier (the UI badge).
  - PromptBuilder    — adjusts the AI's tone per tier.

The band thresholds intentionally reuse the same signals as
ingestion.gear_inference.infer_gear_levels (Naismith duration, the alpine/
winter/technical flags, the DIFFICULT/EXPERT check) so the two never drift.
"""

from __future__ import annotations

RIGOR_TIERS = ["casual", "standard", "serious", "expedition"]

# Short, user-facing line per tier. Doubles as the casual "soft nudge" shown on
# a hike card and as a tone cue injected into the AI prompt.
TIER_BLURB: dict[str, str] = {
    "casual":     "Quick outing — water and good shoes and you're set.",
    "standard":   "A real half-day out — pack the essentials; there's a small chance the day runs long.",
    "serious":    "A committing day — come prepared for weather, navigation, and a long day on your feet.",
    "expedition": "Multi-day territory — full kit plus food and water for every day out.",
}

# On a casual trip these baseline "ten essentials" categories are demoted: a
# flat 2-mile stroll shouldn't flag "missing: first aid" as loudly as a 10-mile
# climb. GearGapAnalyzer suppresses gaps for these when the tier is casual and
# leans on TIER_BLURB["casual"] instead. (footwear/hydration are covered by that
# nudge; everything committing stays on from `standard` up.)
CASUAL_SUPPRESSED = frozenset({
    "first_aid", "navigation", "illumination", "hydration", "shell", "insulation",
})


def _duration_h(length_km: float, gain_m: float) -> float:
    """Naismith time estimate (hours), matching gear_inference._naismith."""
    return (length_km / 5.0) + (gain_m / 600.0)


def _diff_name(difficulty) -> str:
    """Upper-case difficulty name from a DifficultyLevel enum or a string."""
    if difficulty is None:
        return ""
    return (difficulty.name if hasattr(difficulty, "name") else str(difficulty)).upper()


def rigor_tier(
    length_km:     float,
    gain_m:        float,
    max_alt_m:     float = 0.0,
    difficulty=None,
    duration_days: int = 1,
    tags=None,
) -> str:
    """
    Classify a trip into one of RIGOR_TIERS.

    duration_days is the *requested* trip length — the single strongest signal:
    any overnight is expedition-tier regardless of trail size. For single-day
    trips the band comes from the trail's own commitment (Naismith time, gain,
    difficulty, and alpine/winter/technical terrain).
    """
    length_km     = float(length_km or 0.0)
    gain_m        = float(gain_m or 0.0)
    max_alt_m     = float(max_alt_m or 0.0)
    duration_days = int(duration_days or 1)
    tagset        = {t.lower() for t in (tags or [])}

    duration_h  = _duration_h(length_km, gain_m)
    diff        = _diff_name(difficulty)
    is_hard     = diff in {"DIFFICULT", "EXPERT", "HARD"}
    is_alpine   = max_alt_m > 2000
    is_winter   = max_alt_m > 1500 or bool(tagset & {"snow", "winter", "ice"})
    is_technical = max_alt_m > 2500 or "glacier" in tagset or bool(
        tagset & {"scramble", "via_ferrata"}
    )

    # Expedition — any overnight, or a trail simply too big to do in a day.
    if duration_days > 1 or duration_h > 10 or length_km > 20:
        return "expedition"

    # Serious — a committing single day.
    if is_hard or is_alpine or is_winter or is_technical or duration_h > 4.5 or gain_m > 600:
        return "serious"

    # Casual — genuinely trivial: short, flat, easy, low, no harsh terrain.
    easy_or_unknown = diff in {"", "EASY"}
    if easy_or_unknown and duration_h < 2 and gain_m < 250:
        return "casual"

    return "standard"


def tier_index(tier: str) -> int:
    """Ordinal rank of a tier (casual=0 … expedition=3), or -1 if unknown."""
    try:
        return RIGOR_TIERS.index(tier)
    except ValueError:
        return -1
