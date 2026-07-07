"""
trip_metrics.py

Pure derivations from a selected hike's real stats — no LLM, no session state.

  - estimate_hike_duration() : Naismith-rule on-trail time from distance + gain.
  - reverse_geocode()        : Nominatim reverse lookup for a human place label,
                               used to replace the crude "Near your current
                               location" destination with the trailhead's actual
                               town/region.
  - km_to_miles / m_to_feet  : unit helpers (the DB stores metric; the UI and
                               itinerary are imperial).

Kept separate from TripInputParser (which owns forward geocoding for user text)
so the save/summary path can depend on these without pulling in the parser.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

KM_PER_MILE = 1.60934
FT_PER_M    = 3.28084


def km_to_miles(km):
    return round(km / KM_PER_MILE, 1) if km is not None else None


def m_to_feet(m):
    return round(m * FT_PER_M) if m is not None else None


def estimate_hike_duration(length_km, gain_m):
    """
    Estimate on-trail time via Naismith's rule: ~5 km/h on the flat plus ~1 hour
    per 600 m of ascent. Returns (hours, human_label) — e.g. (0.74, "~45 min").

    A rough planning estimate, not a promise: real pace varies with fitness,
    terrain, and load. Deliberately simple; tune the constants if it reads high
    or low. Returns (None, None) when there's no usable distance.
    """
    if not length_km or length_km <= 0:
        return None, None
    hours = length_km / 5.0 + (gain_m or 0) / 600.0
    return hours, _duration_label(hours)


def _duration_label(hours: float) -> str:
    minutes = hours * 60
    if minutes < 90:
        # Round to the nearest 15 min for a tidy "~45 min" / "~1 hr 15 min".
        rounded = max(15, round(minutes / 15) * 15)
        if rounded < 60:
            return f"~{rounded} min"
        h, m = divmod(rounded, 60)
        return f"~{h} hr" + (f" {m} min" if m else "")
    if hours < 8:
        label = "half-day" if hours < 4 else "full-day"
        return f"~{round(hours * 2) / 2:g} hrs ({label})"
    # Very long single hikes → express in days at ~6 hiking hours/day.
    days = max(1, round(hours / 6))
    return f"~{days} days on trail"


def reverse_geocode(lat, lng):
    """
    Resolve a lat/lng to a concise human place label (town/county + state) via
    one Nominatim reverse call. Callers should invoke this at most once per
    selection — never per chat turn. Returns None on any failure so callers can
    fall back to a coarser label (the hike's region, etc.).
    """
    if lat is None or lng is None:
        return None
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat, "lon": lng, "format": "json",
                "zoom": 12, "addressdetails": 1,
            },
            headers={"User-Agent": "HikeBuilder/1.0"},
            timeout=5.0,
        )
        data = r.json()
        addr = data.get("address", {}) if isinstance(data, dict) else {}
        # Prefer the most specific populated-place field available.
        place = (
            addr.get("town") or addr.get("city") or addr.get("village")
            or addr.get("hamlet") or addr.get("county") or addr.get("suburb")
        )
        state = addr.get("state")
        parts = [p for p in (place, state) if p]
        if parts:
            return ", ".join(parts)
        # Fall back to Nominatim's own display_name (first two components).
        name = data.get("display_name")
        if name:
            return ", ".join(name.split(",")[:2]).strip()
    except Exception as e:
        logger.warning("reverse_geocode failed for (%s, %s): %s", lat, lng, e)
    return None
