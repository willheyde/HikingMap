"""
ItineraryParser.py

Second-pass Groq call that extracts a structured day-by-day itinerary
from the natural-language response Groq just produced.

Design intent
-------------
The user-facing itinerary response stays natural prose — Groq writes for
the hiker, not for a parser.  Immediately after that response is returned,
a separate low-temperature extraction call converts the prose into a list
of DayPlan objects that get written to plan.days.

This approach was chosen over embedding a JSON block in the main response
because:
  - Groq sometimes silently drops embedded blocks under token pressure
  - The extraction prompt can be kept strict and deterministic (temp 0.1)
    without affecting the tone of the conversational response
  - Failures are isolated — a bad parse leaves plan.days empty rather than
    corrupting the user-facing response

Public API
----------
    parser = ItineraryParser(groq_client)
    days   = parser.parse_from_response(ai_response, duration_days=3)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from AI.GroqClient import GroqClient

from .TripPlan import DayPlan

logger = logging.getLogger(__name__)


# ── Extraction system prompt ──────────────────────────────────────────────────
#
# Strict JSON-only.  Every sentence is load-bearing: "no preamble" prevents
# "Sure! Here is the JSON:", "no fences" prevents ```json wrapping, and the
# schema comment prevents hallucinated field names.

_EXTRACT_SYSTEM = """\
You are a JSON extractor. Read the hiking trip itinerary and output a single \
valid JSON object. No preamble. No explanation. No markdown fences.

Output schema (omit any numeric field that is not mentioned — do not guess):
{
  "days": [
    {
      "day_number": <integer>,
      "title": <short label, e.g. "Drive in + summit attempt">,
      "distance_miles": <number, omit if unknown>,
      "elevation_gain_ft": <integer, omit if unknown>,
      "campsite": <location name string, or null if not an overnight>,
      "notes": <one sentence of key advice, or null>
    }
  ]
}

Units: distance in miles, elevation in feet. Convert if the source uses km/m.
If the source says "approx." or "~", use the number and omit the qualifier.\
"""


class ItineraryParser:
    """
    Stateless.  Instantiate once at module level in trip_chat.py and
    share the GroqClient singleton so no extra connections are opened.
    """

    def __init__(self, groq_client: "GroqClient") -> None:
        self._groq = groq_client

    def parse_from_response(
        self,
        ai_response:   str,
        duration_days: Optional[int] = None,
    ) -> list[DayPlan]:
        """
        Attempts to extract DayPlan objects from a prose itinerary response.

        Returns an empty list if:
          - The response doesn't look like a full itinerary (still gathering
            info, asking clarifying questions, etc.)
          - The Groq extraction call fails
          - JSON parsing or validation fails

        On empty return, the caller should leave plan.days unchanged so the
        last successful parse is preserved.

        duration_days is used as a sanity check: if the parsed result
        contains significantly more days than the trip length, something
        went wrong and we discard the result rather than storing garbage.
        """
        if not ai_response or not _looks_like_itinerary(ai_response):
            return []

        try:
            raw = self._groq.extract(
                system_prompt = _EXTRACT_SYSTEM,
                content       = ai_response,
            )
        except Exception as e:
            logger.warning("ItineraryParser: extraction call failed: %s", e)
            return []

        days = _parse_json(raw, duration_days)

        if days:
            logger.info("ItineraryParser: extracted %d day(s).", len(days))

        return days


# ── Module-level helpers ──────────────────────────────────────────────────────

def _looks_like_itinerary(text: str) -> bool:
    """
    Fast gate before making the extraction API call.

    A response that is just a clarifying question ("How many miles per day
    are you comfortable with?") or a casual day reference ("On Day 1, would
    you prefer a 5-mile trail?") will not contain the structured Day N: header
    that PromptBuilder instructs Groq to use, so those turns are cheap.

    Two conditions must both be true:
      1. A proper "Day N:" header line — the exact format PromptBuilder
         specifies.  A casual mention like "on Day 1" fails this check
         because there is no colon immediately after the number.
      2. At least one distance stat (miles/mi) OR one elevation/gain stat
         (ft/feet/gain).  Together they represent the minimum data present
         in a real itinerary line:
             "Distance: X miles  |  Gain: Y ft"

    This replaces the previous substring-count approach, which had two bugs:
      - "mile" and "miles" were both in the marker list, so a single mention
        of "miles" counted as two markers toward the threshold of three,
        causing false positives on simple questions.
      - "day 1" + "mile" + "trail" appearing in a clarifying question ("A
        5-mile trail on Day 1, would that work?") also hit the threshold.
    """
    tl = text.lower()

    # "Day 1:", "Day 2:", "Day 10:" etc — colon required
    has_day_header = bool(re.search(r"\bday\s+\d+\s*:", tl))

    # Distance: any number followed by miles / mi (whole word to avoid "mimic")
    has_distance = bool(re.search(r"\d+(\.\d+)?\s*(miles?\b|mi\b)", tl))

    # Elevation/gain: any number followed by ft / feet / gain
    has_gain = bool(re.search(r"\d+\s*(ft\b|feet\b|gain)", tl))

    return has_day_header and (has_distance or has_gain)


def _parse_json(raw: str, duration_days: Optional[int]) -> list[DayPlan]:
    """
    Parses the raw string from the extraction call into DayPlan objects.
    Handles any accidental markdown fencing Groq adds despite the prompt.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.splitlines()
        cleaned = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            "ItineraryParser: JSON decode failed — %s | raw (first 300 chars): %.300s",
            e, raw,
        )
        return []

    days_raw = data.get("days")
    if not isinstance(days_raw, list) or not days_raw:
        logger.warning("ItineraryParser: 'days' key missing or empty in extraction response.")
        return []

    # Sanity check: more than one extra day suggests the model hallucinated
    # extra days beyond the trip length.
    if duration_days and len(days_raw) > duration_days + 1:
        logger.warning(
            "ItineraryParser: parsed %d days but trip is %d days — discarding result.",
            len(days_raw), duration_days,
        )
        return []

    days: list[DayPlan] = []
    for entry in days_raw:
        if not isinstance(entry, dict):
            logger.warning("ItineraryParser: skipping non-dict day entry: %r", entry)
            continue
        try:
            days.append(DayPlan(
                day_number        = int(entry["day_number"]),
                title             = str(entry.get("title") or f"Day {entry['day_number']}"),
                distance_miles    = _to_float(entry.get("distance_miles")),
                elevation_gain_ft = _to_int(entry.get("elevation_gain_ft")),
                campsite          = entry.get("campsite") or None,
                notes             = entry.get("notes") or None,
            ))
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("ItineraryParser: skipping malformed day entry %r: %s", entry, e)
            continue

    if not days:
        logger.warning("ItineraryParser: all entries were malformed — returning empty.")

    return days


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None