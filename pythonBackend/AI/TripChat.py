"""
trip_chat.py

Single POST endpoint: /api/trip/chat
Save endpoint:        POST /api/trip/save

Orchestrates the full request lifecycle:
  1.  Load or create session
  2.  Fetch user gear from DB
  3.  Parse trip intent (destination phase only — single parse, with lat/lng)
  4.  Search for hike candidates + run per-hike gear analysis
  5.  Resolve hike selection; promote selected hike's gaps to plan.gear_gaps
  6.  Phase transition / destination-reset check (pre-response)
      6b. Python-level destination-change detector (belt-and-suspenders)
  7.  Build system prompt
  8.  Call Groq (with per-phase token + temperature settings)
  8b. Parse itinerary from Groq response (itinerary phase only)
  9.  Post-response check (catches Groq emitting DESTINATION RESET)
  9b. Scan finalize-phase response for SAVE CONFIRMED signal
  10. Append turn + async summarize if needed
  11. Persist session to Redis
  12. Return response + metadata to frontend

Key design notes
----------------
* Intent is parsed ONCE per request, inside the destination-phase guard,
  using the lat/lng the frontend sent.

* Gear analysis (GearGapAnalyzer.analyze_for_hike) runs in the destination
  phase, once per candidate hike.  Results cached in phase_data (Redis dicts).

* No per-phase gear-analysis block.  Gaps are promoted at hike selection time.

* After every Groq response in the itinerary phase, ItineraryParser attempts
  to extract DayPlan objects from the prose.  Heuristic gate prevents the
  extraction call on clarifying-question turns.

* Per-phase Groq parameters are imported from PromptBuilder.PHASE_GROQ_PARAMS.

* DESTINATION RESET is caught two ways:
    - Pre-response: _detect_destination_change() checks the user message
      against a set of high-confidence phrase signals.  Fires before Groq
      responds, so the reset is applied to the prompt Groq sees.
    - Post-response: scans ai_response for the literal string
      "DESTINATION RESET" as a fallback for cases the Python detector
      missed (ambiguous phrasing that Groq caught but the detector didn't).
      Only the reset signal is checked post-response — full evaluate() is
      NOT called again to avoid spurious phase advances.

* SAVE CONFIRMED is detected post-response in the finalize phase.
  ChatResponse.save_confirmed = True tells the frontend to trigger
  POST /api/trip/save?session_id=...
"""

import asyncio
import difflib
import logging
import re
from typing import Optional
from uuid import UUID
from types import SimpleNamespace
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from Auth.authentication        import get_current_user_id
from Repos.TripRepo             import TripRepository
from Services.TripService       import TripService
from AI.TripInputParser import (
    TripInputParser, TripIntent, RefinementIntent, ALL_FEATURE_KEYWORDS,
)
from AI.GearGapAnalyzer import GearGapAnalyzer, CATEGORY_TO_ITEM_TYPE, CAT_RAIN_GEAR, CAT_INSULATION
from Services.UserService import UserService
from Repos.UserRepo       import UserRepository
from AI.ItineraryParser         import ItineraryParser
from AI.PromptBuilder           import build_system_prompt, PHASE_GROQ_PARAMS
from AI.Summarizer              import Summarizer
from AI.PhaseController         import PhaseController
from AI.GroqClient              import GroqClient
from AI.TripSession         import TripSession
from AI.TripPlan            import GearGap
from trip_metrics           import estimate_hike_duration, reverse_geocode
from gear_levels            import resolve_gear_category, resolve_level
from PyObjects.Trip         import Trip
from AI.SessionStore import SessionStore, SessionStoreUnavailable
from Repos.ItemRepo             import ItemRepository
from Services.HikeSearchService import HikeSearchService
from Services.HikeService       import HikeService
from Repos.HikeRepo             import HikeRepository
from Services.ItemService import ItemService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trip", tags=["trip"])


# ── Singletons ────────────────────────────────────────────────────────────────

_store             = SessionStore()
_parser            = TripInputParser()
_analyzer          = GearGapAnalyzer()
_summarizer        = Summarizer()
_controller        = PhaseController()
_groq              = GroqClient()
_itinerary_parser  = ItineraryParser(_groq)   # shares the same Groq connection
_hike_service      = HikeService(HikeRepository())
_hike_search       = HikeSearchService(_hike_service)


def get_service() -> TripService:
    return TripService(TripRepository())

def get_item_service() -> ItemService:
    return ItemService(ItemRepository())

def get_user_service() -> UserService:
    return UserService(UserRepository())

# ── Destination-change phrase detector ───────────────────────────────────────
#
# Belt-and-suspenders fallback for DESTINATION RESET.
# These phrases are chosen for very high precision — they almost never appear
# in innocent in-phase messages.  The detector fires BEFORE Groq responds,
# so the session is cleaned up before the prompt is built.
#
# Groq's own "DESTINATION RESET" emission (post-response) remains as the
# fallback for ambiguous phrasing the detector misses (e.g. "I'm thinking
# something warmer" — detector won't catch it, but Groq should).
#
# Only fires when session.phase != "destination" (nothing to reset otherwise).

_DESTINATION_CHANGE_PHRASES: frozenset[str] = frozenset({
    "start over",
    "start again",
    "start fresh",
    "change destination",
    "change the destination",
    "different destination",
    "different location",
    "different trail",
    "different hike",
    "different mountain",
    "different park",
    "different area",
    "somewhere else",
    "somewhere different",
    "try somewhere",
    "try a different",
    "try another place",
    "try another trail",
    "try another hike",
    "what about going to",
    "let's go to",
    "i changed my mind",
    "i've changed my mind",
    "never mind",
    "nevermind",
    "cancel the trip",
    "instead of",
    "actually, let",        # "actually, let's do X instead"
    "actually let",
    "can i go to",       # "Can I go to carr pond instead?"
    "can we go to",
    "go back to destination",
    "go back to destinations",
    "go back to the destination",
    "go back to hike",
    "go back to hikes",
    "back to destination",
    "back to destinations",
    "back to the destination",
    "back to hike selection",
    "return to destination",
    "what if we went to",
    "how about going to",
    "actually, can we",
    "actually can we",
    "what about hikes in",
    "what about hiking in",
    "can we look at",
    "can we check",
})

_GEAR_ADD_RE = re.compile(r"\n?GEAR ADD:\s*([^\n]+)", re.IGNORECASE)
_DIFFICULTY_RE = re.compile(
    r"\b(easy|moderate|medium|hard|difficult|strenuous|challenging)\b",
    re.IGNORECASE,
)

# Catches Groq echoing the raw HIKE OPTIONS stats/tags line (or the gear-check
# line, or a "here are the N hike options" header) despite being told not to.
# Now that the frontend renders options as buttons instead of appending a
# plain-text list, any such leaked line would show up as stray duplicate text
# above the buttons — this strips it defensively. See step 9f.
_LEAKED_HIKE_LINE_RE = re.compile(
    r"(?mi)^.*Tags:\s*\[.*\].*$\n?|^\s*Gear check:.*$\n?|^\s*Here (?:are|is) the .*hike option.*$\n?"
)

# ── Bug 1 fix: trail-system name guard ───────────────────────────────────────
#
# TripInputParser occasionally geocodes a geographic region (e.g. "Rhode Island")
# to the nearest named long-distance trail system ("Appalachian Trail").  The
# regex below catches the most common US long-distance trail names.  When
# destination_full matches and destination_raw doesn't, we override the display
# name with destination_raw so the saved trip summary shows the correct location.
_TRAIL_SYSTEM_RE = re.compile(
    r"\b(appalachian|pacific\s+crest|continental\s+divide|long\s+path|"
    r"ice\s+age|florida\s+national\s+scenic|natchez\s+trace|"
    r"north\s+country|potomac\s+heritage|arizona)\s+trail\b",
    re.IGNORECASE,
)
_AFFIRMATION_PHRASES: frozenset[str] = frozenset({
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
    "sounds good", "do it", "go ahead", "that works", "works for me",
})

_DIFFICULTY_PIVOT: dict[str, str] = {"hard": "moderate", "moderate": "easy"}
ACTIVITY_DURATION_TAGS: dict[str, list[str]] = {
    "day_hike":       ["short", "half_day", "full_day"],
    "overnight":      ["full_day"],
    "backpacking":    ["full_day"],
    "extended":       ["full_day"],
    "mountaineering": ["full_day"],
}
FEATURE_KEYWORD_MAP: dict[str, list[str]] = {
    "waterfall":    ["waterfall", "falls", "cascade"],
    "lake":         ["lake", "pond", "tarn", "swimming hole", "swim"],
    "summit":       ["summit", "peak", "mountaintop", "highest point", "top of"],
    "canyon":       ["canyon", "gorge", "slot canyon", "ravine"],
    "ridge":        ["ridge", "ridgeline", "exposed ridge"],
    "glacier":      ["glacier", "glacial", "icefield"],
    "meadow":       ["meadow", "wildflower", "wildflowers", "open field"],
    "forest":       ["forest", "woods", "wooded", "tree cover"],
    "beach":        ["beach", "coastal", "shoreline", "ocean"],
    "cave":         ["cave", "cavern", "grotto"],
    "viewpoint":    ["view", "views", "overlook", "vista", "scenic", "scenery"],
    "hot_spring":   ["hot spring", "hot springs", "thermal"],
    "river":        ["river", "creek", "stream", "waterway"],
    "historic":     ["historic", "ruins", "petroglyphs", "old growth"],
    "desert":       ["desert", "arid", "cactus", "red rock"],
    "montane":      ["montane", "mountain", "mountainous", "highland", "highlands", "high country"],
    "subalpine":    [
        "subalpine", "alpine", "above treeline", "above tree line",
        "high alpine", "exposed", "treeline", "near treeline",
    ],
    "lowland":      ["lowland", "flat ground", "gentle terrain"],
    "seasonal":     [
        "seasonal", "spring or fall", "spring/fall",
        "shoulder season", "seasonal access", "open seasonally",
    ],
    "water_feature": ["water feature", "water source", "near water", "by the water", "on the water"],
}
# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str
    session_id: Optional[str]   = None
    user_lat:   Optional[float] = None   # frontend sends on every message
    user_lng:   Optional[float] = None


class ChatResponse(BaseModel):
    session_id:     str
    response:       str
    phase:          str
    plan:           dict
    advanced:       bool
    created:        bool
    save_confirmed: bool = False   # True when Groq emits SAVE CONFIRMED in finalize
    # Structured hike options for the frontend to render as selectable cards/
    # buttons instead of parsing the plain-text list out of `response`. Only
    # populated in the destination phase while options are presented and no
    # hike has been picked yet; empty otherwise. Clicking option N should send
    # the chat message "N" (1-based, matching `index`) — the same signal a
    # user typing the number would have sent.
    hike_options:   list[dict] = []


class SaveResponse(BaseModel):
    trip_id: str
    title:   str
    stops:   list[dict]
    gear:    list[dict]


# Chat lifecycle: active (Redis-only) -> saved -> completed -> reviewed
# (the last three live on trips.status; see migrations/001_trips_lifecycle.sql).
_VALID_CHAT_STATUSES: frozenset[str] = frozenset({"active", "saved", "completed", "reviewed"})


class ChatSummary(BaseModel):
    """One row in GET /chats — enough to render a history list item, not
    the full session/trip payload (see GET /chats/{id} for that)."""
    id:           str
    status:       str                    # active | saved | completed | reviewed
    title:        str
    created_at:   Optional[str] = None
    updated_at:   Optional[str] = None
    phase:        Optional[str] = None   # set only for status="active"
    needs_review: bool = False           # only meaningful for status="completed"; drives the dismissible banner
    rating:       Optional[int] = None   # 1-5, set only if a review with a rating exists


class ReviewRequest(BaseModel):
    went:            bool
    difficulty_felt: Optional[str] = None   # EASY | MODERATE | DIFFICULT | EXPERT
    elevation_felt:  Optional[str] = None
    rating:          Optional[int] = None   # 1-5
    notes:           Optional[str] = None


class DuplicateResponse(BaseModel):
    """Shaped like ChatResponse's essentials — the frontend treats this
    exactly like landing mid-conversation in the destination phase."""
    session_id:   str
    response:     str
    phase:        str
    plan:         dict
    hike_options: list[dict] = []


# ── Gear loader ───────────────────────────────────────────────────────────────

def _load_user_gear(user_id: str, item_service: ItemService) -> list[dict]:
    items = item_service.list_by_user(UUID(user_id))
    gear: list[dict] = []
    for item in items:
        attrs = getattr(item, "attributes", None) or {}
        gear_category = resolve_gear_category(item.item_type, attrs)
        gear.append({
            "id":            str(item.id),
            "name":          item.name,
            "category":      item.item_type,          # raw item_type (legacy consumers)
            "gear_category": gear_category,           # functional category (A+ model)
            "level":         resolve_level(gear_category, attrs),
            "weight":        item.weight,
            "cost":          item.cost,
            # Prefer the raw jsonb (covers free-text gear built as a base Item,
            # whose typed attribute fields aren't populated) then the typed field.
            "temp_rating_f": attrs.get("temp_rating_f", getattr(item, "temp_rating_f", None)),
            "waterproof":    attrs.get("waterproof",    getattr(item, "waterproof", None)),
        })
    return gear


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def trip_chat(
    req:             ChatRequest,
    current_user_id: str            = Depends(get_current_user_id),
    item_service:    ItemService    = Depends(get_item_service),
    user_service:    UserService    = Depends(get_user_service),
):
    # ── 1. Load or create session ──────────────────────────────────────────
    try:
        session, created = _store.get_or_create(
            session_id = req.session_id,
            user_id    = current_user_id,
        )
    except SessionStoreUnavailable as e:
        logger.error("Session service unavailable for user %s: %s", current_user_id, e)
        raise HTTPException(503, "Session service is temporarily unavailable. Please try again in a moment.")
    itinerary_prebuilt = bool(session.plan.days)

    # ── 2. Fetch user gear from DB ─────────────────────────────────────────
    try:
        user_gear = _load_user_gear(current_user_id, item_service)
    except Exception as e:
        logger.error("Failed to fetch gear for user %s: %s", current_user_id, e)
        raise HTTPException(500, "Could not load gear data.")

    # ── 3. Parse intent (destination phase only, single call with lat/lng) ─
    intent: Optional[TripIntent] = None
    hike_context: str = ""

    if session.phase == "destination":
        # Bug fix: this used to guard on `not session.plan.is_destination_set()`,
        # which also requires hike_id — but hike_id isn't set until step 5,
        # AFTER this check runs. On the exact turn the user picks a hike
        # ("option 2"), that condition was still True, so their selection
        # message got reparsed as if it were a fresh destination description.
        # When the regex path found nothing, this fell through to the LLM
        # extraction fallback, which would happily "extract" a destination
        # from something like "Option 1: Red Trail" and silently overwrite
        # plan.destination_full/state/tags/etc with garbage right as the
        # trip was being finalized. hikes_presented is the real signal for
        # "still gathering destination info" — once options are shown, there
        # is nothing left here for this branch to do.
        if not session.phase_data.get("hikes_presented"):
            named_query = _extract_hike_name_query(req.message)
            if named_query:
                # ── Named-trail request: direct DB lookup, not a filtered search ──
                hike, candidates = _resolve_named_hike(named_query)
                if hike is not None:
                    # One confident match → select it outright. intent stays None,
                    # steps 4/5 skip, and step 6 auto-advances to gear_review.
                    # Off the event loop: this does a DB get_hike + a (possibly
                    # 5s) reverse-geocode inside _capture_selected_hike_facts.
                    await asyncio.to_thread(_select_named_hike, session, user_gear, hike)
                    logger.info(
                        "Session %s: named-hike direct select — %r → %s",
                        session.session_id, named_query, hike.name,
                    )
                elif candidates:
                    # Several plausible matches → present as cards to disambiguate.
                    hike_context = _present_named_candidates(session, user_gear, candidates)
                    logger.info(
                        "Session %s: named-hike disambiguation — %r → %d candidates",
                        session.session_id, named_query, len(candidates),
                    )
                else:
                    # No match → deterministic "describe it" reply; short-circuit
                    # before Groq so the wording is exactly as intended.
                    not_found = (
                        f"I couldn't find a trail called “{named_query}” in my "
                        "database — I may just not have that one yet. Can you tell me a "
                        "bit about it so I can find the closest match? Roughly how hard is "
                        "it (easy, moderate, or hard), and where is it (a nearby town, "
                        "park, or state)?"
                    )
                    logger.info(
                        "Session %s: named-hike not found — %r",
                        session.session_id, named_query,
                    )
                    session.add_turn(req.message, not_found)
                    if not _store.save(session):
                        logger.error("Redis save failed for session %s", session.session_id)
                    return ChatResponse(
                        session_id     = session.session_id,
                        response       = not_found,
                        phase          = session.phase,
                        plan           = session.plan.to_dict(),
                        advanced       = False,
                        created        = created,
                        hike_options   = [],
                    )
            elif _has_no_destination(req.message):
                logger.info(
                    "Session %s: no-location short-circuit — skipping parse "
                    "for message: %r",
                    session.session_id, req.message,
                )
                text = req.message.lower().strip()
                required, preferred, avoid_permits, priority = _parser._extract_tags(
                    text, _parser._extract_activity(text), _parser._extract_difficulty(text)
                )
                max_len, target_len = _parser._extract_length_constraints(text)   # ← was _extract_max_length_km
                _merge_accum_tags(
                    session, required, preferred, priority,
                    _parser._extract_difficulty(text),
                    max_len, target_len,
                )
            else:
                intent = _parse_intent(req)
                if intent is not None:
                    _merge_accum_tags(
                        session, intent.required_tags, intent.preferred_tags,
                        intent.priority_tags, intent.difficulty_hint,
                        intent.max_length_km, intent.target_length_km,
                    )
                    intent.required_tags    = session.phase_data["accum_required_tags"]
                    intent.preferred_tags   = session.phase_data["accum_preferred_tags"]
                    intent.priority_tags    = session.phase_data["accum_priority_tags"]
                    intent.difficulty_hint  = intent.difficulty_hint or session.phase_data.get("accum_difficulty_hint")
                    intent.max_length_km    = intent.max_length_km or session.phase_data.get("accum_max_length_km")
                    intent.target_length_km = intent.target_length_km or session.phase_data.get("accum_target_length_km")
                    _apply_intent_to_plan(
                        session, intent,
                        destination_override=_resolve_destination_display(intent),
                    )

                    if (
                        intent.destination_type == "region"
                        and not session.phase_data.get("drive_distance_asked")
                    ):
                        session.phase_data["drive_distance_asked"] = True

        # ── 4. Hike search + per-hike gear analysis ────────────────────────
        if intent is not None and not session.phase_data.get("hikes_presented"):
            hike_context = _search_and_analyse(session, user_gear, intent)

        elif session.phase_data.get("hikes_presented") and not session.plan.hike_id:
            hike_context = session.phase_data.get("hike_context", "")

    # ── 5. Resolve hike selection; promote gaps to plan ────────────────────
    # just_selected_hike: this turn's user message resolved to a numbered pick
    # (a card click / "option N"). It gates the SEARCH_REFINE handler below —
    # a selection is NOT a refine request, and honoring a misfired SEARCH_REFINE
    # on the selection turn soft-resets the just-made choice and desyncs the
    # phase machine from Groq's context permanently (see step 9e guard).
    just_selected_hike = False
    if (
        session.phase == "destination"
        and session.phase_data.get("hikes_presented")
        and session.plan.hike_id is None
    ):
        idx = PhaseController.extract_hike_selection(
            req.message,
            count=len(session.phase_data.get("hike_options", [])),
        )
        if idx is not None:
            session.plan.hike_id   = session.phase_data["hike_options"][idx]
            session.plan.hike_name = session.phase_data["hike_names"][idx]
            _promote_hike_gaps(session, str(session.plan.hike_id))
            # to_thread: captures DB stats + a reverse-geocode (blocking httpx,
            # up to 5s) — keep it off the event loop.
            await asyncio.to_thread(_capture_selected_hike_facts, session)
            just_selected_hike = True
            logger.info(
                "Session %s: hike selected — %s (%d gap(s)).",
                session.session_id,
                session.plan.hike_name,
                len(session.plan.gear_gaps),
            )

    # ── 6. Phase transition check (pre-response) ──────────────────────────
    advanced, reset = _controller.evaluate(
        session      = session,
        user_message = req.message,
        intent       = intent,
        ai_response  = "",
    )

    # ── 6b. Python-level destination-change detector ───────────────────────
    #
    # Catches high-confidence change signals before Groq responds.
    # Only meaningful once we're past the destination phase.
    if not reset and not advanced and _detect_destination_change(req.message, session.phase):
        reset = True
        logger.info(
            "Session %s: destination change detected by phrase detector.",
            session.session_id,
        )

    if reset:
        _reset_destination(session)
        advanced = False
        new_intent = _parse_intent(req)
        if new_intent is not None:
            intent = new_intent
            # Bug 1 fix: same logging + trail-system guard on the reset path.
            logger.info(
                "Session %s: post-reset intent — destination_full=%r "
                "destination_raw=%r lat=%s lng=%s",
                session.session_id,
                new_intent.destination_full,
                getattr(new_intent, "destination_raw", "N/A"),
                new_intent.lat,
                new_intent.lng,
            )
            _apply_intent_to_plan(
                session, new_intent,
                destination_override=_resolve_destination_display(new_intent),
            )
            hike_context = _search_and_analyse(session, user_gear, new_intent)

    if advanced:
        _handle_phase_entry(session)

    # ── 7. Build system prompt ─────────────────────────────────────────────
    logger.info(
        "Session %s: phase=%s advanced=%s after evaluate",
        session.session_id, session.phase, advanced,
    )

    # Bug 3 fix: capture whether the finalize summary was already shown BEFORE
    # build_system_prompt is called.  _finalize_phase_block sets
    # save_summary_shown=True on the first call, so by the time we check
    # save_confirmed below the flag is always True — we need the value from
    # the START of this turn to know whether the summary was shown in a prior
    # turn and the user is now genuinely confirming, vs. saying "save" before
    # they've even seen the summary.
    finalize_summary_prebuilt = (
        session.phase == "finalize"
        and session.phase_data.get("save_summary_shown", False)
    )

    system_prompt = build_system_prompt(session, user_gear, hike_context=hike_context)

    # ── 8. Call Groq (per-phase token + temperature settings) ─────────────
    groq_params = _resolve_groq_params(session)

    try:
        ai_response, _ = _groq.chat(
            system_prompt   = system_prompt,
            summary         = session.summary,
            window_messages = session.get_window_messages(),
            user_message    = req.message,
            **groq_params,
        )
    except Exception as e:
        logger.error("Groq API error: %s", e)
        raise HTTPException(502, "AI service unavailable. Please try again.")

    # ── 8b. Parse itinerary from response (itinerary phase only) ──────────
    #
    # ItineraryParser gates on a fast heuristic before making the extraction
    # call, so clarifying-question turns are cheap.  An empty return leaves
    # plan.days unchanged — last successful parse is preserved.
    if session.phase == "itinerary":
        days = _itinerary_parser.parse_from_response(
            ai_response   = ai_response,
            duration_days = session.plan.duration_days,
        )
        if days:
            # Bug 2 fix: drop filler days where both distance and gain are
            # zero.  Groq sometimes appends "Day 2: No hiking planned — 0 mi,
            # 0 ft gain" for single-day trips; ItineraryParser was serialising
            # these as phantom DayPlan objects that showed up in the save summary.
            days = _drop_phantom_days(days)
        if days:
            session.plan.days = days
            logger.info(
                "Session %s: itinerary updated — %d day(s) parsed.",
                session.session_id, len(days),
            )

    # ── 9. Post-response check — catches Groq emitting DESTINATION RESET ───
    #
    # The full evaluate() is deliberately NOT called here.  Its phase-advance
    # logic would operate on the already-advanced session.phase and could
    # spuriously skip a phase (e.g. a user message like "let's go with option 2"
    # advances destination→gear_review in step 6, then in step 9 the same
    # "let's go" matches GEAR_DONE_SIGNALS in the now-active gear_review phase,
    # advancing gear_review→itinerary and silently skipping gear review).
    #
    # Step 9's only job is to catch the literal "DESTINATION RESET" token
    # that Groq emits when it detects an ambiguous destination-change phrase
    # the Python detector in step 6b missed.
    # ── 9. Post-response check ─────────────────────────────────────────────
    if not reset and "DESTINATION RESET" in ai_response:
        # Guard: if the user was re-selecting a numbered trail option,
        # Groq may have mis-fired DESTINATION RESET on "instead".
        # Don't honor the reset — re-run hike selection instead.
        if _is_trail_reselection(req.message, session):
            logger.info(
                "Session %s: suppressed false-positive DESTINATION RESET "
                "(message looks like trail re-selection).",
                session.session_id,
            )
            # Re-run selection logic exactly as step 5 does
            idx = PhaseController.extract_hike_selection(
                req.message,
                count=len(session.phase_data.get("hike_options", [])),
            )
            if idx is not None:
                session.plan.hike_id   = session.phase_data["hike_options"][idx]
                session.plan.hike_name = session.phase_data["hike_names"][idx]
                _promote_hike_gaps(session, str(session.plan.hike_id))
                # to_thread: same blocking DB + reverse-geocode as above.
                await asyncio.to_thread(_capture_selected_hike_facts, session)
                # Replace Groq's wrong-phase response with a clean trail-switch message.
                ai_response = (
                    f"Switching to {session.plan.hike_name} — "
                    "I've pulled the gear check for that trail instead. "
                    "Would you like to review the gaps, or are you good to proceed?"
                )
                # hike_id is now set on the same turn evaluate() already ran (step 6),
                # so without this the phase would only advance on the NEXT request —
                # same class of stuck-flow bug as the destination-plan fix above.
                if session.phase == "destination":
                    session.advance_phase()
                    _handle_phase_entry(session)
                    advanced = True
        else:
            _reset_destination(session)
            advanced = False
            logger.info(
                "Session %s: DESTINATION RESET caught in Groq response (post-response).",
                session.session_id,
            )
            ai_response = (
                "Got it — let's start fresh. "
                "Where would you like to go, and roughly how many days are you thinking?"
            )
    # ── 9a. GEAR ADD signal (post-response, gear_review only) ──────────────
    #
    # Groq emits "GEAR ADD: <category>" on its own line when the user confirms
    # they'll address a specific gap from the GEAR GAPS list. Items are
    # pre-computed — this never creates a new item row. Python maps the
    # category to a catalog item_type (CATEGORY_TO_ITEM_TYPE), looks up an
    # existing catalog item via ItemService, and links it to the user's gear
    # via UserService.add_item. The matching gap is removed from
    # plan.gear_gaps and its item id recorded in plan.gear_selected. The
    # token is stripped before the response reaches the frontend regardless
    # of whether the add succeeded.
    if session.phase == "gear_review" and "GEAR ADD:" in ai_response:
        for raw_category in _GEAR_ADD_RE.findall(ai_response):
            _handle_gear_add(
                session         = session,
                raw_category    = raw_category,
                item_service    = item_service,
                user_service    = user_service,
                current_user_id = current_user_id,
            )
        ai_response = _GEAR_ADD_RE.sub("", ai_response).strip()

    # ── 9d. ADVANCE_PHASE signal (post-response, gear_review/itinerary) ────
    #
    # PromptBuilder._rules() instructs Groq to append ADVANCE_PHASE when the
    # user's message genuinely approves moving on. Outside the SEARCH_REFINE
    # branch below, nothing ever consumed this token: the phase transition
    # was driven entirely by PhaseController's keyword regexes (evaluate(),
    # step 6), which don't cover every phrasing Groq itself understands as
    # approval (e.g. "that looks right" doesn't match ITINERARY_DONE_SIGNALS).
    # Result: the raw token leaked into the user-visible response AND the
    # phase silently failed to advance until a later message happened to
    # match one of the hardcoded phrases — the exact "conversation got
    # stuck" symptom. _structural_prerequisites_met() re-uses the same data
    # gate the regex path relies on, so this can't advance a phase early.
    if not advanced and "ADVANCE_PHASE" in ai_response:
        old_phase = session.phase
        if old_phase in ("gear_review", "itinerary") and _structural_prerequisites_met(session, itinerary_prebuilt):
            session.advance_phase()
            _handle_phase_entry(session)
            advanced = True
            logger.info(
                "Session %s: ADVANCE_PHASE signal — advancing %s → %s.",
                session.session_id, old_phase, session.phase,
            )
        else:
            logger.warning(
                "Session %s: ADVANCE_PHASE emitted but prerequisites not met "
                "(phase=%s, hike_id=%s, days=%d).",
                session.session_id, session.phase,
                session.plan.hike_id, len(session.plan.days),
            )
        ai_response = re.sub(r"\n?ADVANCE_PHASE\n?", "", ai_response).strip()

    # ── 9e. SEARCH_REFINE signal ───────────────────────────────────────────
#
# Groq emits SEARCH_REFINE when the user wants different criteria in the
# same destination (difficulty change, wants a water feature, etc.) — NOT
# a full destination change. Python:
#   1. Soft-resets hike selection (keeps lat/lng/destination/duration)
#   2. Updates difficulty if the user mentioned one
#   3. Re-runs the hike search with the updated plan state
#   4. Makes a second Groq call so the new options appear in THIS turn
#
# The second Groq call reuses Groq's own framing from the first response
# (stripped of the signal token) as a natural language intro before the
# new option list lands.
    # Guard: a card click / numbered pick this turn is a SELECTION, not a
    # refine request. On the selection turn the phase has just advanced to
    # gear_review, so Groq now sees the gear_review prompt — whose opening
    # instruction invites SEARCH_REFINE — and occasionally misfires it on the
    # bare "Option N" message. Honoring it would _soft_reset the just-made
    # selection back to the destination phase and desync session.phase from
    # Groq's conversational context for the rest of the chat. Strip the leaked
    # token and confirm the selection deterministically instead.
    if just_selected_hike and "SEARCH_REFINE" in ai_response:
        logger.info(
            "Session %s: ignoring SEARCH_REFINE on hike-selection turn "
            "(would have wiped the just-made selection).",
            session.session_id,
        )
        ai_response = ai_response.replace("SEARCH_REFINE", "").strip()
        hike_label = session.plan.hike_name or "that trail"
        ai_response = (
            f"Great choice — {hike_label} it is. "
            "Let me check your gear against this trail before we plan the days."
        )

    if not reset and not just_selected_hike and "SEARCH_REFINE" in ai_response:
        logger.info(
            "Session %s: SEARCH_REFINE signal — soft-resetting and re-searching.",
            session.session_id,
        )
        _soft_reset_hike_selection(session)

        # parse_refinement() instead of _parse_intent() — refinement messages
        # almost never name a destination, and _parse_intent's geocode failure
        # path discards the extracted tags along with it. parse_refinement()
        # never touches geocoding and never raises.
        refinement = _parser.parse_refinement(req.message)

        if _looks_like_affirmation(req.message):
            pivot = session.phase_data.pop("pivot_difficulty", None)
            if pivot:
                session.plan.difficulty = pivot
        elif refinement.required_tags or refinement.preferred_tags or refinement.priority_tags or refinement.difficulty_hint:
            if refinement.difficulty_hint:
                session.plan.difficulty = refinement.difficulty_hint
            # ── FIX 2a: only overwrite stored tags when the new parse has tags ──
            # Prevents "yeah, easier is fine" from wiping the water feature from
            # the prior turn — difficulty updates cleanly but tags are preserved.
            if refinement.required_tags or refinement.preferred_tags or refinement.priority_tags:
                session.phase_data["refine_required_tags"]  = refinement.required_tags
                session.phase_data["refine_preferred_tags"] = refinement.preferred_tags
                session.phase_data["refine_priority_tags"]  = refinement.priority_tags
        else:
            diff_match = _DIFFICULTY_RE.search(req.message)
            if diff_match:
                raw = diff_match.group(1).lower()
                session.plan.difficulty = "moderate" if raw == "medium" else raw

        refinement_intent = _intent_from_plan_with_override(
            session.plan,
            SimpleNamespace(
                activity_type     = getattr(refinement, "activity_type", None),
                difficulty_hint   = session.plan.difficulty,
                required_tags     = session.phase_data.get("refine_required_tags", []),
                preferred_tags    = session.phase_data.get("refine_preferred_tags", []),
                priority_tags     = session.phase_data.get("refine_priority_tags", []),
                avoid_permits     = getattr(refinement, "avoid_permits", False),
                max_length_km     = session.phase_data.get("refine_max_length_km"),      # ← NEW
                target_length_km  = session.phase_data.get("refine_target_length_km"),   # ← NEW
            ),
        )
        logger.info(
            "Session %s: SEARCH_REFINE resolved — difficulty=%r required=%s preferred=%s priority=%s",
            session.session_id, session.plan.difficulty,
            refinement_intent.required_tags, refinement_intent.preferred_tags,
            refinement_intent.priority_tags,
        )

        original_difficulty = session.plan.difficulty or "moderate"
        alt_difficulties    = [d for d in ["easy", "moderate", "hard"] if d != original_difficulty]
        hike_context        = _search_and_analyse(session, user_gear, refinement_intent)
        feature_tags        = list(refinement_intent.required_tags) + list(refinement_intent.priority_tags)

        # ── FIX 2b: check unmatched_concept_tags to decide whether to auto-expand ──
        # hike_context is non-empty even when water features aren't found (priority
        # filter falls through to the full list). We need unmatched_concept_tags to
        # distinguish "found hikes with the feature" from "found hikes without it".
        has_unmatched = bool(session.phase_data.get("unmatched_concept_tags"))

        refine_note = ""
        if hike_context and not has_unmatched:
            # Primary search returned hikes that satisfy the requested features.
            session.phase_data.pop("search_empty", None)
            refine_note = (
                "The hike search has been re-run with updated criteria. "
                "HIKE OPTIONS shows the new results. Present them directly. "
                "Do NOT emit SEARCH_REFINE."
            )
        elif feature_tags or has_unmatched:
            # ── FIX 2c: reset hike_context so the fallback block fires if the
            # loop can't find the feature at any difficulty.
            hike_context = ""
            for alt_diff in alt_difficulties:
                alt_intent = _intent_from_plan_with_override(
                    session.plan,
                    SimpleNamespace(
                        activity_type     = refinement_intent.activity_type,
                        difficulty_hint   = alt_diff,
                        required_tags     = list(refinement_intent.required_tags),
                        preferred_tags    = list(refinement_intent.preferred_tags),
                        priority_tags     = list(refinement_intent.priority_tags),
                        avoid_permits     = refinement_intent.avoid_permits,
                        max_length_km     = refinement_intent.max_length_km,      # ← NEW
                        target_length_km  = refinement_intent.target_length_km,   # ← NEW
                    ),
                )
                alt_context   = _search_and_analyse(session, user_gear, alt_intent)
                alt_unmatched = bool(session.phase_data.get("unmatched_concept_tags"))
                if alt_context and not alt_unmatched:
                    hike_context = alt_context
                    session.phase_data.pop("search_empty", None)
                    refine_note = (
                        f"No {original_difficulty} trails with the requested features were "
                        f"found in the database. Showing {alt_diff} trails with those features "
                        f"instead. Mention the difficulty change naturally in your response. "
                        f"Do NOT emit SEARCH_REFINE."
                    )
                    break
        if refinement.max_length_km is not None:
            session.phase_data["refine_max_length_km"]    = refinement.max_length_km
            session.phase_data["refine_target_length_km"] = refinement.target_length_km
        # ── Fallback: restore prior options when all searches came back empty ─────
        if not hike_context:
            prev_context = session.phase_data.pop("prev_hike_context", "")
            if prev_context:
                logger.info(
                    "Session %s: SEARCH_REFINE + auto-expand exhausted — "
                    "restoring prev options as fallback.",
                    session.session_id,
                )
                session.phase_data["hike_context"]      = prev_context
                session.phase_data["hike_options"]      = session.phase_data.pop("prev_hike_options", [])
                session.phase_data["hike_names"]        = session.phase_data.pop("prev_hike_names", [])
                session.phase_data["hike_list_display"] = session.phase_data.pop("prev_hike_list_display", "")  # ← NEW
                session.phase_data["hike_cards"]         = session.phase_data.pop("prev_hike_cards", [])
                session.phase_data["hikes_presented"]   = True
                session.phase_data.pop("search_empty", None)
                hike_context = prev_context
                if feature_tags:
                    refine_note = (
                        f"No trails with the requested features exist in the database near this "
                        f"destination (checked {original_difficulty} and "
                        f"{', '.join(alt_difficulties)}). "
                        f"Show the original options and tell the user plainly: that feature has "
                        f"no database coverage in this area. Suggest they try a different location "
                        f"or drop that requirement. "
                        f"Do NOT promise to search again. Do NOT emit SEARCH_REFINE."
                    )
                else:
                    refine_note = (
                        "No trails were found for the updated criteria. "
                        "Showing the original options. Do NOT emit SEARCH_REFINE."
                    )
            else:
                session.phase_data.pop("prev_hike_options", None)
                session.phase_data.pop("prev_hike_names", None)
                session.phase_data.pop("prev_hike_list_display", None)
                session.phase_data.pop("prev_hike_cards", None)
                session.phase_data.pop("search_empty", None)
                if not refine_note:
                    refine_note = (
                        "No trails were found for any of the requested criteria. "
                        "Tell the user and suggest trying a different area or adjusting "
                        "requirements. Do NOT emit SEARCH_REFINE."
                    )
        else:
            session.phase_data.pop("prev_hike_context", None)
            session.phase_data.pop("prev_hike_options", None)
            session.phase_data.pop("prev_hike_names", None)
            session.phase_data.pop("prev_hike_list_display", None)
            session.phase_data.pop("prev_hike_cards", None)

        # Strip SEARCH_REFINE from the first response, then make the second call
        # with a prompt that includes the search result note.
        ai_response = ai_response.replace("SEARCH_REFINE", "").strip()
        _refine_prompt = build_system_prompt(
            session, user_gear, hike_context=hike_context, refine_note=refine_note
        )
        try:
            ai_response, _ = _groq.chat(
                system_prompt   = _refine_prompt,
                summary         = session.summary,
                window_messages = session.get_window_messages(),
                user_message    = req.message,
                **PHASE_GROQ_PARAMS["destination"],
            )
            # Defensive strip — if Groq still emits SEARCH_REFINE despite the note,
            # prevent it from reaching the user or re-triggering the outer handler.
            ai_response = ai_response.replace("SEARCH_REFINE", "").strip()
        except Exception as e:
            logger.error(
                "Session %s: inline re-search after SEARCH_REFINE failed: %s",
                session.session_id, e,
            )
            # Fall through — user gets the stripped framing as a partial response
        else:
            if "ADVANCE_PHASE" in ai_response:
                logger.warning(
                    "Session %s: ADVANCE_PHASE emitted but prerequisites not met "
                    "(phase=%s, hike_id=%s, days=%d).",
                    session.session_id, session.phase,
                    session.plan.hike_id, len(session.plan.days),
                )
        ai_response = re.sub(r"\n?ADVANCE_PHASE\n?", "", ai_response).strip()
    # ── 9b. Detect SAVE CONFIRMED signal (finalize phase only) ────────────
    #
    # Groq is instructed to begin its response with the exact two words
    # "SAVE CONFIRMED" when the user confirms they want to save.
    # We check the start of the response (strip + uppercase) so minor
    # whitespace variations don't cause a miss.
    # The frontend uses save_confirmed=True to trigger POST /api/trip/save.
    #
    # Bug 3 fix: gate on finalize_summary_prebuilt so a user typing "save"
    # before they've seen the summary can't trigger a premature save.  The
    # PromptBuilder now also instructs Groq never to emit SAVE CONFIRMED in
    # sub-state 1, but this Python guard is the belt to that suspender.
    save_confirmed = (
        session.phase == "finalize"
        and ai_response.lstrip().upper().startswith("SAVE CONFIRMED")
        and finalize_summary_prebuilt
    )
    if save_confirmed:
        logger.info("Session %s: SAVE CONFIRMED signal received.", session.session_id)
    elif (
        session.phase == "finalize"
        and ai_response.lstrip().upper().startswith("SAVE CONFIRMED")
        and not finalize_summary_prebuilt
    ):
        logger.warning(
            "Session %s: suppressed premature SAVE CONFIRMED — "
            "trip summary not yet shown to user.",
            session.session_id,
        )

    # ── 9f. Hike-selection turn: strip any leaked list, guarantee a close-out ──
    #
    # The frontend renders HIKE OPTIONS as selectable cards/buttons (see
    # ChatResponse.hike_options) instead of a plain-text list, so Groq's
    # response should be reasoning + top picks + a close-out line — nothing
    # else. Despite _hike_context_block()'s "do NOT retype" instruction, Groq
    # sometimes echoes the raw stats/tags line anyway; strip any such lines
    # defensively so they don't show up as duplicate text above the buttons.
    # Also guarantees a close-out question if Groq's response got truncated
    # before writing one (destination sub-state 2 is token-capped — see
    # _resolve_groq_params).
    if (
        session.phase == "destination"
        and session.phase_data.get("hikes_presented")
        and not session.plan.hike_id
    ):
        ai_response = _LEAKED_HIKE_LINE_RE.sub("", ai_response).strip()
        if not ai_response.rstrip().endswith("?"):
            ai_response = ai_response.rstrip() + "\n\nWhich one would you like?"

    hike_options = (
        session.phase_data.get("hike_cards", [])
        if (
            session.phase == "destination"
            and session.phase_data.get("hikes_presented")
            and not session.plan.hike_id
        )
        else []
    )

    # ── 10. Append turn + async summarize if threshold crossed ─────────────
    session.add_turn(req.message, ai_response)

    if session.needs_summarization():
        asyncio.create_task(_async_summarize(session))

    # ── 11. Persist to Redis ───────────────────────────────────────────────
    if not _store.save(session):
        logger.error("Redis save failed for session %s", session.session_id)

    # ── 12. Return ─────────────────────────────────────────────────────────
    return ChatResponse(
        session_id     = session.session_id,
        response       = ai_response,
        phase          = session.phase,
        plan           = session.plan.to_dict(),
        advanced       = advanced,
        created        = created,
        save_confirmed = save_confirmed,
        hike_options   = hike_options,
    )


# ── Save endpoint ─────────────────────────────────────────────────────────────

@router.post("/save", response_model=SaveResponse)
def save_trip(
    session_id:      str,
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
    item_service:    ItemService = Depends(get_item_service),
):
    """
    Converts the completed AI session into persisted DB rows and cleans
    up the Redis session.

    Called by the frontend when the user confirms save in the finalize phase.
    session_id is passed as a query param: POST /api/trip/save?session_id=...
    """
    session = _store.get(session_id)
    logger.info(
        "save_trip: session_id=%s found=%s phase=%s destination_set=%s days=%d",
        session_id,
        session is not None,
        getattr(session, "phase", "N/A"),
        session.plan.is_destination_set() if session else False,
        len(session.plan.days) if session else 0,
    )
    if not session:
        raise HTTPException(404, "Session not found or expired.")

    if session.user_id != current_user_id:
        raise HTTPException(403, "Forbidden.")

    if session.phase != "finalize":
        raise HTTPException(400, "Trip is not ready to save yet.")

    if not session.plan.is_destination_set():
        raise HTTPException(400, "Trip destination is incomplete.")

    # The user's current kit becomes the trip's "packed" gear list. Best-effort:
    # if this lookup fails, save_from_session falls back to plan.gear_selected.
    try:
        owned_item_ids = [str(item.id) for item in item_service.list_by_user(UUID(current_user_id))]
    except Exception as e:
        logger.warning("save_trip: could not load owned gear for user %s: %s", current_user_id, e)
        owned_item_ids = None

    try:
        trip = service.save_from_session(
            user_id        = UUID(current_user_id),
            session        = session,
            owned_item_ids = owned_item_ids,
        )
        _store.delete(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("save_from_session failed: %s", e)
        raise HTTPException(500, "Failed to save trip.")
    return SaveResponse(
        trip_id = str(trip.id),
        title   = trip.title,
        stops   = [s.to_dict() for s in trip.stops],
        gear    = [g.to_dict() for g in trip.gear],
    )


# ── Chat history endpoints ─────────────────────────────────────────────────────
#
# "Chat" here spans two stores: an in-progress conversation lives only in
# Redis (status=active); the moment it's saved (see save_trip above,
# status="saved"), Postgres's trips table becomes the system of record —
# there is no separate chat_sessions table. See migrations/001_trips_lifecycle.sql
# for why trips was extended instead of introducing a parallel table.

def _chat_title(session: TripSession) -> str:
    """Same fallback TripService.save_from_session uses for trip.title —
    kept in sync manually since an active session has no title field of
    its own (it's derived, not stored, until the trip is actually saved)."""
    return session.plan.hike_name or session.plan.destination_full or "New trip"


@router.get("/chats", response_model=list[ChatSummary])
def list_chats(
    status:          Optional[str] = None,   # comma-separated, e.g. "active,saved"
    current_user_id: str           = Depends(get_current_user_id),
    service:         TripService   = Depends(get_service),
):
    """
    Lists this user's chats across both stores, newest-updated first.
    status defaults to all four states when omitted.
    """
    requested = (
        [s.strip() for s in status.split(",") if s.strip()]
        if status else sorted(_VALID_CHAT_STATUSES)
    )
    invalid = [s for s in requested if s not in _VALID_CHAT_STATUSES]
    if invalid:
        raise HTTPException(400, f"Invalid status value(s): {', '.join(invalid)}")

    summaries: list[ChatSummary] = []

    if "active" in requested:
        for session in _store.list_active(current_user_id):
            summaries.append(ChatSummary(
                id         = session.session_id,
                status     = "active",
                title      = _chat_title(session),
                created_at = session.created_at,
                updated_at = session.updated_at,
                phase      = session.phase,
            ))

    pg_statuses = [s for s in requested if s != "active"]
    if pg_statuses:
        # hydrate=False — the list view only needs title/status/timestamps,
        # not each trip's full stops/gear (that's what GET /chats/{id} is for).
        trips = service.list_user_trips(
            UUID(current_user_id), statuses=pg_statuses, hydrate=False,
        )
        # One batch lookup instead of N+1 — only reviewed trips will ever
        # have a rated hike_completions row, but it's cheap to just ask for
        # everyone in one shot rather than filtering first.
        ratings = service.get_ratings([trip.id for trip in trips])
        for trip in trips:
            summaries.append(ChatSummary(
                id           = str(trip.id),
                status       = trip.status,
                title        = trip.title,
                created_at   = trip.created_at.isoformat() if trip.created_at else None,
                updated_at   = trip.updated_at.isoformat() if trip.updated_at else None,
                needs_review = trip.needs_review,
                rating       = ratings.get(str(trip.id)),
            ))

    summaries.sort(key=lambda s: s.updated_at or "", reverse=True)
    return summaries


def _trip_readiness(trip, current_user_id: str, item_service: ItemService) -> list[dict]:
    """
    Live gear readiness for a saved trip: the trail's required gear vs the user's
    CURRENT kit, so it reflects gear added since the trip was saved. Best-effort —
    returns [] (no checklist) rather than erroring if the hike or gear can't load.
    """
    stop  = trip.stops[0] if getattr(trip, "stops", None) else None
    trail = (stop.trail_data or {}) if stop else {}
    hike_id = trail.get("hike_id")
    if not hike_id:
        return []
    try:
        hike = _hike_service.get_hike(UUID(str(hike_id)))
    except Exception as e:
        logger.warning("readiness: could not load hike %s: %s", hike_id, e)
        return []
    if not hike or not getattr(hike, "gear_requirements", None):
        return []
    try:
        user_gear = _load_user_gear(current_user_id, item_service)
    except Exception as e:
        logger.warning("readiness: could not load gear for %s: %s", current_user_id, e)
        return []
    return _analyzer.readiness_for_hike(user_gear, hike)


@router.get("/chats/{chat_id}", response_model=dict)
def get_chat(
    chat_id:         str,
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
    item_service:    ItemService = Depends(get_item_service),
):
    """
    Fetches one chat. Redis is checked first since an active session's
    session_id never appears in Postgres at all; anything not found there
    is looked up as a saved/completed/reviewed trip instead.
    """
    session = _store.get(chat_id)
    if session:
        if session.user_id != current_user_id:
            raise HTTPException(403, "Forbidden.")
        # Mirrors the /chat endpoint's hike_options gating — without this,
        # resuming a session mid-selection would lose its option buttons
        # until the next message.
        hike_options = (
            session.phase_data.get("hike_cards", [])
            if (
                session.phase == "destination"
                and session.phase_data.get("hikes_presented")
                and not session.plan.hike_id
            )
            else []
        )
        return {
            "id":           session.session_id,
            "status":       "active",
            "title":        _chat_title(session),
            "phase":        session.phase,
            "plan":         session.plan.to_dict(),
            "messages":     session.get_window_messages(),
            "created_at":   session.created_at,
            "updated_at":   session.updated_at,
            "hike_options": hike_options,
        }

    trip = _owned_chat_trip(chat_id, current_user_id, service)
    result = trip.to_dict()
    if trip.status in ("completed", "reviewed"):
        completion = service.get_completion(trip.id)
        result["completion"] = completion.to_dict() if completion else None
    # Live per-trail gear readiness for the "double-check before you go" checklist.
    result["readiness"] = _trip_readiness(trip, current_user_id, item_service)
    return result


def _owned_chat_trip(chat_id: str, current_user_id: str, service: TripService) -> Trip:
    """
    Shared lookup for the Postgres-only chat actions (mark-done, review) —
    same 404/403 shape as get_chat's Postgres branch and TripController's
    _owned_trip, minus the Redis check (none of these actions are valid on
    an active session; there's no trip row yet to act on).
    """
    try:
        trip_uuid = UUID(chat_id)
    except ValueError:
        raise HTTPException(404, "Chat not found.")

    try:
        trip = service.get_trip(trip_uuid)
    except ValueError:
        raise HTTPException(404, "Chat not found.")

    if str(trip.user_id) != current_user_id:
        raise HTTPException(403, "Forbidden.")

    return trip


@router.post("/chats/{chat_id}/complete", response_model=dict)
def complete_chat(
    chat_id:         str,
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
):
    """'Mark as done' — saved -> completed. The review questionnaire (and
    the needs_review nudge, N days later) only becomes reachable after this."""
    trip = _owned_chat_trip(chat_id, current_user_id, service)
    try:
        trip = service.mark_completed(trip)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return trip.to_dict()


@router.post("/chats/{chat_id}/review", response_model=dict)
def review_chat(
    chat_id:         str,
    payload:         ReviewRequest,
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
):
    """Questionnaire submission — completed -> reviewed. Writes hike_completions."""
    trip = _owned_chat_trip(chat_id, current_user_id, service)
    try:
        completion = service.submit_review(
            trip,
            went            = payload.went,
            difficulty_felt = payload.difficulty_felt,
            elevation_felt  = payload.elevation_felt,
            rating          = payload.rating,
            notes           = payload.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return completion.to_dict()


@router.get("/past-hikes/stats", response_model=dict)
def past_hikes_stats(
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
):
    """Aggregate header for the Past Hikes page — hike_count, total_miles,
    favorite_region. See TripService.get_past_hikes_stats for what's derived
    from where."""
    return service.get_past_hikes_stats(UUID(current_user_id))


@router.post("/chats/{chat_id}/duplicate", response_model=DuplicateResponse)
def duplicate_chat(
    chat_id:         str,
    current_user_id: str          = Depends(get_current_user_id),
    service:         TripService  = Depends(get_service),
    item_service:    ItemService  = Depends(get_item_service),
):
    """
    "Go Again" — clones a saved/completed/reviewed trip's search criteria
    into a brand-new active (Redis) session and re-runs the search live
    against current trail data, rather than replaying the original hike_id
    or cached results. Trail data (gear requirements, tags, which hikes
    even still exist) may have changed since the original session, so
    replaying what was shown then risks surfacing stale or wrong info —
    only the *criteria* are cloned, not the answer.
    """
    trip = _owned_chat_trip(chat_id, current_user_id, service)
    stop = trip.stops[0] if trip.stops else None
    if not stop:
        raise HTTPException(400, "This trip has no destination data to duplicate.")

    trail = stop.trail_data or {}

    try:
        user_gear = _load_user_gear(current_user_id, item_service)
    except Exception as e:
        logger.error("duplicate_chat: failed to load gear for user %s: %s", current_user_id, e)
        raise HTTPException(500, "Could not load gear data.")

    try:
        session, _ = _store.get_or_create(session_id=None, user_id=current_user_id)
    except SessionStoreUnavailable:
        raise HTTPException(503, "Session service is temporarily unavailable. Please try again in a moment.")

    plan = session.plan
    plan.destination_full = trail.get("destination") or stop.destination
    plan.lat               = stop.lat
    plan.lng               = stop.lng
    plan.state              = trail.get("state")
    plan.max_length_km      = trail.get("max_length_km")
    plan.target_length_km   = trail.get("target_length_km")
    plan.activity_type      = trail.get("activity_type") or stop.activity_type
    plan.duration_days      = trail.get("duration_days") or stop.duration_days
    plan.difficulty         = trail.get("difficulty")
    plan.required_tags      = list(trail.get("required_tags") or [])
    plan.preferred_tags     = list(trail.get("preferred_tags") or [])
    plan.priority_tags      = list(trail.get("priority_tags") or [])

    # destination_type isn't persisted in trail_data — heuristic: a state
    # means this was a region-scoped search (proximity matters less); no
    # state means it was a point search (e.g. "near me", proximity matters
    # a lot). See HikeSearchService.find_hikes_for_intent's proximity_weight.
    intent = SimpleNamespace(
        lat               = plan.lat,
        lng               = plan.lng,
        destination_full  = plan.destination_full,
        destination_type  = "region" if plan.state else "point",
        activity_type     = plan.activity_type or "hiking",
        duration_days     = plan.duration_days,
        difficulty_hint   = plan.difficulty,
        required_tags     = plan.required_tags,
        preferred_tags    = plan.preferred_tags,
        priority_tags     = plan.priority_tags,
        avoid_permits     = False,
        region_tag        = None,
        state             = plan.state,
        max_length_km     = plan.max_length_km,
        target_length_km  = plan.target_length_km,
    )

    _search_and_analyse(session, user_gear, intent)

    destination_label = plan.destination_full or trip.title
    if session.phase_data.get("hike_cards"):
        response_text = (
            f"Let's do {destination_label} again — here's what's currently available. "
            "Which one sounds good?"
        )
    else:
        response_text = (
            f"Trying {destination_label} again, but nothing matches the original criteria "
            "in the current data. Want to adjust and search again?"
        )

    session.add_turn(f"Go again: {trip.title}", response_text)
    if not _store.save(session):
        logger.error("duplicate_chat: Redis save failed for session %s", session.session_id)

    return DuplicateResponse(
        session_id   = session.session_id,
        response     = response_text,
        phase        = session.phase,
        plan         = plan.to_dict(),
        hike_options = session.phase_data.get("hike_cards", []),
    )


# ── Private: destination-phase helpers ────────────────────────────────────────



def _looks_like_affirmation(message: str) -> bool:
    msg = message.strip().lower().rstrip(".!")
    return msg in _AFFIRMATION_PHRASES or (
        len(msg.split()) <= 3
        and any(p in msg for p in ("yes", "yeah", "yep", "yup", "sure", "ok", "okay"))
    )
def _soft_reset_hike_selection(session: TripSession) -> None:
    """
    Preserves destination (lat/lng/destination_full/duration_days) but clears
    hike selection, gear analysis, and itinerary state so a fresh search can run.
    Used when the user wants different trail criteria in the same area.
    """
    session.phase_data["prev_hike_context"]      = session.phase_data.get("hike_context", "")
    session.phase_data["prev_hike_options"]      = list(session.phase_data.get("hike_options", []))
    session.phase_data["prev_hike_names"]        = list(session.phase_data.get("hike_names", []))
    session.phase_data["prev_hike_list_display"] = session.phase_data.get("hike_list_display", "")
    session.phase_data["prev_hike_cards"]        = session.phase_data.get("hike_cards", [])
    session.plan.hike_id          = None
    session.plan.hike_name        = None
    session.plan.gear_gaps        = []
    session.plan.gear_finalized   = False
    session.plan.days             = []
    session.plan.itinerary_approved = False
    session.phase                 = "destination"
    for key in (
        "hikes_presented", "hike_options", "hike_names",
        "hike_context", "hike_list_display", "hike_cards", "gear_analyses", "search_attempted", "search_empty",
        "drive_distance_asked",
    ):
        session.phase_data.pop(key, None)
    logger.info(
        "Session %s: soft hike reset — destination preserved, search state cleared.",
        session.session_id,
    )


def _intent_from_plan(plan) -> TripIntent:
    """
    Reconstructs a TripIntent from the current plan's confirmed destination.
    Used for search refinements where the destination is already known.
    """
    return TripIntent(
        destination_full = plan.destination_full,
        destination_raw  = plan.destination_full,
        raw_goal         = "",
        lat              = plan.lat,
        lng              = plan.lng,
        destination_type = "region",
        activity_type    = plan.activity_type or "hiking",
        duration_days    = plan.duration_days,
        difficulty_hint  = plan.difficulty,
        state            = plan.state,           # ← NEW
        max_length_km     = plan.max_length_km,       # ← NEW
        target_length_km  = plan.target_length_km,
    )


def _intent_from_plan_with_override(plan, refinement: "RefinementIntent"):
    """
    Merges confirmed destination coordinates with freshly parsed preferences
    from a re-parsed TripIntent.  Returns a SimpleNamespace that satisfies
    HikeSearchService.find_hikes_for_intent() — the same pattern used by
    HikeSearchService's own fallback_intent internally.

    Keeps lat/lng/destination from the confirmed plan (so the search stays in
    the same geographic area) but adopts new tag preferences, priority tags,
    and difficulty from re_intent (so "water feature", "I really want a water
    feature", "harder", etc. are not lost).
    """
    return SimpleNamespace(
        lat               = plan.lat,
        lng               = plan.lng,
        destination_full  = plan.destination_full,
        destination_raw   = plan.destination_full,
        raw_goal          = "",
        destination_type  = "region",
        activity_type     = refinement.activity_type or plan.activity_type or "hiking",
        duration_days     = plan.duration_days,
        difficulty_hint   = refinement.difficulty_hint or plan.difficulty,
        required_tags     = list(refinement.required_tags or []),
        preferred_tags    = list(refinement.preferred_tags or []),
        priority_tags     = list(refinement.priority_tags or []),
        avoid_permits     = refinement.avoid_permits,
        state             = getattr(plan, "state", None),
        max_length_km     = getattr(refinement, "max_length_km", None) or plan.max_length_km,        # ← NEW
        target_length_km  = getattr(refinement, "target_length_km", None) or plan.target_length_km,  # ← NEW
    )
def _handle_gear_add(
    session:         TripSession,
    raw_category:    str,
    item_service:    ItemService,
    user_service:    UserService,
    current_user_id: str,
) -> None:
    """
    Resolves a "GEAR ADD: <category>" signal into a real catalog item and
    links it to the user's gear.

    Items are pre-computed — this NEVER creates a new item row. It only
    looks up an existing catalog item (via ItemService.list_items) and links
    it to the user (via UserService.add_item), then updates
    plan.gear_selected / plan.gear_gaps. Any failure is logged and the
    signal is dropped silently — the conversation continues unaffected.
    """
    # Normalize: lowercase, collapse any non a-z run (spaces, punctuation)
    # to a single underscore, so "first aid" / "first aid." / "First Aid"
    # all become "first_aid", matching GearGap.category values.
    category = re.sub(r"[^a-z_]+", "_", raw_category.strip().lower()).strip("_")

    gap = next((g for g in session.plan.gear_gaps if g.category == category), None)
    if gap is None:
        logger.warning(
            "Session %s: GEAR ADD for unknown/already-resolved category '%s' — ignoring.",
            session.session_id, category,
        )
        return

    item_type = CATEGORY_TO_ITEM_TYPE.get(category)
    if item_type is None:
        logger.warning(
            "Session %s: no item_type mapping for gear category '%s' — ignoring GEAR ADD.",
            session.session_id, category,
        )
        return

    try:
        catalog_items = item_service.list_items(item_type=item_type)
    except Exception as e:
        logger.warning(
            "Session %s: catalog lookup failed for item_type '%s': %s",
            session.session_id, item_type, e,
        )
        return

    # "clothing" backs both insulation and rain_gear — narrow by waterproof.
    if category == CAT_RAIN_GEAR:
        catalog_items = [i for i in catalog_items if getattr(i, "waterproof", False)]
    elif category == CAT_INSULATION:
        catalog_items = [i for i in catalog_items if not getattr(i, "waterproof", False)]

    if not catalog_items:
        logger.warning(
            "Session %s: no catalog item found for category '%s' (item_type=%s) — ignoring GEAR ADD.",
            session.session_id, category, item_type,
        )
        return

    chosen = catalog_items[0]

    try:
        user_service.add_item(UUID(current_user_id), str(chosen.id))
    except Exception as e:
        logger.error(
            "Session %s: failed to link item %s to user %s: %s",
            session.session_id, chosen.id, current_user_id, e,
        )
        return

    session.plan.gear_selected.append(str(chosen.id))
    session.plan.gear_gaps = [g for g in session.plan.gear_gaps if g.category != category]

    logger.info(
        "Session %s: linked '%s' (item_type=%s) to user gear, resolving category '%s'.",
        session.session_id, chosen.name, item_type, category,
    )
def _parse_intent(req: ChatRequest) -> Optional[TripIntent]:
    """
    Single authoritative parse call — preserves coordinates.
    Returns None on any parse failure rather than raising.
    """
    try:
        return _parser.parse(
            req.message,
            user_lat=req.user_lat,
            user_lng=req.user_lng,
        )
    except ValueError as e:
        logger.info("Parser could not resolve destination: %s", e)
    except Exception as e:
        logger.warning("Parser error: %s", e)
    return None


def _search_and_analyse(
    session:   TripSession,
    user_gear: list[dict],
    intent:    TripIntent,
) -> str:
    try:
        result = _hike_search.find_hikes_with_fallback(intent)
    except Exception as e:
        logger.warning("HikeSearchService failed: %s", e)
        return ""

    if not result.scored:
        logger.info("HikeSearchService returned no results for intent: %s", intent)
        session.phase_data["search_attempted"] = True
        session.phase_data["search_empty"] = True
        session.phase_data["unmatched_concept_tags"] = []   # ← NEW
        session.phase_data["hike_list_display"]  = ""
        return _hike_search.format_for_context([], search_result=result)

    if result.unmatched_concept_tags:
        pivot = _DIFFICULTY_PIVOT.get(result.difficulty_hint)
        if pivot:
            session.phase_data["pivot_difficulty"] = pivot
    else:
        session.phase_data.pop("pivot_difficulty", None)

    gear_analyses: dict[str, list[GearGap]] = {}
    for hike, _ in result.scored:
        try:
            gear_analyses[str(hike.id)] = _analyzer.analyze_for_hike(user_gear, hike)
        except Exception as e:
            logger.warning("GearGapAnalyzer failed for hike %s: %s", hike.id, e)
            gear_analyses[str(hike.id)] = []

    session.phase_data["gear_analyses"] = {
        hike_id: [_gap_to_dict(g) for g in gaps]
        for hike_id, gaps in gear_analyses.items()
    }

    _controller.on_hikes_presented(session, result.scored)

    context = _hike_search.format_for_context(
        result.scored,
        gear_analyses=gear_analyses,
        search_result=result,
    )
    session.phase_data["hike_list_display"] = _hike_search.format_hike_list(
        result.scored, gear_analyses
    )
    session.phase_data["hike_cards"] = _hike_search.to_option_cards(
        result.scored, gear_analyses
    )
    logger.debug("Session %s: hike_context =\n%s", session.session_id, context)
    session.phase_data["hike_context"]           = context
    session.phase_data["unmatched_concept_tags"] = result.unmatched_concept_tags
    return context

# ── Named-trail request lookup ────────────────────────────────────────────────
#
# The default destination flow geocodes the user's text and runs a *filtered*
# search — it never looks a trail up by its own name. When the user names a
# specific trail ("I want to hike Mount Sterling Trail", or the "Plan a trip to
# <name>" button, which sends "I want to plan a trip to <name>."), we short-
# circuit to a direct DB name lookup instead. Capture group 1 = the trail-name
# candidate that follows the lead-in.
_HIKE_NAME_REQUEST_PATTERNS = [
    re.compile(r"\bplan(?:ning)?\s+(?:a\s+|the\s+)?(?:trip|hike|visit)\s+(?:to|for|on|around)\s+(.+)", re.I),
    re.compile(r"\bi(?:'d| would)?\s*(?:really\s+)?(?:want|wanna|like|love)\s+to\s+(?:hike|do|climb|tackle|visit)\s+(.+)", re.I),
    re.compile(r"\blet'?s\s+(?:hike|do|tackle|climb)\s+(.+)", re.I),
    re.compile(r"\btake\s+me\s+(?:to|up)\s+(.+)", re.I),
]

# Candidate tails starting with these tokens are region / relative-location
# phrases ("in the mountains", "near boston"), not a proper trail name — reject
# so the normal geocode/filter flow handles them.
_NAME_QUERY_REJECT_START = re.compile(
    r"^(?:in|near|around|by|close|somewhere|anywhere|something|anything|a\s+place)\b", re.I
)

# Generic descriptors ("a moderate loop", "a nice hike") — a filtered search in
# disguise, not a named trail. Rejected so we don't hijack them into a name
# lookup (and a spurious "couldn't find that trail" reply). Anchored to the whole
# string, so it only catches a *bare* descriptor — the checks below handle
# descriptors that carry a trailing qualifier ("a scenic trail by the coast").
_GENERIC_DESC_RE = re.compile(
    r"^(?:a|an|some|the)?\s*"
    r"(?:easy|moderate|hard|difficult|challenging|tough|strenuous|short|long|"
    r"quick|nice|good|great|scenic|beautiful|fun|pretty)?\s*"
    r"(?:day\s+)?(?:hike|trail|loop|walk|trip|path|route|adventure|trek)s?$",
    re.I,
)

# A proper trail name never opens with an indefinite article/quantifier — those
# introduce a *description* ("a scenic trail…", "an easy hike…", "some loop…"),
# which _GENERIC_DESC_RE misses once a trailing qualifier defeats its end anchor.
# ("the" is already stripped from the candidate before this runs.)
_INDEFINITE_START_RE = re.compile(r"^(?:a|an|some)\b", re.I)

# A spatial / criteria preposition anywhere in the candidate marks a filtered-
# search phrase ("… by the coast", "trail near boston", "hike with a waterfall"),
# not a proper name — proper trail names almost never contain these words.
_CRITERIA_PREP_RE = re.compile(r"\b(?:near|around|by|with|without|along)\b", re.I)

# A bare geographic-feature / region word ("the mountains" → "mountains") is a
# region, not a named trail. Whole-string match only, so a name that merely
# contains one of these ("Blue Hills") is untouched.
_BARE_REGION_RE = re.compile(
    r"^(?:mountains?|coast|woods|forest|wilderness|desert|beach|hills|"
    r"outdoors|nature|wilds?|countryside)$",
    re.I,
)


def _extract_hike_name_query(message: str) -> Optional[str]:
    """
    If `message` reads as a request to hike a *specific, named* trail, return the
    cleaned trail-name candidate; otherwise None. Deliberately strict: only fires
    on explicit "hike/do/plan a trip to <X>" lead-ins, and rejects candidates
    that are really region phrases ("in the mountains") or generic descriptors
    ("a moderate loop") so a normal filtered search isn't hijacked.
    """
    text = (message or "").strip()
    if not text:
        return None
    for pat in _HIKE_NAME_REQUEST_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        candidate = m.group(1).strip()
        candidate = re.sub(r"[.!?,;:\s]+$", "", candidate)          # trailing punctuation
        candidate = re.sub(r"[,\s]+please$", "", candidate, flags=re.I).strip()
        candidate = re.sub(r"^the\s+", "", candidate, flags=re.I).strip()   # "the X Trail" → "X Trail"
        if len(candidate) < 3:
            return None
        if _NAME_QUERY_REJECT_START.match(candidate):
            return None
        if _GENERIC_DESC_RE.match(candidate):
            return None
        if _INDEFINITE_START_RE.match(candidate):                  # "a scenic trail …"
            return None
        if _CRITERIA_PREP_RE.search(candidate):                    # "… near/by/with …"
            return None
        if _BARE_REGION_RE.match(candidate):                       # "the mountains" → region
            return None
        if not re.search(r"[a-zA-Z]{3,}", candidate):              # needs a real word
            return None
        return candidate
    return None


def _normalize_name(s: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for name comparison."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _resolve_named_hike(query: str):
    """
    Look a trail up by name and decide how confident the match is.

    Returns:
        (hike, None)        — one confident match (auto-select it)
        (None, candidates)  — several plausible matches (disambiguate; len >= 2)
        (None, [])          — nothing found (ask the user to describe it)
    """
    try:
        candidates = _hike_service.search_hikes_by_name(query, limit=5)
    except Exception as e:
        logger.warning("Name lookup failed for %r: %s", query, e)
        return None, []
    if not candidates:
        return None, []

    qn = _normalize_name(query)

    # Exact (normalized) name match wins outright.
    exact = [h for h in candidates if _normalize_name(h.name) == qn]
    if len(exact) == 1:
        return exact[0], None

    if len(candidates) == 1:
        return candidates[0], None

    # Rank by fuzzy similarity; a clear leader is treated as confident.
    scored = sorted(
        candidates,
        key=lambda h: difflib.SequenceMatcher(None, qn, _normalize_name(h.name)).ratio(),
        reverse=True,
    )
    best   = difflib.SequenceMatcher(None, qn, _normalize_name(scored[0].name)).ratio()
    second = difflib.SequenceMatcher(None, qn, _normalize_name(scored[1].name)).ratio()
    if best >= 0.72 and (best - second) >= 0.15:
        return scored[0], None
    return None, scored


def _analyse_and_store_gaps(session: TripSession, user_gear: list[dict], hikes: list) -> dict:
    """Run per-hike gear analysis for `hikes`, cache dict-form gaps in phase_data
    (as _search_and_analyse does), and return {hike_id: [GearGap]}."""
    gear_analyses: dict[str, list] = {}
    for hike in hikes:
        try:
            gear_analyses[str(hike.id)] = _analyzer.analyze_for_hike(user_gear, hike)
        except Exception as e:
            logger.warning("GearGapAnalyzer failed for hike %s: %s", hike.id, e)
            gear_analyses[str(hike.id)] = []
    session.phase_data["gear_analyses"] = {
        hid: [_gap_to_dict(g) for g in gaps] for hid, gaps in gear_analyses.items()
    }
    return gear_analyses


def _select_named_hike(session: TripSession, user_gear: list[dict], hike) -> None:
    """
    Direct one-shot select of a named trail: present-then-pick in a single turn.
    Mirrors the card-click path (step 5) so the phase machine — which gates on
    hikes_presented + hike_id — auto-advances destination → gear_review on the
    following evaluate() call. Populates plan.gear_gaps + authoritative hike facts.
    """
    _controller.on_hikes_presented(session, [(hike, 1)])
    _analyse_and_store_gaps(session, user_gear, [hike])

    session.plan.hike_id   = str(hike.id)
    session.plan.hike_name = hike.name
    session.plan.lat       = hike.lat
    session.plan.lng       = hike.lng
    if not session.plan.duration_days:
        session.plan.duration_days = 1

    _promote_hike_gaps(session, str(hike.id))
    _capture_selected_hike_facts(session)


def _present_named_candidates(session: TripSession, user_gear: list[dict], candidates: list) -> str:
    """
    Present several name matches as selectable option cards for disambiguation —
    same shape as a normal search result, so clicking a card ("2") flows through
    the existing selection path. Returns the Groq context string.
    """
    scored = [(h, 1) for h in candidates]
    gear_analyses = _analyse_and_store_gaps(session, user_gear, candidates)

    _controller.on_hikes_presented(session, scored)
    context = _hike_search.format_for_context(scored, gear_analyses=gear_analyses)
    session.phase_data["hike_list_display"] = _hike_search.format_hike_list(scored, gear_analyses)
    session.phase_data["hike_cards"]        = _hike_search.to_option_cards(scored, gear_analyses)
    session.phase_data["hike_context"]      = context
    return context


def _is_trail_reselection(message: str, session: TripSession) -> bool:
    """
    Returns True if the message looks like the user is picking a different
    numbered trail from the options already presented — not changing destination.
    Only meaningful when hike options have been presented this session.
    """
    # extract_hike_selection returns a valid index → it's a numbered pick
    if not session.phase_data.get("hikes_presented"):
        return False
    count = len(session.phase_data.get("hike_options", []))   # ← no trailing comma
    return PhaseController.extract_hike_selection(message, count=count) is not None
def _promote_hike_gaps(session: TripSession, hike_id: str) -> None:
    """
    Converts the stored dict-form gaps for the selected hike back to GearGap
    objects and writes them to plan.gear_gaps.

    Called at hike selection time so plan.gear_gaps is populated before the
    phase transitions to gear_review.
    """
    raw_gaps = session.phase_data.get("gear_analyses", {}).get(hike_id, [])
    session.plan.gear_gaps = [_dict_to_gap(g) for g in raw_gaps]


# Matches the crude "Near your current location" / "near me" destination label
# TripInputParser emits when no place was named — the trigger to upgrade it to
# the trailhead's real place via reverse geocoding.
_CRUDE_DESTINATION_RE = re.compile(r"^\s*near\b", re.IGNORECASE)


def _capture_selected_hike_facts(session: TripSession) -> None:
    """
    At hike selection, pull the chosen trail's authoritative stats from the DB
    onto the plan so the finalize summary and the saved trip reflect the REAL
    hike — not the user's original search filters or the LLM's guesses.

    Sets plan.difficulty (real DB difficulty — authoritative for a single-hike
    trip), plan.hike_length_km, plan.hike_elevation_gain_m, and a Naismith
    on-trail-time estimate (plan.estimated_duration). Also upgrades a crude
    "Near your current location" destination to the trailhead's real place label
    via a single reverse-geocode call (falls back to the hike's region on
    failure). Best-effort: any lookup failure leaves the plan untouched.
    """
    plan = session.plan
    if not plan.hike_id:
        return
    try:
        hike = _hike_service.get_hike(UUID(str(plan.hike_id)))
    except Exception as e:
        logger.warning("Could not load selected hike %s for facts: %s", plan.hike_id, e)
        return
    if hike is None:
        return

    plan.hike_length_km        = hike.length_km
    plan.hike_elevation_gain_m = hike.elevation_gain_m

    # Real trail difficulty is authoritative for a single-hike trip — the user's
    # difficulty filter was only ever a search hint.
    try:
        plan.difficulty = hike.difficulty.name.lower()
    except AttributeError:
        plan.difficulty = str(hike.difficulty).lower()

    _hours, label = estimate_hike_duration(hike.length_km, hike.elevation_gain_m)
    plan.estimated_duration = label

    # Upgrade a crude / "near me" destination to the trailhead's real place.
    if not plan.destination_full or _CRUDE_DESTINATION_RE.match(plan.destination_full):
        place = reverse_geocode(getattr(hike, "lat", None), getattr(hike, "lng", None))
        plan.destination_full = place or hike.region or plan.destination_full or hike.name

    logger.info(
        "Session %s: captured hike facts — %.1f km, %.0f m gain, difficulty=%s, "
        "est=%s, destination=%r",
        session.session_id, hike.length_km, hike.elevation_gain_m,
        plan.difficulty, plan.estimated_duration, plan.destination_full,
    )


# ── Private: general helpers ──────────────────────────────────────────────────
def _merge_accum_tags(
    session, required, preferred, priority,
    difficulty_hint=None, max_length_km=None, target_length_km=None,
) -> None:    
    """
    Accumulates feature/priority tags across turns in the destination-gathering
    phase (before is_destination_set()). Needed because each turn is parsed from
    that turn's raw text only — without this, "summit hike" followed by "in NC"
    silently drops the summit requirement the moment the second turn re-parses.
    """
    session.phase_data["accum_required_tags"]  = sorted(set(session.phase_data.get("accum_required_tags", []))  | set(required))
    session.phase_data["accum_preferred_tags"] = sorted(set(session.phase_data.get("accum_preferred_tags", [])) | set(preferred))
    session.phase_data["accum_priority_tags"]  = sorted(set(session.phase_data.get("accum_priority_tags", []))  | set(priority))
    if difficulty_hint:
        session.phase_data["accum_difficulty_hint"] = difficulty_hint
    if max_length_km is not None:
        session.phase_data["accum_max_length_km"] = max_length_km
    if target_length_km is not None:
        session.phase_data["accum_target_length_km"] = target_length_km
def _apply_intent_to_plan(
    session:              TripSession,
    intent:               TripIntent,
    destination_override: Optional[str] = None,
) -> None:
    """
    Write a parsed TripIntent into the active plan.

    destination_override lets callers substitute a display-safe name when
    the parser's destination_full looks like a trail-system name rather than
    the geographic region the user asked for (see _resolve_destination_display).
    """
    plan                  = session.plan
    plan.destination_full = (
        destination_override if destination_override is not None
        else intent.destination_full
    )
    plan.lat               = intent.lat
    plan.lng               = intent.lng
    plan.state              = intent.state
    plan.max_length_km      = getattr(intent, "max_length_km", None)      # ← NEW
    plan.target_length_km   = getattr(intent, "target_length_km", None)   # ← NEW
    plan.activity_type      = intent.activity_type
    plan.duration_days      = intent.duration_days
    plan.difficulty         = intent.difficulty_hint or plan.difficulty
    # Persisted (not left in phase_data, which is wiped on every phase
    # transition) so it survives to save time for trail_data / Go Again.
    plan.required_tags      = list(getattr(intent, "required_tags", None) or [])
    plan.preferred_tags     = list(getattr(intent, "preferred_tags", None) or [])
    plan.priority_tags      = list(getattr(intent, "priority_tags", None) or [])

def _resolve_groq_params(session: TripSession) -> dict:
    """
    Returns per-phase Groq parameters with session-aware overrides.
    All other phases return PHASE_GROQ_PARAMS unchanged.

    Gear review: all gaps are now presented in one response, so max_tokens
    is scaled with gap count to prevent mid-list truncation on larger kits.

    Formula: max(base, 180 + n * 40), capped at 650.
      0–4 gaps  →  350  (base, unchanged)
      8 gaps    →  500
      12 gaps   →  650  (cap)

    The cap is conservative: the GEAR GAPS block lives in the system prompt,
    so Groq's job is friendly prose framing + one question, not a re-listing.
    """
    params = dict(PHASE_GROQ_PARAMS.get(session.phase, {}))

    if session.phase == "gear_review":
        # Scale with gap count to prevent mid-list truncation.
        n = len(session.plan.gear_gaps)
        params["max_tokens"] = min(650, max(350, 180 + n * 40))

    elif session.phase == "destination":
        if session.plan.hike_id:
            # Sub-state 3: confirming selection.
            # One warm sentence + transition note — no list, no reasoning.
            params["max_tokens"] = 200
        elif session.phase_data.get("hikes_presented"):
            # Sub-state 2: curating 5 → top 3 + full list.
            # Needs room for reasoning, three callouts, and the full table.
            params["max_tokens"] = 350
        else:
            # Sub-state 1: gathering destination info.
            # Just asking questions — keep it tight.
            params["max_tokens"] = 275

    return params


# ── Bug 1 helpers: trail-system name guard ────────────────────────────────────

def _is_trail_system_name(text: Optional[str]) -> bool:
    """
    Returns True if text names a long-distance US trail system (e.g.
    "Appalachian Trail") rather than a geographic region.  Used to detect
    when TripInputParser has geocoded a state/region to a nearby trail system.
    """
    return bool(text and _TRAIL_SYSTEM_RE.search(text))


def _resolve_destination_display(intent: TripIntent) -> Optional[str]:
    """
    Returns a display-safe destination name when destination_full looks like a
    trail-system name.  Falls back to destination_raw when that field exists
    and doesn't also look like a trail system.  Returns None when
    destination_full looks correct and no override is needed.

    This is a heuristic band-aid; the root fix belongs in TripInputParser's
    geocoding logic.  The log.warning lines make the mismatch visible so the
    parser bug can be tracked down independently.
    """
    if not _is_trail_system_name(intent.destination_full):
        return None
    raw = getattr(intent, "destination_raw", None)
    if raw and not _is_trail_system_name(raw):
        logger.warning(
            "Parser returned trail-system name %r as destination_full; "
            "overriding with destination_raw %r. "
            "Fix root cause in TripInputParser geocoding.",
            intent.destination_full, raw,
        )
        return raw.title()
    # destination_raw is also a trail name or missing — no safe override.
    logger.warning(
        "Parser returned trail-system name %r as destination_full and "
        "destination_raw=%r offers no safe alternative. Keeping as-is.",
        intent.destination_full, raw,
    )
    return None


# ── Bug 2 helper: phantom day filter ─────────────────────────────────────────

def _drop_phantom_days(days: list) -> list:
    """
    Remove filler DayPlan entries where both distance_miles and
    elevation_gain_ft are zero or absent.

    Groq occasionally appends a placeholder day for single-day trips
    ("Day 2: No hiking planned — 0 mi, 0 ft gain").  ItineraryParser
    serialises these faithfully, which makes them show up in the finalize
    summary as phantom entries.  Dropping them here keeps the itinerary
    clean without touching ItineraryParser.
    """
    return [
        d for d in days
        if (d.distance_miles or 0) > 0 or (d.elevation_gain_ft or 0) > 0
    ]


def _detect_destination_change(message: str, phase: str) -> bool:
    """
    Returns True if the user message almost certainly signals a desire to
    change destination.

    Only fires when phase != "destination" — there's nothing to reset if
    we're still gathering the original destination.

    Kept intentionally conservative (high precision, lower recall).
    Groq's own DESTINATION RESET emission covers the ambiguous cases this
    detector misses.
    """
    if phase == "destination":
        return False
    msg = message.lower()
    return any(phrase in msg for phrase in _DESTINATION_CHANGE_PHRASES)

# ── Cause 1 fix: no-location pre-parse check ─────────────────────────────────
#
# A message with feature/activity words ("summit", "lake", "ridge") but no
# location signal can't succeed in TripInputParser.parse() — there's nothing
# to geocode against. Short-circuiting here avoids burning a full parse cycle
# (regex miss → Groq extraction call → failed geocode → second Groq call →
# raised ValueError) on a request that can't succeed regardless.
#
# Feature detection reuses TripInputParser.ALL_FEATURE_KEYWORDS directly
# rather than a hand-maintained copy, so it grows automatically every time a
# new feature/keyword pair is added there. Location detection is fully
# delegated to _parser.has_location_signal(), which is built from
# TripInputParser's own STATE_KEYWORDS (all 50 states), REGION_KEYWORDS, and
# parks_lookup.json — neither list needs touching as the hikes table expands
# past NC/RI.
_NO_LOCATION_ACTIVITY_KEYWORDS: frozenset[str] = frozenset({
    "easy", "moderate", "hard", "challenging", "short", "hike",
})
_NO_LOCATION_FEATURE_KEYWORDS: frozenset[str] = (
    ALL_FEATURE_KEYWORDS | _NO_LOCATION_ACTIVITY_KEYWORDS
)

def _has_no_destination(message: str) -> bool:
    """
    True when the message mentions a feature/activity/difficulty word but
    has zero location signal — the case where TripInputParser.parse() has
    nothing to geocode and will fail regardless of how it's parsed.
    """
    text = message.lower()
    has_feature = any(kw in text for kw in _NO_LOCATION_FEATURE_KEYWORDS)
    return has_feature and not _parser.has_location_signal(message)
def _handle_phase_entry(session: TripSession) -> None:
    """
    Called exactly once when the session advances to a new phase.
    gear_review: gaps are already in plan.gear_gaps (promoted at selection);
    on_enter_gear_review just sets the gaps_presented flag.
    """
    logger.info("Session %s: entering phase=%s", session.session_id, session.phase)

    if session.phase == "gear_review":
        _controller.on_enter_gear_review(session, session.plan.gear_gaps)
    elif session.phase == "itinerary":
        _controller.on_enter_itinerary(session)
    elif session.phase == "finalize":
        _controller.on_enter_finalize(session)


def _reset_destination(session: TripSession) -> None:
    session.phase      = "destination"
    session.phase_data = {}
    session.summary    = ""
    session.clear_window()
    plan                    = session.plan
    plan.destination_full   = None
    plan.hike_name          = None
    plan.hike_id            = None
    plan.lat                = None
    plan.lng                = None
    plan.state              = None
    plan.max_length_km      = None      # ← NEW
    plan.target_length_km   = None      # ← NEW
    plan.activity_type      = None
    plan.duration_days      = None
    plan.difficulty         = None
    plan.required_tags      = []
    plan.preferred_tags     = []
    plan.priority_tags      = []
    plan.gear_gaps          = []
    plan.gear_finalized     = False
    plan.days               = []
    plan.itinerary_approved = False
    logger.info("Session %s destination reset.", session.session_id)


def _gap_to_dict(gap: GearGap) -> dict:
    """Serialise a GearGap to a plain dict for Redis storage in phase_data."""
    return {
        "category":   gap.category,
        "issue":      gap.issue,
        "detail":     gap.detail,
        "suggestion": getattr(gap, "suggestion", None),
    }


def _dict_to_gap(d: dict) -> GearGap:
    """Reconstruct a GearGap from a plain dict retrieved from phase_data."""
    return GearGap(
        category   = d["category"],
        issue      = d["issue"],
        detail     = d["detail"],
        suggestion = d.get("suggestion"),
    )


async def _async_summarize(session: TripSession) -> None:
    try:
        new_summary = _summarizer.summarize(
            messages     = session.get_window_messages(),
            prev_summary = session.summary,
        )
        session.update_summary(new_summary)
        _store.save(session)
        logger.info(
            "Summarized session %s (%d words).",
            session.session_id,
            len(new_summary.split()),
        )
    except Exception as e:
        logger.error("Async summarize failed for %s: %s", session.session_id, e)


# ── Health ────────────────────────────────────────────────────────────────────
def _structural_prerequisites_met(session: TripSession, itinerary_prebuilt: bool) -> bool:
    """
    Called by the ADVANCE_PHASE handler to verify Groq's intent signal is
    safe to honor.  Each phase has exactly one data-integrity gate:

      destination  — hike selected AND options were presented
                     (covers the case where hike_id gets set mid-turn)
      gear_review  — hike is confirmed (gaps may be empty; that's fine)
      itinerary    — at least one DayPlan parsed by ItineraryParser
      finalize     — always structural, handled by save endpoint directly
     itinerary_prebuilt: whether plan.days was non-empty at the START of this
    turn (before ItineraryParser ran). Prevents ADVANCE_PHASE from firing on
    the same turn Groq first generates the itinerary — the user hasn't seen
    it yet and can't have approved it.
    """
    phase = session.phase
    if phase == "destination":
        return (
            session.plan.hike_id is not None
            and session.phase_data.get("hikes_presented", False)
        )
    if phase == "gear_review":
        return session.plan.hike_id is not None
    if phase == "itinerary":
        # plan.days must exist AND must have existed before this turn started.
        # Without the second guard, the parser populates days and ADVANCE_PHASE
        # fires in the same response, skipping itinerary review entirely.
        return bool(session.plan.days) and itinerary_prebuilt
    return False


# ── Health ────────────────────────────────────────────────────────────────────
@router.get("/health")
def health():
    return {"redis": _store.ping(), "status": "ok"}