# Services/HikeSearchService.py
#
# Bridges TripIntent → HikeService.
#
# Phase 1  Hard filter  — passes column-backed and tag-array constraints to
#                          HikeService.search_hikes(), which calls the repo.
# Phase 2  Soft rank    — scores the surviving candidates in Python by counting
#                          how many preferred_tags each hike contains.
# Phase 3  format_for_context() — serialises the top-N results into the string
#                          injected into the Groq system prompt.  When
#                          gear_analyses is supplied (dict of hike_id →
#                          list[GearGap]), a one-line gear-readiness note is
#                          appended under each option so Groq can surface
#                          compatibility at the point of trail selection.
#
# Fallback search (find_hikes_with_fallback)
#   When required_tags produce 0 results, strips the failing tags and re-runs
#   with their alternatives promoted to preferred_tags (soft boost).  Returns a
#   SearchResult that carries substitution metadata so format_for_context() can
#   prepend a plain-text header — the LLM narrates the substitution, it does
#   not decide it.
#
# Concept expansion (CONCEPT_EXPANSIONS)
#   Some user-facing terms span multiple database tags.  "Water feature" is the
#   canonical example: the DB has river, lake, pond, stream, waterfall as
#   separate tags, but users say "water feature" to mean any of them.
#   CONCEPT_EXPANSIONS maps these terms → their constituent tags, which are
#   injected into preferred_tags so the scorer gives credit for ANY of them
#   rather than requiring ALL (which is what required_tags would enforce).
#   This means "water feature" never hard-filters trails but strongly boosts
#   any trail that touches water.
#
# Priority / champion tags (TripIntent.priority_tags)
#   When the user explicitly emphasizes a feature ("I really want a water
#   feature"), TripInputParser promotes it into priority_tags. Unlike a plain
#   preferred tag (soft score boost), a priority tag hard-filters the scored
#   candidate list down to matches when any exist — the champion feature wins
#   outright instead of being diluted into the same scoring pool as every
#   other preference. If nothing matches, the full scored list is left as-is
#   and the gap is surfaced honestly via unmatched_concept_tags below, rather
#   than silently returning zero hikes.
#
# This file knows about TripIntent.  HikeService/HikeRepo do NOT.

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, List, Optional, Tuple

from AI.rigor import rigor_tier, TIER_BLURB
from PyObjects.Hike import DifficultyLevel, Hike
from Services.HikeService import HikeService
from trip_metrics import MAX_KM_PER_DAY

if TYPE_CHECKING:
    from AI.TripInputParser import TripIntent

# Tags in TripIntent.required_tags that map to dedicated boolean columns
# instead of the tags[] array.  Strip these before building the @> query.
_COLUMN_TAGS: frozenset[str] = frozenset({"can_camp"})

# Preferred tags that are INFERRED trail descriptors (length bucket, gain tier,
# altitude/terrain tier, season) rather than user-requested FEATURES. They ride
# into preferred_tags from the activity/difficulty defaults — e.g. a bare "hikes
# near me" injects short/half_day/full_day via the day_hike default, and a
# difficulty hint injects gain tiers. A returned set that doesn't happen to
# include one of these is NOT a data gap worth disclosing: surfacing "no
# full_day trails" as the reason for a "wooded" search made the model answer a
# question nobody asked and drop the real request. Excluded from
# unmatched_preferred_tags so only genuine feature gaps get a DATA NOTE.
_NON_FEATURE_PREFERRED_TAGS: frozenset[str] = frozenset({
    # length buckets
    "short", "half_day", "full_day", "overnight", "multi_day",
    # elevation-gain tiers
    "flat", "gentle_gain", "moderate_gain", "high_gain", "very_high_gain",
    # altitude / terrain tiers
    "lowland", "montane", "subalpine", "alpine",
    # season windows + permits
    "year_round", "summer_only", "spring_fall", "seasonal", "permits_required",
})

DEFAULT_RADIUS_KM: float = 150.0
EXPANDED_RADIUS_KM: float = 350.0
# Distance (km) at which the point-search proximity bonus decays to zero. Kept
# much tighter than the *search* radius (DEFAULT_RADIUS_KM) on purpose: when the
# user names a specific place ("Linville Gorge"), a trail 2 km away should rank
# decisively above one 34 km away. Normalizing the bonus over the full 150 km
# search radius made 2 km vs 34 km nearly indistinguishable (0.95 vs 0.77 of the
# weight), so tag-rich long trails that merely pass nearby still won. The search
# still *returns* trails out to DEFAULT_RADIUS_KM — this only shapes ranking.
POINT_PROXIMITY_FALLOFF_KM: float = 30.0

# Weight of the length-proximity term for an approximate-length request ("about
# 3 miles"). Was effectively 0.3 (the helper default), which is ~10x smaller than
# the 3.0 point-proximity weight — so a correct-length trail could never overcome
# a nearer-but-shorter one and "about 3 miles near me" returned ~2-mile trails. At
# 1.0 a perfect-length match is worth ~10 km of proximity-equivalence: enough to
# reorder near-but-wrong-length results without overriding proximity outright.
# Tunable — raise it if length should matter more, lower it if it over-pulls far
# trails.
LENGTH_PROXIMITY_WEIGHT: float = 1.0
_DIFFICULTY_HINT_TO_ENUM: dict[str, DifficultyLevel] = {
    "easy":     DifficultyLevel.EASY,
    "moderate": DifficultyLevel.MODERATE,
    "hard":     DifficultyLevel.DIFFICULT,
}

# ── Concept expansion ─────────────────────────────────────────────────────────
#
# Maps user-facing concept terms to the set of DB tags they encompass.
# These are injected into preferred_tags (soft boost) rather than
# required_tags (hard filter) so that:
#   - A trail with ANY matching tag scores highly
#   - A trail with NO matching tag is still surfaced if nothing better exists
#
# Concepts should also be checked in required_tags and demoted to preferred
# if found there, since they can't be satisfied by a single-tag @> query.

CONCEPT_EXPANSIONS: dict[str, list[str]] = {
    # Water. `stream` is a distinct tag from `river` (ingestion splits
    # waterway=stream from waterway=river|canal) — most moving water in the DB is
    # a stream, so it must be a constituent here or water searches miss the bulk
    # of near-creek trails.
    "water_feature": ["river", "stream", "lake", "waterfall"],
    "water":         ["river", "stream", "lake", "waterfall"],
    "waterway":      ["river", "stream", "lake"],
    # Views / elevation
    "view":          ["viewpoint", "summit", "ridge"],
    "scenic":        ["viewpoint", "ridge", "lake", "summit", "meadow"],
    # Family-friendly terrain — all four constituents are real DB tags today
    "family":        ["flat", "short", "lowland", "year_round"],
    # Season / access window — consolidates the seasonal/spring_fall overlap
    "seasonal":      ["seasonal", "spring_fall"],
    # Wildflowers aren't independently tracked anywhere in the taxonomy.
    # Intentionally empty — this guarantees the concept is ALWAYS reported
    # via unmatched_concept_tags whenever requested, instead of silently
    # succeeding because a co-mentioned "meadow" tag happened to match.
    "wildflower":    [],
}

# ── Fallback tag map ──────────────────────────────────────────────────────────
#
# When a required tag returns 0 results, the alternatives listed here are
# injected into preferred_tags so they boost scoring without hard-filtering.
# Keep entries concrete and OSM-plausible; broad catch-alls dilute the ranking.
#
# Order within each list is preference order (most similar first).

TAG_FALLBACKS: dict[str, list[str]] = {
    # non-DB tags — always need a substitute
    "waterfall":   ["river", "lake"],
    "summit":      ["viewpoint", "ridge", "very_high_gain"],
    "cave":        ["historic", "montane"],
    "beach":       ["lake", "river"],
    "glacier":     ["subalpine", "very_high_gain", "high_gain"],
    "canyon":      ["river", "ridge"],
    "hot_spring":  ["river", "lake"],
    "technical":   ["ridge", "summit", "subalpine"],
    "forest":      ["montane", "lowland"],
    "desert":      ["montane", "ridge"],

    # real DB tags — reachable as required_tags for the first time after
    # Patch 1; still need a fallback if a given radius has zero coverage
    "lake":        ["river", "waterfall"],
    "viewpoint":   ["ridge", "summit"],
    "historic":    ["montane"],
    "meadow":      ["subalpine", "lowland"],
    "ridge":       ["summit", "viewpoint", "montane"],
    "river":       ["stream", "lake", "waterfall"],
    "stream":      ["river", "waterfall", "lake"],
    "montane":     ["subalpine", "ridge"],
    "subalpine":   ["summit", "ridge", "montane"],
    "lowland":     ["flat", "meadow"],
}

# ── Search result wrapper ─────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """
    Returned by find_hikes_with_fallback().

    scored               — ranked (Hike, score) pairs, same shape as
                           find_hikes_for_intent() output.
    failed_required_tags — tags the user asked for that yielded 0 results.
    substituted_tags     — alternatives that were soft-boosted in the retry.
    is_fallback          — True only when the retry found results; False when
                           the primary search succeeded OR both passes returned
                           nothing (so callers can distinguish "fallback hit"
                           from "genuinely empty area").
    requested_concept_tags — concept terms (e.g. "water_feature") found in the
                             intent that were expanded into constituent DB tags.
    unmatched_concept_tags — subset of the above where NONE of the returned
                             hikes have any of the constituent DB tags.  When
                             non-empty, format_for_context() prepends a note so
                             Groq can honestly tell the user the feature wasn't
                             found rather than hallucinating it into the tags.
    unmatched_preferred_tags — same idea as unmatched_concept_tags, but for
                           plain preferred_tags (viewpoint, ridge, summit,
                           historic, etc.) that never went through
                           CONCEPT_EXPANSIONS. These previously had no
                           disclosure mechanism at all, which is the root
                           cause of Groq hallucinating justifications for
                           tags that don't exist on any returned hike.
    """
    scored:                  List[Tuple[Hike, int]]
    failed_required_tags:    List[str] = field(default_factory=list)
    substituted_tags:        List[str] = field(default_factory=list)
    is_fallback:              bool      = False
    requested_concept_tags:  List[str] = field(default_factory=list)
    unmatched_concept_tags:  List[str] = field(default_factory=list)
    unmatched_preferred_tags: List[str] = field(default_factory=list)  # NEW — Cause 2
    difficulty_hint:          Optional[str] = None
    radius_expanded:          bool = False 
    difficulty_mismatch:      bool = False

class HikeSearchService:
    def __init__(self, hike_service: HikeService) -> None:
        self.hike_service = hike_service

    # ── Public API ─────────────────────────────────────────────────────────────

    def find_hikes_for_intent(
        self,
        intent: "TripIntent",
        top_n: int = 5,
        max_distance_km: float = DEFAULT_RADIUS_KM,
    ) -> List[Tuple[Hike, int]]:
        """
        Phase 1 + Phase 2.

        Returns a list of (Hike, match_score) tuples, sorted by score
        descending then distance ascending, truncated to top_n.

        match_score = number of preferred_tags present on the hike
                    + difficulty proximity bonus.

        Concept expansion runs first: any concept term in required_tags or
        preferred_tags is replaced by its constituent DB tags so "water
        feature" matches river, lake, pond, stream, and waterfall.

        If intent.priority_tags is set, the sorted list is hard-filtered down
        to hikes matching at least one priority tag (or its concept-expanded
        constituents) — but only when at least one candidate matches. If none
        match, the full sorted list is returned unchanged so the caller can
        disclose the gap rather than return zero hikes.
        """
        can_camp, tag_required = self._split_required_tags(intent.required_tags)

        tag_required, preferred_expanded = _expand_concept_tags(
            tag_required,
            list(getattr(intent, "preferred_tags", None) or []),
        )

        permits_required: Optional[bool] = False if intent.avoid_permits else None

        # Per-day feasibility ceiling: when the user named no explicit max length,
        # cap the trail at what fits in the trip's day count (MAX_KM_PER_DAY per
        # day) so a 182 km through-trail isn't offered for a 1- or 2-day trip. A
        # user-typed ceiling always wins; setting intent.max_km_per_day_cap = None
        # disables the derivation (find_hikes_with_fallback's last-resort pass).
        max_length_km = getattr(intent, "max_length_km", None)
        cap_per_day = getattr(intent, "max_km_per_day_cap", MAX_KM_PER_DAY)
        if max_length_km is None and cap_per_day:
            max_length_km = cap_per_day * max(1, int(getattr(intent, "duration_days", 1) or 1))

        candidates: List[Hike] = self.hike_service.search_hikes(
            user_lat=intent.lat,
            user_lon=intent.lng,
            max_distance_km=max_distance_km,
            min_length_km=getattr(intent, "min_length_km", None),   # ← NEW: floor
            max_length_km=max_length_km,
            can_camp=can_camp,
            permits_required=permits_required,
            required_tags=tag_required or None,
            region=getattr(intent, "region_tag", None),   # ← was silently dropped before
            state=getattr(intent, "state", None),          # ← NEW
        )
        if intent.difficulty_hint:
            target_diff = _DIFFICULTY_HINT_TO_ENUM.get(intent.difficulty_hint)
            if target_diff is not None:
                exact_difficulty = [h for h in candidates if h.difficulty == target_diff]
                if exact_difficulty:
                    candidates = exact_difficulty
        # Point-scoped queries ("near Raleigh", "near me") should be dominated
        # by distance — a trail 150mi away shouldn't outrank one 10 minutes
        # away just because it has one extra matching tag. Region-scoped
        # queries (a whole state/mountain range) keep the original light-touch
        # weighting, since "close to the state centroid" isn't a meaningful
        # signal there.
        is_point = getattr(intent, "destination_type", "point") == "point"
        proximity_weight = 3.0 if is_point else 0.3
        # Normalize the point-search bonus over a tight radius so a trail right at
        # the named place decisively outranks one 30+ km away; region searches
        # keep decaying over the full search radius (centroid-closeness is weak
        # signal there). See POINT_PROXIMITY_FALLOFF_KM.
        proximity_falloff = POINT_PROXIMITY_FALLOFF_KM if is_point else max_distance_km

        scored: List[Tuple[Hike, float]] = [
            (
                hike,
                _tag_match_score(set(hike.tags or []), preferred_expanded)
                + _difficulty_score(hike, intent.difficulty_hint)
                + _proximity_bonus(hike, proximity_falloff, weight=proximity_weight)
                + _length_proximity_bonus(hike, getattr(intent, "target_length_km", None), weight=LENGTH_PROXIMITY_WEIGHT),   # ← NEW
            )
            for hike in candidates
        ]

        # Primary ranking dimension (from TripIntent.primary_priority, decided by
        # the parser's rules or TripChat's hybrid Groq step). When set, it becomes
        # the PRIMARY sort key and the composite score is only the tiebreak, so a
        # request that's really "about" distance orders by closeness-to-target and
        # one that's "about" a feature puts feature-matching trails first — while
        # never collapsing to a single dimension (score/geo still break ties).
        primary = getattr(intent, "primary_priority", None)
        target  = getattr(intent, "target_length_km", None)
        scored.sort(key=lambda pair: _primary_sort_key(pair, primary, target))

        # ── Champion / priority filter ──────────────────────────────────────
        # A feature the user explicitly emphasized ("I really want a water
        # feature") should win outright over every other soft preference —
        # not just nudge the score like everything in preferred_tags does.
        # Hard-filter to matches when any exist; if none exist, leave the
        # full scored list as-is so find_hikes_with_fallback's
        # unmatched_concept_tags tracking can disclose the gap honestly
        # instead of silently returning zero hikes.
        priority_tags = list(getattr(intent, "priority_tags", None) or [])
        if priority_tags:
            expanded_priority: set[str] = set()
            for tag in priority_tags:
                expanded_priority.update(CONCEPT_EXPANSIONS.get(tag, [tag]))
            matches = [
                pair for pair in scored
                if expanded_priority & set(pair[0].tags or [])
            ]
            if matches:
                scored = matches

        return scored[:top_n]
    def find_hikes_with_fallback(
        self,
        intent: "TripIntent",
        top_n: int = 5,
        max_distance_km: float = DEFAULT_RADIUS_KM,
    ) -> SearchResult:
        """
        Wraps find_hikes_for_intent() with a single tag-substitution retry.

        Pass 1 — run the full intent as-is.
        Pass 2 — if pass 1 returns nothing and any required_tags are in
                 TAG_FALLBACKS, retry with:
                   • failing tags removed from required_tags (hard filter lifted)
                   • their alternatives appended to preferred_tags (soft boost)

        Concept tracking: after each pass, checks whether any returned hike
        has constituent tags for each requested concept (e.g. river/lake/pond
        for "water_feature").  If none do, populates
        SearchResult.unmatched_concept_tags so format_for_context() can prepend
        a disclosure note and Groq can tell the user the truth instead of
        hallucinating matching tags.
        """
        all_intent_tags = (
            list(getattr(intent, "required_tags", None) or [])
            + list(getattr(intent, "preferred_tags", None) or [])
            + list(getattr(intent, "priority_tags", None) or [])
        )
        requested_concepts = [t for t in all_intent_tags if t in CONCEPT_EXPANSIONS]

        def _unmatched(scored_pairs: List[Tuple[Hike, int]]) -> List[str]:
            all_result_tags: set[str] = set()
            for hike, _ in scored_pairs:
                all_result_tags.update(hike.tags or [])
            return [
                concept for concept in requested_concepts
                if not any(t in all_result_tags for t in CONCEPT_EXPANSIONS.get(concept, []))
            ]

        # ── Pass 1: primary search ─────────────────────────────────────────
        scored = self.find_hikes_for_intent(intent, top_n, max_distance_km)

        # ── Pass 1.5: radius expansion for hard-difficulty geocode gaps ─────
        # "Hard"/high-gain queries often geocode to a state centroid (e.g.
        # NC → Raleigh, flat Piedmont) well outside the default radius from
        # where the qualifying mountain trails actually live. A single radius
        # bump fixes the common case without needing region-aware geocoding.
        radius_expanded = False
        search_radius = max_distance_km

        if max_distance_km < EXPANDED_RADIUS_KM:
            has_required_features = bool(set(intent.required_tags or []) - _COLUMN_TAGS)
            difficulty_gap = (
                intent.difficulty_hint is not None
                and _difficulty_unmatched(scored, intent.difficulty_hint)
            )
            tag_gap = has_required_features and len(scored) < top_n

            if not scored or difficulty_gap or tag_gap:
                wider = self.find_hikes_for_intent(intent, top_n, EXPANDED_RADIUS_KM)
                wider_is_better = (
                    (not scored and wider)
                    or (difficulty_gap and wider and not _difficulty_unmatched(wider, intent.difficulty_hint))
                    or (tag_gap and len(wider) > len(scored))
                )
                if wider_is_better:
                    scored = wider
                    search_radius = EXPANDED_RADIUS_KM
                    radius_expanded = True

        if scored:
            return SearchResult(
                scored                    = scored,
                requested_concept_tags    = requested_concepts,
                unmatched_concept_tags    = _unmatched(scored),
                unmatched_preferred_tags  = _get_unmatched_preferred_tags(
                    scored, intent.preferred_tags, requested_concepts
                ),
                difficulty_hint           = intent.difficulty_hint,
                radius_expanded           = radius_expanded,
                difficulty_mismatch       = _difficulty_unmatched(scored, intent.difficulty_hint),
            )

        # ── Pass 2: tag-substitution fallback ──────────────────────────────
        # Uses search_radius (still expanded if 1.5 ran but came up empty,
        # so a hard-difficulty query gets one combined wide-radius +
        # tag-substitution attempt rather than two separate narrow ones).
        if intent.difficulty_hint == "hard" and max_distance_km < EXPANDED_RADIUS_KM:
            search_radius = EXPANDED_RADIUS_KM

        fallback_map: dict[str, list[str]] = {
            tag: TAG_FALLBACKS[tag]
            for tag in intent.required_tags
            if tag not in _COLUMN_TAGS and tag in TAG_FALLBACKS
        }

        if not fallback_map:
            # No substitutable tags left to try — but the empty result may be the
            # derived per-day ceiling, not the tags. Relax the cap as a last resort
            # before giving up, so a sparse region returns something.
            relaxed = self._search_uncapped(intent, intent, top_n, search_radius)
            return SearchResult(
                scored                    = relaxed,
                requested_concept_tags    = requested_concepts,
                unmatched_concept_tags    = _unmatched(relaxed) if relaxed else requested_concepts,
                unmatched_preferred_tags  = _get_unmatched_preferred_tags(
                    relaxed, intent.preferred_tags, requested_concepts
                ),
                difficulty_hint           = intent.difficulty_hint,
                radius_expanded           = search_radius != max_distance_km,
                difficulty_mismatch       = _difficulty_unmatched(relaxed, intent.difficulty_hint),
            )

        failed_tags     = list(fallback_map.keys())
        substitute_tags = [t for alts in fallback_map.values() for t in alts]

        fallback_intent = SimpleNamespace(
            lat               = intent.lat,
            lng               = intent.lng,
            required_tags     = [t for t in intent.required_tags if t not in fallback_map],
            preferred_tags    = list(getattr(intent, "preferred_tags", None) or []) + substitute_tags,
            priority_tags     = list(getattr(intent, "priority_tags", None) or []),
            difficulty_hint   = intent.difficulty_hint,
            min_length_km     = getattr(intent, "min_length_km", None),      # ← NEW: floor
            max_length_km     = getattr(intent, "max_length_km", None),
            target_length_km  = getattr(intent, "target_length_km", None),   # ← NEW
            duration_days     = getattr(intent, "duration_days", None),       # ← per-day cap
            avoid_permits     = intent.avoid_permits,
            region_tag        = getattr(intent, "region_tag", None),
            state             = getattr(intent, "state", None),
        )

        fallback_scored = self.find_hikes_for_intent(
            fallback_intent, top_n, search_radius
        )
        if not fallback_scored:
            fallback_scored = self._search_uncapped(intent, fallback_intent, top_n, search_radius)

        return SearchResult(
            scored                    = fallback_scored,
            failed_required_tags      = failed_tags,
            substituted_tags          = substitute_tags,
            is_fallback                = bool(fallback_scored),
            requested_concept_tags    = requested_concepts,
            unmatched_concept_tags    = _unmatched(fallback_scored),
            unmatched_preferred_tags  = _get_unmatched_preferred_tags(
                fallback_scored, intent.preferred_tags, requested_concepts
            ),
            difficulty_hint            = intent.difficulty_hint,
            radius_expanded            = search_radius != max_distance_km,
            difficulty_mismatch        = _difficulty_unmatched(fallback_scored, intent.difficulty_hint),
        )

    def _search_uncapped(self, gate_intent, source, top_n, search_radius):
        """Last-resort retry with the per-day distance ceiling disabled.

        Only fires when the ceiling was *derived* (the user typed no explicit max)
        — a user's own max is never overridden. Lets a sparse region return trails
        longer than the reasonable per-day cap rather than nothing; the itinerary
        auto-extends the day count for whatever the user then selects.
        """
        if getattr(gate_intent, "max_length_km", None) is not None:
            return []
        prev = getattr(source, "max_km_per_day_cap", MAX_KM_PER_DAY)
        source.max_km_per_day_cap = None
        try:
            return self.find_hikes_for_intent(source, top_n, search_radius)
        finally:
            source.max_km_per_day_cap = prev

    @staticmethod
    def _format_state_label(state: Optional[str]) -> Optional[str]:
        """
        "NC".title() → "Nc" (str.title() only capitalizes the first letter of
        each word, lowercasing the rest) — 2-letter state codes need to stay
        upper. Underscore-joined region-style values ("blue_ridge") still get
        the word-title treatment.
        """
        if not state:
            return None
        return state.upper() if len(state) == 2 and state.isalpha() else state.replace("_", " ").title()

    def format_hike_list(
    self,
    scored: List[Tuple[Hike, float]],
    gear_analyses: Optional[dict] = None,
) -> str:
        """
        Pure numbered hike list — trail stats + optional gear-check line, no
        DATA NOTE or substitution headers. This is the exact text trip_chat.py
        appends after Groq's prose response (Bug 3 fix): Groq is no longer
        asked to retype this block itself, so there's nothing for it to
        truncate mid-list or restart numbering on. format_for_context() below
        calls this internally too, so the two can never drift out of sync.
        """
        lines: List[str] = []
        for i, (hike, _score) in enumerate(scored, start=1):
            tags_str    = ", ".join(hike.tags or [])
            dist        = getattr(hike, "distance_km", None)
            dist_part   = f", {dist:.0f} km away" if dist is not None else ""
            state_part  = f", {self._format_state_label(hike.state)}" if hike.state else ""
            camp_part   = ", camping available" if hike.can_camp else ""
            permit_part = ", permit required" if hike.permits_required else ""

            difficulty_str = (
                hike.difficulty.name.title()
                if hasattr(hike.difficulty, "name")
                else str(hike.difficulty).title()
            )

            lines.append(
                f"{i}. {hike.name}: "
                f"{hike.length_km} km, {difficulty_str}, "
                f"Gain: {hike.elevation_gain_m} m"
                f"{dist_part}"
                f"{state_part}"
                f"{camp_part}"
                f"{permit_part}"
                f", Tags: [{tags_str}]"
            )

            if gear_analyses is not None:
                gaps = gear_analyses.get(str(hike.id), [])
                gear_line = _summarise_gaps(gaps)
                lines.append(f"   Gear check: {gear_line}")

        return "\n".join(lines)

    def to_option_cards(
        self,
        scored: List[Tuple[Hike, float]],
        gear_analyses: Optional[dict] = None,
        duration_days: int = 1,
        anchor_label: Optional[str] = None,
    ) -> List[dict]:
        """
        Structured, JSON-serialisable equivalent of format_hike_list(), for the
        frontend to render as selectable option cards/buttons instead of a
        plain-text list. `index` is 1-based and matches the number
        PhaseController.extract_hike_selection() expects when the frontend
        sends the user's click back as a chat message (e.g. "2").

        `rigor_tier` (casual/standard/serious/expedition) is stamped on each card
        so the UI can render a prep-level badge; it reflects the requested
        duration, so an overnight request lifts every card to expedition.

        `anchor_label` names what `distance_km` is measured from (the searched
        place, e.g. "Linville Gorge", or "you" for a near-me search) so the UI
        can render "8 km from Linville Gorge" instead of an ambiguous "8 km
        away". Passed straight through as `distance_anchor`; None omits it.
        """
        cards: List[dict] = []
        for i, (hike, _score) in enumerate(scored, start=1):
            difficulty_str = (
                hike.difficulty.name.title()
                if hasattr(hike.difficulty, "name")
                else str(hike.difficulty).title()
            )
            tier = rigor_tier(
                length_km     = hike.length_km,
                gain_m        = hike.elevation_gain_m,
                max_alt_m     = getattr(hike, "max_altitude_m", 0),
                difficulty    = hike.difficulty,
                duration_days = duration_days,
                tags          = hike.tags,
            )
            cards.append({
                "index":             i,
                "name":              hike.name,
                "length_km":         hike.length_km,
                "difficulty":        difficulty_str,
                "elevation_gain_m":  hike.elevation_gain_m,
                "distance_km":       getattr(hike, "distance_km", None),
                "distance_anchor":   anchor_label,
                "state":             self._format_state_label(hike.state),
                "can_camp":          bool(hike.can_camp),
                "permits_required":  bool(hike.permits_required),
                "tags":              list(hike.tags or []),
                "rigor_tier":        tier,
                "gear_summary":      _summarise_gaps((gear_analyses or {}).get(str(hike.id), []), tier),
            })
        return cards
    def format_for_context(
        self,
        scored: List[Tuple[Hike, float]],
        gear_analyses: Optional[dict] = None,   # hike_id (str) → list[GearGap]
        search_result: Optional[SearchResult] = None,
    ) -> str:
        """
        Phase 3 helper.

        Serialises ranked hikes into a structured string for Groq context
        injection.  When gear_analyses is provided, appends a one-line
        gear-readiness note under each hike.

        When search_result is a fallback hit, prepends a substitution header
        so Groq knows to explain what was swapped and why.
        """
        lines: List[str] = []

        # ── Substitution header (fallback only) ────────────────────────────
        if search_result and search_result.is_fallback:
            failed_str = ", ".join(search_result.failed_required_tags)
            sub_str    = ", ".join(search_result.substituted_tags)
            lines.append(f"[No hikes with: {failed_str}]")
            lines.append(f"[Showing hikes with: {sub_str}]")
            lines.append("")

        # ── Unmatched concept disclosure ───────────────────────────────────
        # Fires when concept expansion ran (e.g. water_feature → river/lake/pond)
        # but none of the returned hikes have ANY of those constituent tags.
        # Groq reads this note and tells the user honestly instead of inventing
        # fake tags like "water_feature" in its output.
        #
        # Phrased explicitly as a database/data-coverage fact rather than a
        # search miss — the goal is for the user to read this as "the data
        # doesn't exist" rather than "the AI couldn't find it." Also tells
        # Groq to state it once, not hedge per-trail.
        if search_result and (
            search_result.unmatched_concept_tags
            or search_result.unmatched_preferred_tags
            or getattr(search_result, "difficulty_mismatch", False)
        ):
            all_unmatched = search_result.unmatched_concept_tags + search_result.unmatched_preferred_tags
            names = ", ".join(c.replace("_", " ") for c in all_unmatched)
            diff  = search_result.difficulty_hint
            pivot = ""
            if diff == "moderate":
                pivot = " Ask the user if they'd like to try easy trails instead."
            elif diff == "hard":
                pivot = " Ask the user if they'd like to try moderate or easy trails instead."

            if all_unmatched:
                lines.append(
                    f"[DATA NOTE: no trails tagged '{names}' match the current filters "
                    f"(difficulty={diff or 'any'}) in this area. This is a data gap, not a search error."
                    f"{pivot} If the user adjusts difficulty, a new SEARCH_REFINE will run — "
                    f"do NOT say 'nothing else to find.' State the gap once, then offer the pivot.]"
                )
            elif getattr(search_result, "difficulty_mismatch", False):
                lines.append(
                    f"[DATA NOTE: no trails at '{diff}' difficulty were found within range. "
                    f"The options below are the closest available matches overall, NOT '{diff}' "
                    f"matches — do not describe them as '{diff}' or imply they satisfy that request. "
                    f"State this plainly once.]"
                )

            # ── No results (either branch above) ────────────────────────────
            if not scored:
                lines.append("No matching trails found near this destination.")
                return "\n".join(lines)

        # ── Hike list ──────────────────────────────────────────────────────
        lines.append(self.format_hike_list(scored, gear_analyses))
        return "\n".join(lines)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _split_required_tags(
        required_tags,
    ) -> Tuple[Optional[bool], List[str]]:
        required_tags = list(required_tags or [])
        can_camp: Optional[bool] = True if "can_camp" in required_tags else None
        tag_required = [t for t in required_tags if t not in _COLUMN_TAGS]
        return can_camp, tag_required


# ── Concept expansion helper ──────────────────────────────────────────────────
def _length_proximity_bonus(hike: Hike, target_length_km: Optional[float], weight: float = 0.3) -> float:
    """
    Soft bonus for approximate-distance requests ("around 3 miles"). Mirrors
    _proximity_bonus's linear-decay shape but scores trail length against
    the user's stated target instead of geographic distance.

    Returns 0.0 whenever target_length_km is None — i.e. every existing
    query shape (no distance mentioned, or an explicit ceiling like "under
    5 miles") is completely unaffected. This only activates for the new
    approximate-phrasing case.
    """
    if target_length_km is None:
        return 0.0
    delta = abs(hike.length_km - target_length_km)
    window = max(target_length_km * 0.5, 0.1)  # zero bonus past ±50% of target
    return weight * max(0.0, 1.0 - delta / window)


def _primary_sort_key(pair, primary: Optional[str], target: Optional[float]):
    """
    Sort key for the ranked hikes, honoring TripIntent.primary_priority (the AI-
    /rule-decided single most-important dimension). The primary dimension leads;
    the composite score (and geographic distance) only break ties, so ranking is
    never one-dimensional.

    - primary == "distance" (needs a target): closest-to-target length first.
    - primary is a feature tag: trails carrying that tag first.
    - primary is None ("balanced"): the previous behavior — composite score desc,
      then geographic distance asc.
    """
    hike, score = pair
    geo = getattr(hike, "distance_km", None) or float("inf")
    if primary == "distance" and target is not None:
        return (abs((hike.length_km or 0.0) - target), -score, geo)
    if primary and primary != "distance":
        has_feature = primary in set(hike.tags or [])
        return (0 if has_feature else 1, -score, geo)
    return (0.0, -score, geo)
def _expand_concept_tags(
    required_tags: list[str],
    preferred_tags: list[str],
) -> tuple[list[str], list[str]]:
    """
    Converts multi-tag concept terms into their constituent DB tags.

    Concepts found in required_tags are demoted to preferred_tags (OR
    semantics — any matching tag earns score) because the DB @> operator
    requires ALL listed tags, which a single-concept term can't satisfy.

    Examples:
      required=["water_feature", "gentle_gain"]
        → required=["gentle_gain"]
        → preferred += ["river", "lake", "pond", "stream", "waterfall"]

      preferred=["water_feature", "summit"]
        → preferred=["river", "lake", "pond", "stream", "waterfall", "viewpoint", "ridge", "high_altitude", "ocean_view"]
    """
    new_required: list[str] = []
    new_preferred: list[str] = list(preferred_tags)

    for tag in required_tags:
        if tag in CONCEPT_EXPANSIONS:
            new_preferred.extend(CONCEPT_EXPANSIONS[tag])
        else:
            new_required.append(tag)

    # Also expand any concepts already in preferred_tags
    expanded_preferred: list[str] = []
    for tag in new_preferred:
        if tag in CONCEPT_EXPANSIONS:
            expanded_preferred.extend(CONCEPT_EXPANSIONS[tag])
        else:
            expanded_preferred.append(tag)

    return new_required, expanded_preferred


# ── Module-level scoring helpers ──────────────────────────────────────────────

def _summarise_gaps(gaps: list, tier: str = "standard") -> str:
    """
    Convert a list of GearGap objects (or plain dicts) into a short
    human-readable string for embedding under a hike option.

    On a casual trip with nothing flagged, return the friendly one-liner nudge
    instead of the bare "kit looks solid" — the whole point of the casual tier
    is a reassuring "you're set" rather than a checklist.
    """
    if not gaps:
        return TIER_BLURB["casual"] if tier == "casual" else "kit looks solid"

    def _get(item, key):
        return item[key] if isinstance(item, dict) else getattr(item, key, None)

    missing  = [
        _get(g, "category").replace("_", " ")
        for g in gaps
        if _get(g, "issue") == "missing"
    ]
    marginal = [
        _get(g, "category").replace("_", " ")
        for g in gaps
        if _get(g, "issue") == "marginal"
    ]

    parts: list[str] = []
    if missing:
        parts.append(f"missing: {', '.join(missing)}")
    if marginal:
        parts.append(f"worth noting: {', '.join(marginal)}")

    return " | ".join(parts) if parts else "kit looks solid"


def _tag_match_score(hike_tags: set[str], preferred_tags: list[str]) -> float:
    """
    Graduated tag scoring using TAG_FALLBACKS as a one-hop semantic graph.

    Exact match      → 1.0
    First fallback   → 0.5  (most similar)
    Second fallback  → 0.33
    Third fallback   → 0.25
    No match         → 0.0
    """
    score = 0.0
    for pref in preferred_tags:
        if pref in hike_tags:
            score += 1.0
            continue
        alts = TAG_FALLBACKS.get(pref, [])
        for rank, alt in enumerate(alts):
            if alt in hike_tags:
                score += 1.0 / (rank + 2)
                break
    return score
def _get_unmatched_preferred_tags(
    scored: List[Tuple[Hike, int]],
    preferred_tags: List[str],
    concept_tags: List[str],
) -> List[str]:
    """
    Returns preferred tags (excluding concept-expanded terms, which are
    tracked separately via unmatched_concept_tags) that appear in zero
    returned hikes.

    Before this fix, format_for_context() only disclosed gaps for concept
    terms (water_feature, scenic, etc.). Plain preferred tags like
    'viewpoint', 'ridge', 'summit', or 'historic' had no equivalent check —
    when a search returned proximity-only results with zero matches for
    one of these, Groq got no DATA NOTE and invented justifications instead
    of admitting the gap.
    """
    all_result_tags: set[str] = set()
    for hike, _ in scored:
        all_result_tags.update(hike.tags or [])

    db_preferred = [
        t for t in (preferred_tags or [])
        if t not in concept_tags and t not in _NON_FEATURE_PREFERRED_TAGS
    ]
    return [t for t in db_preferred if t not in all_result_tags]

def _proximity_bonus(hike: Hike, falloff_km: float, weight: float = 0.3) -> float:
    """
    Linear proximity bonus so distance has a real role in ranking, not just
    a tiebreaker. `weight` is the bonus given to the closest possible hike
    (dist=0); it decays linearly to 0 at `falloff_km`.

    `falloff_km` is the ranking normalization radius, NOT the search radius —
    for a point search it's deliberately tight (POINT_PROXIMITY_FALLOFF_KM) so
    "actually here" trails win; for a region search it's the full search radius,
    where closeness to a state centroid isn't a meaningful signal anyway.
    """
    dist = getattr(hike, "distance_km", None)
    if dist is None:
        return 0.0
    return weight * max(0.0, 1.0 - dist / falloff_km)


DIFFICULTY_SCORE = {"easy": 0, "moderate": 1, "hard": 2, "difficult": 2, "expert": 3}
def _difficulty_unmatched(scored_pairs, difficulty_hint: Optional[str]) -> bool:
    """
    True when difficulty_hint is set but none of the scored hikes carry that
    exact DifficultyLevel — i.e. find_hikes_for_intent's hard filter had to
    fall back to the unrestricted pool. Single source of truth reused both
    to decide whether a wider-radius retry is worth trying, and to disclose
    the gap to Groq in format_for_context.
    """
    if not difficulty_hint:
        return False
    target = _DIFFICULTY_HINT_TO_ENUM.get(difficulty_hint)
    if target is None:
        return False
    return not any(h.difficulty == target for h, _ in scored_pairs)
def _difficulty_score(hike: Hike, hint: Optional[str]) -> int:
    if not hint:
        return 0
    hike_diff = (
        hike.difficulty.name.lower()
        if hasattr(hike.difficulty, "name")
        else str(hike.difficulty).lower()
    )
    hint_val  = DIFFICULTY_SCORE.get(hint, 1)
    hike_val  = DIFFICULTY_SCORE.get(hike_diff, 1)
    distance  = abs(hint_val - hike_val)
    if distance == 0: return 3
    if distance == 1: return 1
    return 0