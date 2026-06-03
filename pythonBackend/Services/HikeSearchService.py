# Services/HikeSearchService.py
#
# Bridges TripIntent → HikeService.
#
# Phase 1  Hard filter  — passes column-backed and tag-array constraints to
#                          HikeService.search_hikes(), which calls the repo.
# Phase 2  Soft rank    — scores the surviving candidates in Python by counting
#                          how many preferred_tags each hike contains.
# Phase 3 helper        — format_for_context() serialises the top-N results
#                          into the string that gets injected into the Groq
#                          system prompt.
#
# This file knows about TripIntent.  HikeService/HikeRepo do NOT.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from PyObjects.Hike import Hike
from Services.HikeService import HikeService

if TYPE_CHECKING:
    # Avoid a hard circular dependency at import time; only used for type hints.
    from AI.TripInputParser import TripIntent

# Tags in TripIntent.required_tags that map to dedicated boolean columns
# instead of the tags[] array.  Strip these before building the @> query.
_COLUMN_TAGS: frozenset[str] = frozenset({"can_camp"})

# Default search radius when the caller does not specify one.
DEFAULT_RADIUS_KM: float = 150.0


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

        match_score = number of preferred_tags present on the hike.
        """
        can_camp, tag_required = self._split_required_tags(intent.required_tags)
        permits_required: Optional[bool] = False if intent.avoid_permits else None

        # ── Phase 1: hard filter via DB ────────────────────────────────────────
        candidates: List[Hike] = self.hike_service.search_hikes(
            user_lat=intent.lat,
            user_lon=intent.lng,
            max_distance_km=max_distance_km,
            can_camp=can_camp,
            permits_required=permits_required,
            required_tags=tag_required or None,
        )

        # ── Phase 2: score by preferred_tags overlap (pure Python) ─────────────
        preferred_set = set(intent.preferred_tags)
        scored: List[Tuple[Hike, int]] = [
            (hike, len(set(hike.tags or []) & preferred_set))
            for hike in candidates
        ]

        # Primary sort: score desc.  Tiebreaker: distance asc (None → infinity).
        scored.sort(
            key=lambda x: (
                -x[1],
                getattr(x[0], "distance_km", None) or float("inf"),
            )
        )
        return scored[:top_n]

    def format_for_context(self, scored: List[Tuple[Hike, int]]) -> str:
        """
        Phase 3 helper.

        Serialises ranked hikes into a structured string for Groq context
        injection, e.g.:

            1. Yosemite Falls Trail (ID: …): 11.6km, Hard, Gain: 875m,
               22km away, Tags: [waterfall, views]
            2. …

        The PhaseController embeds this verbatim in the system prompt so Groq
        is constrained to recommend only real trails from the database.
        """
        if not scored:
            return "No matching trails found near this destination."

        lines: List[str] = []
        for i, (hike, score) in enumerate(scored, start=1):
            tags_str = ", ".join(hike.tags or [])
            dist = getattr(hike, "distance_km", None)
            dist_part = f", {dist:.0f}km away" if dist is not None else ""
            camp_part = ", camping available" if hike.can_camp else ""
            permit_part = ", permit required" if hike.permits_required else ""
            lines.append(
                f"{i}. {hike.name} (ID: {hike.id}): "
                f"{hike.length_km}km, {hike.difficulty.name.title()}, "
                f"Gain: {hike.elevation_gain_m}m"
                f"{dist_part}"
                f"{camp_part}"
                f"{permit_part}"
                f", Tags: [{tags_str}]"
            )
        return "\n".join(lines)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _split_required_tags(
        required_tags: List[str],
    ) -> Tuple[Optional[bool], List[str]]:
        """
        Separates column-backed tags from true array tags.

        Returns:
            can_camp      — True if "can_camp" was in required_tags, else None.
            tag_required  — required_tags with column-backed entries removed.
                            Ready to pass as the tags @> ARRAY[...] filter.
        """
        can_camp: Optional[bool] = True if "can_camp" in required_tags else None
        tag_required = [t for t in required_tags if t not in _COLUMN_TAGS]
        return can_camp, tag_required