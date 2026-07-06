"""
PhaseController.py

The state machine. This is the only place phase transitions happen.
Groq never decides when to advance — this code does, based on hard signals.

Transition logic per phase:

  destination  → gear_review  : TripIntent parsed AND hike options presented
                                 AND user has selected a specific hike
                                 (plan.hike_id is set by trip_chat.py after calling
                                  extract_hike_selection())

  gear_review  → itinerary    : user explicitly finalizes gear ("looks good", "ready", etc.)
  itinerary    → finalize     : user explicitly approves itinerary
  finalize     → (done)       : trip saved to DB (handled by trip_chat.py)

The destination phase has two internal sub-steps that do NOT change session.phase:
  sub-step 1 — TripIntent parsed, HikeSearchService results injected into Groq prompt.
               Caller marks this with on_hikes_presented().
  sub-step 2 — User picks one of the presented options.
               Caller extracts the selection with extract_hike_selection(), sets
               plan.hike_id, then calls evaluate() — which now advances the phase.

Each check is a combination of:
  - Structured signals (intent parsed, plan fields set)
  - Light keyword detection on the user's last message (no LLM needed)
"""

import re
import logging
from typing import Optional

from .TripSession import TripSession
from .TripPlan    import TripPlan
from .TripInputParser    import TripIntent

logger = logging.getLogger(__name__)


# ── Confirmation keywords ─────────────────────────────────────────────────────
#
# Deliberately conservative — we only advance on clear positive signals.
# Ambiguous messages ("ok", "sure") do NOT advance phase.

GEAR_DONE_SIGNALS = [
    # existing patterns
    r"\bgear.*(good|ready|fine|set|done|finalized|looks good|sorted)\b",
    r"\b(happy|satisfied) with.*(gear|kit|pack)\b",
    r"\bready (to|for).*(itinerary|plan|next|continue)\b",
    r"\b(move on|next step|let'?s go|continue)\b",
    r"\bfinalize.*(gear|kit)\b",
    r"\bthat'?s everything\b",
    r"\bthat (covers|does) it\b",
    # new — natural "skip/accept gaps" phrasings
    r"\bproceed\b",                                              # "proceed as is", "let's proceed"
    r"\bskip\b",                                                 # "skip", "skip this"
    r"\bas.is\b",                                                # "as is", "as-is"
    r"\b(no|don'?t).{0,10}(change|fix|buy|get|address)\b",      # "no need to buy", "don't need to address"
    r"\b(looks? good|all good|good to go|sounds? good)\b",       # "looks good" — also natural here
    r"\b(i'?m|we'?re|i am).{0,15}(ready|set|good)\b",           # "i'm ready", "we're good"
    r"\bignore.{0,30}(gear|gaps?|kit|items?|rest|other|those)\b",  # "ignore the other gear"
    r"\b(don'?t|not).{0,15}(worry|care|worried|concerned)\b",       # "don't worry about it"
    r"\b(fine|okay?|ok).{0,15}with.{0,20}(gaps?|gear|missing|that)\b",       # "ok with that", "fine with the gaps"
]

ITINERARY_DONE_SIGNALS = [
    r"\b(looks good|that'?s good|perfect|love it|approve|approved)\b",
    r"\b(save|ready to save|go ahead and save)\b",
    r"\bitinerary.*(good|approved|done|finalized|ready)\b",
    r"\b(that'?s the plan|let'?s do it|let'?s go with that)\b",
]

DESTINATION_RESET_SIGNALS = [
    r"\bdestination reset\b",
    r"\bchange.*(destination|location|hike|trail|place)\b",
    r"\bactually.*(want|thinking|prefer).*(go to|hike|visit)\b",
    r"\bforget.*(that|it).*(let'?s|i want)\b",
    r"\bstart over\b",
    r"\bdifferent (trail|hike|destination|place)\b",
    r"\bcan (i|we) (go back to|go to|return to)\b",
    r"\b(go|get) back to (the )?(destination|destinations|hike selection|hikes)\b",
    r"\bback to (the )?(destination|destinations|hike selection|hikes)\b",
    r"\b(try|go|head)(?!\s+with\s+\d).{0,25}\binstead\b",
]

# Patterns that indicate the user is selecting one of the numbered hike options.
HIKE_SELECTION_SIGNALS = [
    r"\b(option|trail|hike|choice|number|#)\s*[1-5]\b",
    r"\b(first|second|third|fourth|fifth)\s*(one|option|trail|hike)?\b",
    r"\b(go with|let'?s (do|take)|i'?ll (take|do)|i (want|pick|choose))\b.{0,20}\b[1-5]\b",
    r"\b[1-5]\s*(sounds|looks|seems)\s*(good|great|perfect|nice)\b",
    r"^[1-5][.!?\s]*$",   # bare digit (entire message is just the number)
    r"\b(?:can (?:i|we)|let'?s) (?:look at|check out|see|try)\b.{0,15}\b[1-5]\b",
    r"\b(?:what|how) about\b.{0,15}\b[1-5]\b",
    r"\bshow me\b.{0,15}\b[1-5]\b",
]

# Maps English ordinals → their 1-based position.
_ORDINAL_MAP: dict[str, int] = {
    "first":  1,
    "second": 2,
    "third":  3,
    "fourth": 4,
    "fifth":  5,
}


class PhaseController:
    """
    Usage in trip_chat.py:

        controller = PhaseController()

        # --- after TripInputParser returns a TripIntent ---
        if intent and not session.phase_data.get("hikes_presented"):
            scored = hike_search_service.find_hikes_for_intent(intent)
            controller.on_hikes_presented(session, scored)
            # inject hike_search_service.format_for_context(scored) into Groq prompt

        # --- after Groq responds ---
        # try to resolve hike selection before evaluating transitions
        if (
            session.phase == "destination"
            and session.phase_data.get("hikes_presented")
            and session.plan.hike_id is None
        ):
            idx = PhaseController.extract_hike_selection(
                user_message,
                count=len(session.phase_data.get("hike_options", [])),
            )
            if idx is not None:
                session.plan.hike_id = session.phase_data["hike_options"][idx]

        advanced, reset = controller.evaluate(
            session      = session,
            user_message = message,
            intent       = parsed_intent,   # may be None on selection turn
            ai_response  = groq_response,
        )

        if reset:
            # wipe plan destination fields, stay in destination phase
            ...
        elif advanced:
            # session.phase has already been updated
            # run any on-entry logic for the new phase
            ...
    """

    def evaluate(
        self,
        session:      TripSession,
        user_message: str,
        intent:       Optional[TripIntent],
        ai_response:  str = "",
    ) -> tuple[bool, bool]:
        """
        Evaluate whether a phase transition or reset should happen.

        Returns:
            (advanced: bool, reset: bool)
            advanced = True if phase was advanced (session.phase already updated)
            reset    = True if destination was reset (caller must clear plan fields)

        Note: advanced and reset are mutually exclusive.
        """
        # ── Destination reset (highest priority, any phase) ────────────────
        if self._wants_reset(user_message, ai_response):
            logger.info(
                "PhaseController: destination reset in phase=%s", session.phase
            )
            session.phase      = "destination"
            session.phase_data = {}
            return False, True

        phase = session.phase

        # ── destination → gear_review ──────────────────────────────────────
        if phase == "destination":
            if self._destination_confirmed(session):
                logger.info("PhaseController: advancing destination → gear_review")
                session.advance_phase()
                return True, False

        # ── gear_review → itinerary ────────────────────────────────────────
        elif phase == "gear_review":
            if self._gear_finalized(user_message, session):
                logger.info("PhaseController: advancing gear_review → itinerary")
                session.plan.gear_finalized = True
                session.advance_phase()
                return True, False

        # ── itinerary → finalize ───────────────────────────────────────────
        elif phase == "itinerary":
            if self._itinerary_approved(user_message, session):
                logger.info("PhaseController: advancing itinerary → finalize")
                session.plan.itinerary_approved = True
                session.advance_phase()
                return True, False

        # finalize phase is terminal — trip_chat.py handles the save action
        return False, False

    # ── Phase-specific checks ─────────────────────────────────────────────────

    def _destination_confirmed(self, session: TripSession) -> bool:
        """
        Advance from destination phase when ALL of the following are true:
          1. plan has lat/lng/destination_full/duration_days (populated from TripIntent)
          2. Hike options have been presented to the user (on_hikes_presented was called)
          3. The user has selected a specific hike (plan.hike_id is set)

        The `intent` parameter from evaluate() is intentionally NOT used here —
        on the selection turn the user says "option 2", not a new destination
        description, so intent will be None. plan fields are the source of truth.
        """
        plan = session.plan
        if not (
            plan.destination_full
            and plan.duration_days
            and plan.lat is not None
            and plan.lng is not None
        ):
            return False

        if not session.phase_data.get("hikes_presented"):
            return False

        return plan.hike_id is not None

    def _gear_finalized(self, user_message: str, session: TripSession) -> bool:
        """
        Advance from gear_review when user sends a clear finalization signal.
        Requires that gear gap analysis has already run (gaps presented or empty).
        """
        if session.plan.hike_id is None:
            return False
        return self._matches_any(user_message, GEAR_DONE_SIGNALS)

    def _itinerary_approved(self, user_message: str, session: TripSession) -> bool:
        """
        Advance from itinerary when user approves.
        Requires at least one day to have been parsed — this ensures the
        itinerary parser has successfully run before the trip can be saved.
        """
        if not session.plan.days:
            return False
        return self._matches_any(user_message, ITINERARY_DONE_SIGNALS)

    def _wants_reset(self, user_message: str, ai_response: str) -> bool:
        """
        Check both the user message and the AI's response for reset signals.
        Groq is prompted to emit 'DESTINATION RESET' explicitly when detected.
        trip_chat.py also runs a Python phrase-detector before calling evaluate(),
        but this check remains as a fallback for ambiguous phrasing Groq catches
        that the phrase detector misses.
        """
        return (
            self._matches_any(user_message, DESTINATION_RESET_SIGNALS)
            or "DESTINATION RESET" in ai_response
        )

    # ── Hike selection ────────────────────────────────────────────────────────

    @staticmethod
    def extract_hike_selection(text: str, count: int) -> Optional[int]:
        """
        Parse the user's message for a numbered hike selection.

        Returns the 0-based index into the hike_options list, or None if
        no clear selection was found or the number is out of range.

        `count` should be the number of options that were presented
        (len(session.phase_data["hike_options"])).
        """
        if count <= 0:
            return None

        text_lower = text.lower().strip()

        # 1. Ordinal words: "first", "second", etc.
        for word, one_based in _ORDINAL_MAP.items():
            if re.search(rf"\b{word}\b", text_lower) and one_based <= count:
                return one_based - 1

        # 2. Explicit label + digit: "option 2", "trail 3", "#1", "number 4"
        label_match = re.search(
            r"\b(?:option|trail|hike|choice|number|#)\s*([1-5])\b",
            text_lower,
        )
        if label_match:
            n = int(label_match.group(1))
            if 1 <= n <= count:
                return n - 1

        # 3. Digit following a selection verb: "go with 2", "let's do 3",
        #    "i'll take 1", "i want 4"
        verb_match = re.search(
            r"\b(?:go with|let'?s (?:do|take)|i'?ll (?:take|do)|i (?:want|pick|choose)"
            r"|(?:can (?:i|we)|let'?s|i(?:'d| would)(?: like)?)"
            r" (?:look at|see|check(?: out)?|try|do|go with|pick|choose)"
            r"|(?:what|how) about"
            r"|show me)\b"
            r".{0,20}\b([1-5])\b",
            text_lower,
        )
        if verb_match:
            n = int(verb_match.group(1))
            if 1 <= n <= count:
                return n - 1

        # 4. Bare digit as the entire message: "2" / "2!" / "3."
        bare_match = re.fullmatch(r"\s*([1-5])[.!?\s]*", text_lower)
        if bare_match:
            n = int(bare_match.group(1))
            if 1 <= n <= count:
                return n - 1

        return None

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        text_lower = text.lower().strip()
        return any(re.search(p, text_lower) for p in patterns)

    # ── On-entry actions ──────────────────────────────────────────────────────
    #
    # Called by trip_chat.py right after a phase advance (or sub-step change),
    # to set up phase-specific state before the next prompt is built.

    def on_hikes_presented(
        self,
        session: TripSession,
        scored:  list,          # List[Tuple[Hike, int]] from HikeSearchService
    ) -> None:
        """
        Mark that hike options have been shown to the user.
        Stores the ordered list of hike UUIDs and names so that:
          - extract_hike_selection() can resolve "option 2" → the correct UUID
          - trip_chat.py can look up hike_names[idx] when promoting the selection
        """
        session.phase_data["hikes_presented"] = True
        session.phase_data["hike_options"]    = [str(hike.id) for hike, _ in scored]
        session.phase_data["hike_names"]      = [hike.name   for hike, _ in scored]
        logger.info(
            "PhaseController: %d hike options presented for session %s",
            len(scored),
            getattr(session, "session_id", "?"),
        )

    def on_enter_gear_review(self, session: TripSession, gaps: list) -> None:
        """
        Store gear gaps on the plan and mark that they've been presented.
        Note: plan.gear_gaps is already populated by trip_chat._promote_hike_gaps()
        at hike-selection time — the first line is a no-op in normal flow, but
        the gaps_presented flag is essential: _gear_finalized() gates on it.
        """
        session.plan.gear_gaps               = gaps
        session.phase_data["gaps_presented"] = True

    def on_enter_itinerary(self, session: TripSession) -> None:
        """Clear any stale day plans if re-entering itinerary phase."""
        session.plan.days                       = []
        session.phase_data["itinerary_started"] = True

    def on_enter_finalize(self, session: TripSession) -> None:
        session.phase_data["ready_to_save"] = True