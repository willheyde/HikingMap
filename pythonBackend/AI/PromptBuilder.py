"""
PromptBuilder.py

Pure function module — takes a TripSession + user gear list and returns
a fully assembled system prompt string ready for Groq.

Nothing stateful here.  Keeping prompt logic isolated makes it easy to
iterate on wording without touching business logic.

Key design decisions
--------------------
Destination phase
    Three internal sub-states handled by _destination_phase_block():

      1. Gathering info       — no intent parsed yet, no hikes found
      2. Presenting options   — hikes in context, waiting for a numbered pick
      3. Confirming selection — hike_id set, wrapping up the phase

Gear review phase
    Gear gaps are computed per-hike in the destination phase and embedded
    alongside trail options.  By gear_review entry, the selected hike's
    gaps are in plan.gear_gaps and appear in the GEAR GAPS block.
    Groq's job is discussion + sign-off, not discovery.
    The GEAR GAPS block is only injected in the gear_review phase — it is
    intentionally withheld from the itinerary and finalize phases to avoid
    polluting those prompts with resolved concerns.

Itinerary phase
    Two internal sub-states handled by _itinerary_phase_block():

      1. Building / revising  — plan.days empty.  Groq writes the itinerary
                                in the exact per-day format the parser needs.
      2. Awaiting approval    — plan.days populated.  Groq reviews with the
                                user and emits "Itinerary confirmed — ready
                                to save." when they approve.

Finalize phase
    Two internal sub-states handled by _finalize_phase_block():

      1. Presenting summary   — Groq presents a structured recap of the full
                                trip and asks "Shall I save this trip?"
                                Sets phase_data["save_summary_shown"] = True.
      2. Awaiting save        — user has said yes.  Groq emits the exact
                                string "SAVE CONFIRMED" as the first token.
                                trip_chat.py scans for it and sets
                                save_confirmed=True on ChatResponse so the
                                frontend can trigger POST /api/trip/save.

DESTINATION RESET signal
    "DESTINATION RESET" must appear as the very first token of Groq's
    response when the user changes destination.  Its rule fragment (and the
    other signal fragments) is phase-scoped by _rules(phase) — see the comment
    above _RULES_BY_PHASE.  trip_chat.py also runs a Python-level phrase
    detector as a pre-response fallback.
Groq parameters
    chat() accepts max_tokens / temperature overrides.  trip_chat.py passes
    per-phase values from PHASE_GROQ_PARAMS so callers don't need to know
    prompt internals.
"""

from .TripSession import TripSession
from .TripPlan    import GearGap
from trip_metrics import km_to_miles, m_to_feet


# ── Per-phase Groq call parameters ────────────────────────────────────────────
#
# Imported and used by trip_chat.py when calling _groq.chat().
#
# destination  500 / 0.4  — sub-state 2 (presenting 5 options with gear notes
#                           and natural prose) routinely needs 400–480 tokens.
#                           Low temp keeps hike presentation factual.
# gear_review  350 / 0.4  — one or two gaps per turn; short by design.
#                           Low temp keeps safety advice consistent.
# itinerary   1400 / 0.65 — a 4-day itinerary in the required format is
#                           ~600–900 tokens; 1400 gives headroom for longer
#                           trips.  Slightly higher temp for natural prose
#                           without inventing stats.
# finalize     450 / 0.4  — a 4-day trip summary plus the ask fits at ~300
#                           tokens; 450 handles a 5-day trip cleanly.
#                           Low temp for a consistent, accurate summary.

PHASE_GROQ_PARAMS: dict[str, dict] = {
    "destination": {"max_tokens": 500,  "temperature": 0.4},
    "gear_review": {"max_tokens": 350,  "temperature": 0.4},
    "itinerary":   {"max_tokens": 1400, "temperature": 0.65},
    "finalize":    {"max_tokens": 450,  "temperature": 0.4},
}


# ── Phase configs — destination, itinerary, and finalize handled separately ───
PHASE_CONFIGS = {
    "gear_review": {
        "goal": (
            "IMPORTANT — check the user's intent before discussing gear:\n"
            "If the user is asking for a DIFFERENT TYPE OF HIKE (different difficulty, "
            "wants a water feature, shorter/longer route, etc.) rather than discussing gear, "
            "emit 'SEARCH_REFINE' as the very first word of your response and briefly "
            "acknowledge the new criteria. Do NOT discuss gear gaps in that case.\n\n"
            "Otherwise (the user IS discussing gear): "
            "The user's gear has already been cross-referenced against their selected trail "
            "and the GEAR GAPS section below lists anything missing or worth flagging. "
            "Present ALL gaps in a single response: missing items first, then marginal ones. "
            "After listing everything, ask which (if any) the user plans to address before "
            "the trip — or whether they're happy to proceed as-is. "
            "When the user confirms they'll address a SPECIFIC gap from the GEAR GAPS list "
            "(e.g. 'soft flasks works for me' for the hydration gap), tell them you've added "
            "it to their kit and append GEAR ADD: <category> on its own line at the end of "
            "your response, using the category name shown in brackets in the GEAR GAPS list. "
            "Only do this for gaps the user has just confirmed — never speculatively, and "
            "never for a gap already resolved earlier in the conversation. "
            "Once the user confirms their kit is ready, tell them you're moving on to build the itinerary."
        ),
        "tone": "practical and direct",
    },
}


# ── Prompt assembly ───────────────────────────────────────────────────────────

def build_system_prompt(
    session:      TripSession,
    user_gear:    list[dict],
    hike_context: str = "",
    refine_note:  str = "",
) -> str:
    plan = session.plan

    sections = [_persona()]

    if session.phase == "destination":
        sections.append(_destination_phase_block(session))
    elif session.phase == "itinerary":
        sections.append(_itinerary_phase_block(plan))
    elif session.phase == "finalize":
        sections.append(_finalize_phase_block(session))
    else:
        sections.append(_phase_block(session.phase, PHASE_CONFIGS[session.phase]))

    # refine_note is intentionally NOT injected here anymore — see below.

    sections.append(_gear_block(user_gear))

    # Drop the HIKE OPTIONS block once a hike is chosen (destination sub-state 3
    # and beyond). The 5-trail block with per-hike stats + gear notes is the
    # single largest dynamic section (~400-600 tokens); once plan.hike_id is set
    # the choice is made, so it's dead weight on the selection-confirmation turn.
    if hike_context and session.phase == "destination" and not plan.hike_id:
        sections.append(_hike_context_block(hike_context))

    if plan.is_destination_set():
        sections.append(_trip_block(plan))

    if plan.gear_gaps and session.phase == "gear_review":
        sections.append(_gaps_block(plan.gear_gaps))

    if plan.days:
        sections.append(_itinerary_block(plan))

    if session.summary:
        sections.append(_summary_block(session.summary))

    sections.append(_rules(session.phase))

    # ── Injected AFTER _rules() so it takes precedence ────────────────────
    # The SEARCH_REFINE rule in _rules() is unconditional and emphatic; if
    # refine_note is placed before it, Groq reads the rules last and loops.
    # Placing it here makes "do NOT emit SEARCH_REFINE" the final instruction.
    if refine_note:
        sections.append(
            "CRITICAL — ACTIVE SEARCH RESULT (overrides SEARCH_REFINE rule above):\n"
            + refine_note
            + "\nA search has already executed this turn. "
            "Do NOT emit SEARCH_REFINE under any circumstances."
        )

    return "\n\n".join(s.strip() for s in sections if s.strip())


# ── Destination phase — sub-state aware ──────────────────────────────────────

def _destination_phase_block(session: TripSession) -> str:
    """
    Three destination sub-states detected from session state (priority order):
      hike_id set       → selection confirmed, wrap up
      hikes_presented   → options showing, waiting for numbered pick
      neither           → still gathering info
    """
    plan            = session.plan
    hikes_presented = session.phase_data.get("hikes_presented", False)

    if plan.hike_id:
        hike_label = f'"{plan.hike_name}"' if plan.hike_name else "the selected trail"
        goal = (
            f"The user has chosen {hike_label}. "
            "Confirm their selection in one warm sentence, briefly restate the trip "
            "(destination, duration, difficulty), then tell them you are checking their "
            "gear against this specific trail before moving on. "
            "Do not ask any questions in this response."
        )
        tone = "warm and decisive"

    elif hikes_presented:
        option_count = len(session.phase_data.get("hike_options", []))
        if option_count >= 3:
            picks_line = (
                "Then call out your top three picks BY NAME (never 'option 1' or a "
                "generic label) with one sentence each explaining why they fit this "
                "specific trip. Each sentence MUST cite something concrete and real "
                "about that trail from the HIKE OPTIONS data below — a specific tag, "
                "its length, its elevation gain, or a gear-readiness note. Never write "
                "a vague sentence that could describe any trail (e.g. 'a good option "
                "with a gentle gain and nice scenery') — if you can't name a real, "
                "specific reason for a pick, don't call it out as one of the three. "
            )
        else:
            picks_line = (
                f"There {'is' if option_count == 1 else 'are'} only {option_count} matching "
                f"hike{'s' if option_count != 1 else ''} available. Do not comment on the low "
                "count or apologize for it — talk about what's there naturally, as if this "
                "were the full result set (which it is). "
            )
        goal = (
            "Trail options with gear-readiness notes are in the HIKE OPTIONS block below. "
            "Reason briefly about what this user has told you — trip length, fitness level, "
            "anything they want to see, any constraints. "
            + picks_line +
            "Do NOT restate each trail's full stats line or its Tags list verbatim — "
            "the system displays the full set as selectable cards right below your "
            "response, so your job ends at the reasoning and the close-out question. "
            "You MAY and SHOULD use each trail's real name when you call out a pick. "
            "The user will choose by clicking one of those cards, not by typing a "
            "number — do NOT ask them to 'reply with a number.' Close with something "
            "like 'which one sounds good?' or 'pick whichever fits best.' "
            "Do NOT invent trails not in the HIKE OPTIONS block. "
            "Do NOT advance until the user makes a clear selection. "
            "If the user's message asks for different criteria instead of picking one "
            "(re-emphasizing a feature, asking you to guarantee one, a different "
            "difficulty, a shorter/longer route), do not answer from memory or comment "
            "on the current options' tags yourself — emit SEARCH_REFINE as the very "
            "first word of your response so the system re-runs the search and reports "
            "the real result, including an honest data-coverage note if the feature "
            "truly isn't in the area."
        )
        tone = "clear and consultative"
    elif session.phase_data.get("search_empty"):
        goal = (
            "A trail search ran but returned no results for this destination. "
            "CRITICAL — check the user's intent first:\n"
            "• If the user is asking for DIFFERENT TRAIL CRITERIA (easier difficulty, "
            "a specific feature, shorter route, etc.): emit 'SEARCH_REFINE' as your "
            "very first word, then briefly acknowledge the new criteria in one sentence. "
            "Do NOT mention the previous empty search — a new search will run automatically.\n"
            "• If the user wants to change destination entirely: emit 'DESTINATION RESET'.\n"
            "• Otherwise (user is acknowledging the empty result or asking what to do): "
            "explain no trails were found and ask if they'd like to try a different area, "
            "adjust difficulty, or change trip length. "
            "Do not say 'I will search' — the search already ran."
        )
        tone = "empathetic and helpful"
    else:
        goal = (
            "Help the user choose a hiking destination. "
            "Ask for anything still missing — where they want to go, how many days, "
            "and their preferred difficulty level. "
            "Do not invent trail names or describe specific routes. "
            "Trail options will appear in a HIKE OPTIONS block when the system finds matches."
        )
        tone = "exploratory and enthusiastic"

    return (
        f"CURRENT PHASE: DESTINATION\n"
        f"YOUR GOAL: {goal}\n"
        f"TONE: {tone}."
    )


# ── Itinerary phase — sub-state aware ────────────────────────────────────────

def _itinerary_phase_block(plan) -> str:
    """
    Two itinerary sub-states:

      Building  — plan.days is empty.  Groq writes the full itinerary from
                  scratch using the confirmed trip details.

      Reviewing — plan.days is populated.  The parsed itinerary appears in
                  the ITINERARY SO FAR block.  Groq presents what it built,
                  invites changes, or awaits final approval.

    The Building goal specifies an exact per-day format so ItineraryParser
    can reliably extract DayPlan objects from the prose:

        Day N: <title>
        Distance: X miles  |  Gain: Y ft
        Camp: <name> (or omit if day hike)
        Note: <one sentence>

    The confirmation string ("Itinerary confirmed — ready to save.") is exact
    and is also listed in RULES so Groq sees it on every phase.
    """
    if not plan.days:
        # ── Sub-state 1: build the itinerary ──────────────────────────────
        duration = plan.duration_days or 1
        day_word = "day" if duration == 1 else "days"
        # Ground-truth constraint: the per-day distances/gains MUST sum to the
        # real trail totals from the DB, not the LLM's guess. Without this Groq
        # invents figures (the "5 mi / 500 ft for a 2 mi / 118 ft trail" bug).
        totals_line = ""
        if plan.hike_length_km:
            miles = km_to_miles(plan.hike_length_km)
            feet  = m_to_feet(plan.hike_elevation_gain_m)
            gain_txt = f" and about {feet} ft of total elevation gain" if feet is not None else ""
            totals_line = (
                f"GROUND TRUTH: this trail is about {miles} miles long{gain_txt}. "
                f"The Distance and Gain figures across ALL days MUST sum to roughly these "
                f"totals — do NOT exceed them or invent larger numbers. For a short trail "
                f"this may be a single half-day; do not pad it into multiple days. "
            )
        goal = (
            f"Build a complete {duration}-{day_word} itinerary for the confirmed hike. "
            "Use the details in CONFIRMED TRIP (hike name, destination, duration, difficulty). "
            + totals_line +
            "For EVERY day, follow this exact format — each element on its own line:\n\n"
            "  Day N: <short descriptive title>\n"
            "  Distance: X miles  |  Gain: Y ft\n"
            "  Camp: <campsite name>   (omit this line entirely for day hikes or non-overnight days)\n"
            "  Note: <one practical sentence — water sources, timing, permits, or key hazards>\n\n"
            "Use actual trail names and landmarks you know. "
            "If a figure is an estimate, write 'approx.' before the number. "
            "Do not convert to km — use miles and feet throughout. "
            "After presenting all days, ask: 'Does this look right, or would you like any changes?'"
        )
        tone = "detailed and structured"

    else:
        # ── Sub-state 2: review / approve ─────────────────────────────────
        goal = (
            "The itinerary is in the ITINERARY SO FAR block below — that is what the user sees. "
            "Walk through it briefly and ask if they want any changes. "
            "If they request a change, describe the updated day(s) in the same "
            "'Day N: title / Distance / Camp / Note' format so the system can re-parse it. "
            "Once the user says it looks good or explicitly approves, respond with exactly: "
            "'Itinerary confirmed — ready to save.' "
            "Do not paraphrase that line."
        )
        tone = "collaborative and clear"

    return (
        f"CURRENT PHASE: ITINERARY\n"
        f"YOUR GOAL: {goal}\n"
        f"TONE: {tone}."
    )


# ── Finalize phase — sub-state aware ─────────────────────────────────────────

def _finalize_phase_block(session: TripSession) -> str:
    """
    Two finalize sub-states detected from phase_data:

      Presenting  — save_summary_shown not yet set.  Groq presents the full
                    trip recap in a clean structured format and asks the user
                    to confirm.  The section builders (CONFIRMED TRIP,
                    ITINERARY SO FAR) give Groq everything it needs.

      Confirming  — save_summary_shown is True; user has already seen the
                    summary.  If the user says yes, Groq emits "SAVE CONFIRMED"
                    as the first token so the backend can flag it.  If they
                    want changes, they should be redirected back to the
                    appropriate phase (which requires a DESTINATION RESET or
                    a note that changes aren't possible at this stage).

    The summary format is specified so the output is consistent and scannable:

        Trip: <hike name>, <destination>
        Duration: N days  |  Difficulty: <level>
        Gear notes: <one sentence — key gaps or "kit looks solid">
        Day 1: <title> — X mi, Y ft gain[, Camp: <name>]
        Day 2: ...
        ...

    Bug 3 fix: sub-state 1 now explicitly forbids emitting SAVE CONFIRMED.
    A user typing "save" as their first finalize message hits sub-state 1
    (summary not yet shown), and without this guard Groq would combine the
    summary presentation with a premature SAVE CONFIRMED in the same response,
    leaving the user seeing "Shall I save this trip?" after being told it's
    already confirmed.  The Python layer in trip_chat.py also gates
    save_confirmed on finalize_summary_prebuilt as a belt-and-suspenders check.
    """
    summary_shown = session.phase_data.get("save_summary_shown", False)

    if not summary_shown:
        # ── Sub-state 1: present the trip summary and ask ──────────────────
        #
        # Mark as shown now — trip_chat.py persists phase_data after this
        # turn, so the next request will see summary_shown=True.
        session.phase_data["save_summary_shown"] = True

        goal = (
            "Present a complete trip summary using CONFIRMED TRIP and ITINERARY SO FAR. "
            "Use this exact format:\n\n"
            "  Trip: <hike name>, <destination>\n"
            "  Trail: <X mi, Y ft gain — copy from CONFIRMED TRIP 'Trail stats'; omit if absent>\n"
            "  Duration: N days (<est. time on trail — copy from 'Est. time'>)  |  Difficulty: <level>\n"
            "  Gear notes: <one sentence — mention key missing items or say 'kit looks solid'>\n"
            "  Day 1: <title> — X mi, Y ft gain[, Camp: <campsite name>]\n"
            "  Day 2: <title> — X mi, Y ft gain[, Camp: <campsite name>]\n"
            "  ... (one line per day)\n\n"
            "After the summary, ask exactly: 'Shall I save this trip?'\n"
            "Do not add commentary or caveats — the user has already approved each section.\n"
            # Bug 3 fix: explicit prohibition stops Groq from collapsing sub-state 1
            # and sub-state 2 into a single response when the user says "save" before
            # they have seen the summary.
            "CRITICAL: Do NOT emit 'SAVE CONFIRMED' in this response under any "
            "circumstances — not even if the user's message says 'save', 'yes', or "
            "any other affirmative. The user must read this summary and reply in a "
            "separate message before you may confirm the save."
        )
        tone = "concise and warm"

    else:
        # ── Sub-state 2: user is responding to the save question ───────────
        goal = (
            "The user has seen the trip summary. "
            "If they say yes, confirm, or any clear affirmative: "
            "respond with 'SAVE CONFIRMED' as your very first two words, "
            "then add one warm closing sentence (e.g. 'Enjoy the trail!'). "
            "If they have a last-minute change or say no: acknowledge it, "
            "tell them which phase to revisit (destination, gear, or itinerary), "
            "and note that they can start a new trip if needed. "
            "Do not re-present the full summary."
        )
        tone = "warm and decisive"

    return (
        f"CURRENT PHASE: FINALIZE\n"
        f"YOUR GOAL: {goal}\n"
        f"TONE: {tone}."
    )


# ── Section builders ──────────────────────────────────────────────────────────

def _persona() -> str:
    return (
        "You are Trail AI, a knowledgeable and practical hiking trip planner. "
        "You know gear well, respect trail safety, and give honest advice. "
        "You never invent trail statistics you do not know — you say so and give estimates instead."
    )


def _phase_block(phase: str, cfg: dict) -> str:
    return (
        f"CURRENT PHASE: {phase.upper().replace('_', ' ')}\n"
        f"YOUR GOAL: {cfg['goal']}\n"
        f"TONE: {cfg['tone']}."
    )


def _hike_context_block(hike_context: str) -> str:
    return (
        "HIKE OPTIONS (each entry includes trail stats and a gear-readiness note "
        "based on the user's current kit).\n"
        "IMPORTANT: this data is for YOUR reasoning only. Do NOT retype or reproduce "
        "these entries verbatim (the full stats line or the Tags field) in your "
        "response — the system displays them as selectable cards right below your "
        "reply, so a verbatim copy would just be duplicated text. Your job is the "
        "prose that comes BEFORE those cards: reasoning about fit, and — when there "
        "are 3+ options — calling out your top picks BY NAME, each with one concrete, "
        "real fact drawn from this data (a real tag, its length, its gain — not vague "
        "filler). If a requested feature (e.g. water) is absent from a hike's tags, say "
        "so honestly in your prose rather than inventing a tag.\n"
        + hike_context
    )


def _gear_block(user_gear: list[dict]) -> str:
    if not user_gear:
        return "USER'S GEAR:\nNo gear items on record."

    lines = ["USER'S GEAR (owned items):"]
    by_cat: dict[str, list[dict]] = {}
    for item in user_gear:
        cat = item.get("category", "other").replace("_", " ").title()
        by_cat.setdefault(cat, []).append(item)

    for cat, items in by_cat.items():
        lines.append(f"  {cat}:")
        for item in items:
            weight_kg = round(float(item.get("weight", 0)) / 1000, 2)
            cost      = int(float(item.get("cost", 0)))
            lines.append(f"    • {item['name']} — {weight_kg} kg, ${cost}")

    return "\n".join(lines)


def _trip_block(plan) -> str:
    lines = [
        "CONFIRMED TRIP:",
        f"  Destination : {plan.destination_full}",
        f"  Activity    : {plan.activity_type.replace('_', ' ').title() if plan.activity_type else 'Not set'}",
        f"  Duration    : {plan.duration_days} day{'s' if plan.duration_days != 1 else ''}",
        f"  Difficulty  : {plan.difficulty.title() if plan.difficulty else 'Not specified'}",
    ]
    if plan.hike_name:
        lines.insert(1, f"  Hike        : {plan.hike_name}")

    # Real trail stats (from the DB at selection) — the authoritative figures the
    # summary must use. Groq must NOT invent different distance/gain numbers.
    if plan.hike_length_km:
        miles = km_to_miles(plan.hike_length_km)
        feet  = m_to_feet(plan.hike_elevation_gain_m)
        stat = f"  Trail stats : {miles} mi"
        if feet is not None:
            stat += f", {feet} ft gain"
        lines.append(stat)
    if plan.estimated_duration:
        lines.append(f"  Est. time   : {plan.estimated_duration} on trail")
    if plan.state:                                                           # ← NEW
        # "NC".title() → "Nc" — 2-letter state codes need to stay upper.
        state_label = (
            plan.state.upper() if len(plan.state) == 2 and plan.state.isalpha()
            else plan.state.replace("_", " ").title()
        )
        lines.append(f"  State       : {state_label}")
    if plan.notes:
        lines.append(f"  Notes       : {plan.notes}")
    return "\n".join(lines)

def _gaps_block(gaps: list[GearGap]) -> str:
    """
    Rendered in the gear_review phase only.  Gaps contain only the selected
    hike's analysis (promoted from phase_data by trip_chat.py).
    """
    lines    = ["GEAR GAPS for selected trail (reference only — the user has seen these):"]
    missing  = [g for g in gaps if g.issue == "missing"]
    marginal = [g for g in gaps if g.issue == "marginal"]

    if missing:
        lines.append("  Missing entirely:")
        for g in missing:
            line = f"    • [{g.category.replace('_', ' ')}] {g.detail}"
            if g.suggestion:
                line += f"  →  {g.suggestion}"
            lines.append(line)

    if marginal:
        lines.append("  Worth flagging:")
        for g in marginal:
            line = f"    • [{g.category.replace('_', ' ')}] {g.detail}"
            if g.suggestion:
                line += f"  →  {g.suggestion}"
            lines.append(line)

    if not missing and not marginal:
        lines.append("  No gaps — kit looks solid for this trail.")

    return "\n".join(lines)


def _itinerary_block(plan) -> str:
    if not plan.days:
        return ""
    lines = ["ITINERARY SO FAR:"]
    for day in plan.days:
        lines.append(f"  Day {day.day_number}: {day.title}")
        if day.distance_miles:
            lines.append(f"    Distance      : {day.distance_miles} mi")
        if day.elevation_gain_ft:
            lines.append(f"    Elevation gain: {day.elevation_gain_ft} ft")
        if day.campsite:
            lines.append(f"    Camp          : {day.campsite}")
        if day.notes:
            lines.append(f"    Notes         : {day.notes}")
    return "\n".join(lines)


def _summary_block(summary: str) -> str:
    return f"CONVERSATION SUMMARY (decisions made in earlier turns):\n{summary}"


# ── Rules — modular + phase-scoped ────────────────────────────────────────────
#
# The rules block was previously one ~1,200-token monolith sent verbatim every
# turn, regardless of phase. It's now split into a small always-on core plus
# per-signal fragments, and _rules(phase) assembles only the fragments that
# phase can actually act on. Each fragment carries a single worked example
# instead of the 3-4 it used to — the pattern is learned from one; the extras
# were pure token cost.
#
# Fragment → phase mapping (see _RULES_BY_PHASE):
#   destination : SEARCH_REFINE, DESTINATION RESET, trail-data honesty
#   gear_review : GEAR ADD, ADVANCE_PHASE, SEARCH_REFINE, DESTINATION RESET
#   itinerary   : itinerary format, ADVANCE_PHASE, SEARCH_REFINE, DESTINATION RESET
#   finalize    : save confirmation, DESTINATION RESET
#
# DESTINATION RESET rides along in every phase (a global escape hatch — the user
# can bail to a new location at any point). Everything else is scoped to where
# it's reachable, so e.g. the finalize prompt no longer ships the GEAR ADD or
# itinerary-format instructions it can never use.

_RULES_GENERAL = (
    "General\n"
    "- Stay focused on the current phase goal. Do not jump ahead.\n"
    "- Keep responses under 220 words unless building or revising an itinerary.\n"
    "- Never fabricate gear specs, trail distances, or elevation figures — write "
    "'approx.' before any estimate.\n"
    "- Do not repeat the full gear list back to the user unprompted.\n"
    "- Be direct. Avoid filler like 'Great question!' or 'Certainly!'."
)

_RULES_DESTINATION_RESET = (
    "DESTINATION RESET:\n"
    "- If the user wants a DIFFERENT geographic destination, begin your response with "
    "the exact words 'DESTINATION RESET' before anything else.\n"
    "- Triggers: naming a new place ('let's do Zion'), regret ('I don't love these, "
    "somewhere else?'), or 'instead' about a location.\n"
    "- Do NOT trigger on picking from the numbered options ('go with option 2 instead') "
    "— that's a trail selection, not a destination change.\n"
    "Example:\n"
    "  User: 'Actually, let's try Zion instead.'\n"
    "  You:  'DESTINATION RESET — great choice. What kind of hike are you after in Zion?'"
)

_RULES_SEARCH_REFINE = (
    "SEARCH_REFINE:\n"
    "- Use when the user wants different hike options WITHIN the same destination "
    "(different difficulty, a water feature, shorter/longer route).\n"
    "- Emit 'SEARCH_REFINE' as the very first word, then acknowledge the new criteria "
    "in one sentence. Do NOT ask where they want to hike — the destination is set.\n"
    "- Distinction: a NEW geographic place → DESTINATION RESET; different TRAIL CRITERIA "
    "at the same place → SEARCH_REFINE.\n"
    "Example:\n"
    "  User: 'These are too long — can I see shorter options?'\n"
    "  You:  'SEARCH_REFINE — sure, looking for shorter trails in the same area.'"
)

_RULES_ADVANCE_PHASE = (
    "ADVANCE_PHASE:\n"
    "- When the user clearly signals they are done with THIS phase, append the single "
    "token ADVANCE_PHASE on its own line at the very end of your response.\n"
    "- gear_review: user is happy with their kit / says 'proceed', 'looks good', 'skip'.\n"
    "- itinerary: user approves AFTER the itinerary has already been presented — never "
    "in the same response that first presents it; they must send a separate approval "
    "message.\n"
    "- Never emit it speculatively or mid-sentence. The token is stripped before the "
    "user sees it.\n"
    "Example:\n"
    "  User: 'proceed as is'\n"
    "  You (gear_review): 'Got it — your kit is set. On to the itinerary.\n"
    "                      ADVANCE_PHASE'"
)

_RULES_GEAR_ADD = (
    "GEAR ADD:\n"
    "- When the user confirms a specific item for one of the GEAR GAPS categories, "
    "append 'GEAR ADD: <category>' on its own line at the end, using the exact bracketed "
    "category from the GEAR GAPS block (e.g. '[hydration]' → GEAR ADD: hydration).\n"
    "- One line per confirmed gap. Never invent a category, reuse a resolved one, or emit "
    "speculatively. The token is stripped — describe the addition naturally in prose.\n"
    "Example:\n"
    "  User: 'Soft flasks sound good.'\n"
    "  You: 'Good call — I've added them to your kit. Still got navigation and first aid "
    "to consider — tackle those, or proceed as-is?\n"
    "        GEAR ADD: hydration'"
)

_RULES_ITINERARY_FORMAT = (
    "Itinerary format\n"
    "- Each day MUST start on its own line with 'Day N:' followed by a short title.\n"
    "- Use miles and feet throughout — never km or meters.\n"
    "- When the user approves the itinerary, say EXACTLY: 'Itinerary confirmed — ready "
    "to save.' Do not paraphrase that line."
)

_RULES_SAVE_CONFIRMATION = (
    "Save confirmation\n"
    "- When the user confirms they want to save, begin your response with exactly "
    "'SAVE CONFIRMED' (two words, no punctuation before them).\n"
    "- Only valid after the trip summary has been shown and the user has replied to "
    "'Shall I save this trip?'. If your current goal is to PRESENT the summary, you are "
    "in sub-state 1 — do NOT emit 'SAVE CONFIRMED' regardless of what the user said."
)

_RULES_TRAIL_DATA_HONESTY = (
    "Trail data honesty:\n"
    "- Never add, remove, or modify tags in a hike's Tags field — copy them verbatim from "
    "HIKE OPTIONS. If a requested feature is missing from the tags, say so in prose rather "
    "than inventing a tag.\n"
    "- If the HIKE OPTIONS block does NOT begin with a [DATA NOTE:] header, do not include "
    "any data-coverage disclaimers — each search is fresh; past gaps do not carry forward.\n"
    "- If the user asks about something outside the Tags vocabulary entirely (a landmark "
    "name, wildlife, cell service, trail surface), say plainly you don't have data tracked "
    "for that, rather than guessing from the trail name."
)

_RULES_BY_PHASE: dict[str, list[str]] = {
    "destination": [_RULES_SEARCH_REFINE, _RULES_DESTINATION_RESET, _RULES_TRAIL_DATA_HONESTY],
    "gear_review": [_RULES_GEAR_ADD, _RULES_ADVANCE_PHASE, _RULES_SEARCH_REFINE, _RULES_DESTINATION_RESET],
    "itinerary":   [_RULES_ITINERARY_FORMAT, _RULES_ADVANCE_PHASE, _RULES_SEARCH_REFINE, _RULES_DESTINATION_RESET],
    "finalize":    [_RULES_SAVE_CONFIRMATION, _RULES_DESTINATION_RESET],
}


def _rules(phase: str) -> str:
    """Assemble the always-on core + only the signal fragments the given phase
    can act on. See _RULES_BY_PHASE for the mapping and the module comment above
    for why it's split this way."""
    sections = [_RULES_GENERAL, *_RULES_BY_PHASE.get(phase, [])]
    return "RULES:\n\n" + "\n\n".join(sections)