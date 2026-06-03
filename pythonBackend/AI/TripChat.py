"""
trip_chat.py

Single POST endpoint: /api/trip/chat
Save endpoint:        POST /api/trip/save

Orchestrates the full request lifecycle:
  1. Load or create session
  2. Parse user input for trip intent
  3. Populate plan from intent if destination phase
  4. Run gear gap analysis on phase entry
  5. Check for phase transition / destination reset
  6. Build system prompt
  7. Call Grok
  8. Store turn + async summarize if needed
  9. Save session to Redis
  10. Return response + metadata to frontend
"""

import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from requests import session

from Auth.authentication          import get_current_user_id
from Repos.TripRepo               import TripRepository
from Services.TripService         import TripService
from AI.TripInputParser           import TripInputParser, TripIntent
from AI.GearGapAnalyzer           import GearGapAnalyzer
from AI.PromptBuilder             import build_system_prompt
from AI.Summarizer                import Summarizer
from AI.PhaseController           import PhaseController
from AI.GroqClient                import GroqClient
from models.TripSession           import TripSession
from services.SessionStore        import SessionStore
from Repos.ItemRepo               import ItemRepository   # adjust to your actual import
from Services.HikeSearchService import HikeSearchService
from Services.HikeService       import HikeService
from Repos.HikeRepo             import HikeRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trip", tags=["trip"])

# ── Singletons ────────────────────────────────────────────────────────────────

_store      = SessionStore()
_parser     = TripInputParser()
_analyzer   = GearGapAnalyzer()
_summarizer = Summarizer()
_controller = PhaseController()
_grok       = GroqClient()
_hike_search = HikeSearchService(HikeService(HikeRepository()))



def get_service() -> TripService:
    return TripService(TripRepository())

def get_item_repo() -> ItemRepository:
    return ItemRepository()


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str
    session_id: Optional[str] = None    # None = start fresh


class ChatResponse(BaseModel):
    session_id: str
    response:   str
    phase:      str
    plan:       dict
    advanced:   bool
    created:    bool


class SaveResponse(BaseModel):
    trip_id:    str
    title:      str
    stops:      list[dict]
    gear:       list[dict]


# ── Gear loader ───────────────────────────────────────────────────────────────

def _load_user_gear(user_id: str, item_repo: ItemRepository) -> list[dict]:
    """
    Fetches the user's owned gear items from the DB and returns them as
    plain dicts for the AI layer.

    Expects ItemRepository.list_by_user() to return objects with at minimum:
        id, name, category, weight (grams), cost
    Adjust field names below to match your actual Item model.
    """
    items = item_repo.list_by_user(UUID(user_id))
    return [
        {
            "id":       str(item.id),
            "name":     item.name,
            "category": item.category,   # must match CATEGORY_RULES keys in GearGapAnalyzer
            "weight":   item.weight,     # grams
            "cost":     item.cost,
            # Optional — used by sleeping bag temp check:
            "temp_rating_f": getattr(item, "temp_rating_f", None),
        }
        for item in items
    ]


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def trip_chat(
    req:             ChatRequest,
    current_user_id: str          = Depends(get_current_user_id),
    item_repo:       ItemRepository = Depends(get_item_repo),
):
    # ── 1. Load or create session ──────────────────────────────────────────
    session, created = _store.get_or_create(
        session_id = req.session_id,
        user_id    = current_user_id,
    )

    # ── 2. Fetch user gear from DB ─────────────────────────────────────────
    try:
        user_gear = _load_user_gear(current_user_id, item_repo)
    except Exception as e:
        logger.error("Failed to fetch gear for user %s: %s", current_user_id, e)
        raise HTTPException(500, "Could not load gear data.")

    # ── 3. Parse trip intent (destination phase only) ──────────────────────
    intent: Optional[TripIntent] = None
    if session.phase == "destination":
        try:
            intent = _parser.parse(req.message)
            _apply_intent_to_plan(session, intent)
            hike_context: str = ""
            if (
                intent is not None
                and not session.phase_data.get("hikes_presented")
            ):
                try:
                    scored = _hike_search.find_hikes_for_intent(intent)
                    _controller.on_hikes_presented(session, scored)
                    hike_context = _hike_search.format_for_context(scored)
                except Exception as e:
                    logger.warning("HikeSearchService failed: %s", e)
        except ValueError as e:
            logger.info("Parser couldn't resolve destination: %s", e)
        except Exception as e:
            logger.warning("Parser error: %s", e)
        
    # ── 4. Gear gap analysis — once on entry to gear_review ───────────────
    if (
        session.phase == "gear_review"
        and not session.phase_data.get("gaps_presented")
        and session.plan.is_destination_set()
    ):
        gaps = _analyzer.analyze(
            owned_items     = user_gear,
            activity_type   = session.plan.activity_type or "day_hike",
            duration_days   = session.plan.duration_days or 1,
            difficulty      = session.plan.difficulty,
            overnight_low_f = session.phase_data.get("overnight_low_f"),
        )
        _controller.on_enter_gear_review(session, gaps)
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
            session.plan.hike_id = session.phase_data["hike_options"][idx]
    # ── 5. Phase transition check (pre-response) ───────────────────────────
    advanced, reset = _controller.evaluate(
        session      = session,
        user_message = req.message,
        intent       = intent,
        ai_response  = "",
    )

    if reset:
        _reset_destination(session)
        advanced = False

    if advanced:
        _handle_phase_entry(session)

    # ── 6. Build system prompt ─────────────────────────────────────────────
    system_prompt = build_system_prompt(session, user_gear, hike_context=hike_context)
    # ── 7. Call Grok ───────────────────────────────────────────────────────
    try:
        ai_response, _ = _grok.chat(
            system_prompt   = system_prompt,
            summary         = session.summary,
            window_messages = session.get_window_messages(),
            user_message    = req.message,
        )
    except Exception as e:
        logger.error("Grok API error: %s", e)
        raise HTTPException(502, "AI service unavailable. Please try again.")

    # ── 7b. Post-response check — catches Grok emitting DESTINATION RESET ──
    _, post_reset = _controller.evaluate(
        session      = session,
        user_message = req.message,
        intent       = intent,
        ai_response  = ai_response,
    )
    if post_reset and not reset:
        _reset_destination(session)

    # ── 8. Append turn + async summarize if threshold crossed ─────────────
    session.add_turn(req.message, ai_response)

    if session.needs_summarization():
        asyncio.create_task(_async_summarize(session))

    # ── 9. Persist session to Redis ────────────────────────────────────────
    saved = _store.save(session)
    if not saved:
        logger.error("Redis save failed for session %s", session.session_id)

    # ── 10. Respond ────────────────────────────────────────────────────────
    return ChatResponse(
        session_id = session.session_id,
        response   = ai_response,
        phase      = session.phase,
        plan       = session.plan.to_dict(),
        advanced   = advanced,
        created    = created,
    )


# ── Save endpoint ─────────────────────────────────────────────────────────────

@router.post("/save", response_model=SaveResponse)
def save_trip(
    session_id:      str,
    current_user_id: str         = Depends(get_current_user_id),
    service:         TripService = Depends(get_service),
):
    """
    Converts the completed AI session into persisted DB rows and cleans
    up the Redis session.

    Called by the frontend when the user confirms save in the finalize phase.
    session_id is passed as a query param: POST /api/trip/save?session_id=...
    """
    session = _store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired.")

    # Safety check — only the session owner can save
    if session.user_id != current_user_id:
        raise HTTPException(403, "Forbidden.")

    if session.phase != "finalize":
        raise HTTPException(400, "Trip is not ready to save yet.")

    if not session.plan.is_destination_set():
        raise HTTPException(400, "Trip destination is incomplete.")

    try:
        trip = service.save_from_session(
            user_id = UUID(current_user_id),
            session = session,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("save_from_session failed: %s", e)
        raise HTTPException(500, "Failed to save trip.")

    # Clean up Redis — trip is now in the DB
    _store.delete(session_id)

    return SaveResponse(
        trip_id = str(trip.id),
        title   = trip.title,
        stops   = [s.to_dict() for s in trip.stops],
        gear    = [g.to_dict() for g in trip.gear],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_intent_to_plan(session: TripSession, intent: TripIntent) -> None:
    plan                  = session.plan
    plan.destination_full = intent.destination_full
    plan.lat              = intent.lat
    plan.lng              = intent.lng
    plan.activity_type    = intent.activity_type
    plan.duration_days    = intent.duration_days
    plan.difficulty       = intent.difficulty_hint


def _reset_destination(session: TripSession) -> None:
    session.phase      = "destination"
    session.phase_data = {}
    plan               = session.plan
    plan.destination_full   = None
    plan.hike_name          = None
    plan.hike_id            = None
    plan.lat                = None
    plan.lng                = None
    plan.activity_type      = None
    plan.duration_days      = None
    plan.difficulty         = None
    plan.gear_gaps          = []
    plan.gear_finalized     = False
    plan.days               = []
    plan.itinerary_approved = False
    logger.info("Session %s destination reset.", session.session_id)


def _handle_phase_entry(session: TripSession) -> None:
    if session.phase == "itinerary":
        _controller.on_enter_itinerary(session)
    elif session.phase == "finalize":
        _controller.on_enter_finalize(session)


async def _async_summarize(session: TripSession) -> None:
    try:
        new_summary = _summarizer.summarize(
            messages     = session.get_window_messages(),
            prev_summary = session.summary,
        )
        session.update_summary(new_summary)
        _store.save(session)
        logger.info("Summarized session %s (%d words).", session.session_id, len(new_summary.split()))
    except Exception as e:
        logger.error("Async summarize failed for %s: %s", session.session_id, e)


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"redis": _store.ping(), "status": "ok"}