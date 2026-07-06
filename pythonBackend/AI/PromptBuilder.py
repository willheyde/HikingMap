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
    response when the user changes destination.  _rules() contains three
    concrete examples so Groq learns pattern, not just rule.  trip_chat.py
    also runs a Python-level phrase detector as a pre-response fallback.
Groq parameters
    chat() accepts max_tokens / temperature overrides.  trip_chat.py passes
    per-phase values from PHASE_GROQ_PARAMS so callers don't need to know
    prompt internals.
"""

from .TripSession import TripSession
from .TripPlan    import GearGap


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

    if hike_context and session.phase == "destination":
        sections.append(_hike_context_block(hike_context))

    if plan.is_destination_set():
        sections.append(_trip_block(plan))

    if plan.gear_gaps and session.phase == "gear_review":
        sections.append(_gaps_block(plan.gear_gaps))

    if plan.days:
        sections.append(_itinerary_block(plan))

    if session.summary:
        sections.append(_summary_block(session.summary))

    sections.append(_rules())

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
        goal = (
            f"Build a complete {duration}-{day_word} itinerary for the confirmed hike. "
            "Use the details in CONFIRMED TRIP (hike name, destination, duration, difficulty). "
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
            "  Duration: N days  |  Difficulty: <level>\n"
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


def _rules() -> str:
    return (
        "RULES:\n"
        "\n"
        "General\n"
        "- Stay focused on the current phase goal. Do not jump ahead.\n"
        "- Keep responses under 220 words unless building or revising an itinerary.\n"
        "- Never fabricate gear specs, trail distances, or elevation figures — "
        "  write 'approx.' before any estimate.\n"
        "- Do not repeat the full gear list back to the user unprompted.\n"
        "- Be direct. Avoid filler phrases like 'Great question!' or 'Certainly!'.\n"
        "- Never add, remove, or modify tags in a hike's Tags field — copy them verbatim\n"
        "  from the HIKE OPTIONS block. If a requested feature is missing from the tags,\n"
        "  acknowledge that in prose, not by inventing a tag.\n"
        "\n"
        "Itinerary format\n"
        "- Each day MUST start on its own line with 'Day N:' followed by a short title.\n"
        "- Use miles and feet throughout — never km or meters.\n"
        "- When the user approves the itinerary, say EXACTLY:\n"
        "    Itinerary confirmed — ready to save.\n"
        "  Do not paraphrase that line.\n"
        "\n"
        "Save confirmation\n"
        "- When the user confirms they want to save the trip, begin your response with\n"
        "  exactly 'SAVE CONFIRMED' (two words, no punctuation before them).\n"
        "- Do not say 'SAVE CONFIRMED' speculatively — only when the user clearly says yes.\n"
        "- 'SAVE CONFIRMED' is ONLY valid in finalize sub-state 2 (after the trip summary\n"
        "  has been shown and the user has replied to 'Shall I save this trip?').\n"
        "  If the current goal says to present the summary, you are in sub-state 1 —\n"
        "  do NOT emit 'SAVE CONFIRMED' regardless of what the user said.\n"
        "\n"
        "DESTINATION RESET — read this carefully:\n"
        "- If the user indicates they want a different destination at ANY point after the\n"
        "  destination phase, you MUST say 'DESTINATION RESET' as the very first words of\n"
        "  your response, before anything else.\n"
        "- Triggers include (but are not limited to):\n"
        "    • Naming a new place  ('let's do Zion', 'what about Colorado?', 'try Sedona')\n"
        "    • Expressing regret   ('I don't love these', 'actually never mind')\n"
        "    • Asking to restart   ('start over', 'different hike', 'somewhere else')\n"
        "    • Any phrasing with 'instead' about a *location or destination*\n"
        "- Do NOT trigger on trail re-selection from the numbered list:\n"
        "    ('actually let's do 2 instead', 'go with option 3 instead') — these are\n"
        "    picking from the options already shown, not changing destination.\n"
        "\n"
        "Examples:\n"
        "  User: 'Actually, let's try Zion instead.'\n"
        "  You:  'DESTINATION RESET — great choice. What kind of hike are you looking for in Zion?'\n"
        "\n"
        "  User: 'Actually, let's do 2 instead.'  ← trail re-selection, NOT a reset\n"
        "  You:  [confirm selection of option 2, no DESTINATION RESET]\n"
        "\n"
        "  User: 'Hmm, what about trails in Colorado?'\n"
        "  You:  'DESTINATION RESET — let's look at Colorado. How many days are you thinking?'\n"
        "\n"
        "  User: 'I don't love these options, can we try somewhere else?'\n"
        "  You:  'DESTINATION RESET — of course. Where would you like to explore?'"
        "\n"
        "SEARCH_REFINE — read this carefully:\n"
        "- Use this when the user wants different hike options WITHIN the same destination\n"
        "  (different difficulty, wants a water feature, shorter route, etc.).\n"
        "- THIS APPLIES IN ALL PHASES including gear_review and itinerary — if the user\n"
        "  says they want a different kind of hike at any point, emit SEARCH_REFINE.\n"
        "- Emit 'SEARCH_REFINE' as the very first word of your response.\n"
        "- Do NOT emit DESTINATION RESET for these cases.\n"
        "- After 'SEARCH_REFINE', briefly acknowledge the criteria change in one sentence.\n"
        "  Do NOT ask where they want to hike — the destination is already confirmed.\n"
        "\n"
        "SEARCH_REFINE vs DESTINATION RESET — the key distinction:\n"
        "  • User names a NEW geographic place   → DESTINATION RESET\n"
        "  • User wants different TRAIL CRITERIA → SEARCH_REFINE (same location)\n"
        "\n"
        "Examples:\n"
        "  User: 'Instead, can I see a medium hike with a water feature?'\n"
        "  You:  'SEARCH_REFINE — great idea. Let me pull up medium-difficulty RI trails with water features.'\n"
        "\n"
        "  User: 'These are too long — can I see shorter options?'\n"
        "  You:  'SEARCH_REFINE — sure, looking for shorter trails in the same area.'\n"
        "\n"
        "  User (in gear_review): 'Actually I want the hike to have a water feature and be harder.'\n"
        "  You:  'SEARCH_REFINE — got it, looking for harder RI trails with water features.'\n"
        "\n"
        "  User: 'Actually let's try Zion instead.'\n"
        "  You:  'DESTINATION RESET — great choice. What kind of hike are you looking for in Zion?'\n"
        "\n"
        "ADVANCE_PHASE — read this carefully:\n"
        "- When the user clearly signals they are done with the current phase, "
        "append the single token ADVANCE_PHASE on its own line at the very end "
        "of your response — after all other content.\n"
        "- Use it in these phases only:\n"
        "    • gear_review : user says they're happy with their kit, ready to move on,\n"
        "                    or explicitly asks to skip ('proceed', 'looks good', 'skip this').\n"
        "    • Itinerary Rule:"
        "        The user must approve the itinerary in their message AFTER the itinerary has already been presented."
        "        Do NOT emit ADVANCE_PHASE in the same response where you first present the itinerary — even if the user's message that triggered the presentation sounds like approval."
        "         The user must send a separate, explicit approval message before you confirm and advance."
        "- Do NOT emit ADVANCE_PHASE speculatively or mid-sentence.\n"
        "- Do NOT emit ADVANCE_PHASE in the destination or finalize phases.\n"
        "- The token is stripped before the user sees it — they will never see it.\n"
        "\n"
        "Examples:\n"
        "  User: 'Looks good, let's move on.'\n"
        "  You (gear_review):  'Great — moving on to build your itinerary.\n"
        "                       ADVANCE_PHASE'\n"
        "\n"
        "  User: 'proceed as is'\n"
        "  You (gear_review):  'Got it — your kit is set. On to the itinerary.\n"
        "                       ADVANCE_PHASE'\n"
        "\n"
        "  User: 'that looks right'\n"
        "  You (itinerary):    'Itinerary confirmed — ready to save.\n"
        "                       ADVANCE_PHASE'\n"
        "\n"
        "GEAR ADD — read this carefully:\n"
        "- When the user confirms a specific item for one of the GEAR GAPS categories, "
        "append GEAR ADD: <category> on its own line at the very end of your response, "
        "using the category name shown in brackets in the GEAR GAPS block "
        "(e.g. the gap shown as '[hydration]' → GEAR ADD: hydration).\n"
        "- Only use category names that appear in the GEAR GAPS block — never invent "
        "one, and never reuse one that's no longer listed (it's already resolved).\n"
        "- Emit one GEAR ADD line per gap the user confirms; if they confirm two gaps "
        "in the same message, use two separate GEAR ADD lines.\n"
        "- Do not emit GEAR ADD speculatively, for gaps the user hasn't directly "
        "confirmed this turn, or while still discussing options for a gap.\n"
        "- The token is stripped before the user sees it — describe the addition "
        "naturally in your prose (e.g. 'I've added a water filter to your kit').\n"
        "- GEAR ADD is only used in the gear_review phase.\n"
        "\n"
        "Examples:\n"
        "  User: 'Soft flasks sound good, let's go with that.'\n"
        "  You (gear_review): 'Good call — soft flasks are light and pack down small. "
        "I've added them to your kit. You've still got navigation, illumination, and "
        "first aid to think about — want to tackle those too, or proceed as-is?\n"
        "                       GEAR ADD: hydration'\n"
        "\n"
        "  User: 'I'll grab a headlamp and a first aid kit too, then I'm good to go.'\n"
        "  You (gear_review): 'Done — I've added a headlamp and a first-aid kit to "
        "your kit. Your gear looks solid for this trail now.\n"
        "                       GEAR ADD: illumination\n"
        "                       GEAR ADD: first_aid\n"
        "                       ADVANCE_PHASE'\n"
        "DATA NOTE rule:\n"
        "- If the current HIKE OPTIONS block does NOT begin with a [DATA NOTE:] header,\n"
        "  do NOT include any data coverage disclaimers in your response — not even\n"
        "  if a previous assistant turn mentioned one. Each search is fresh; past gaps\n"
        "  do not carry forward.\n"
        "\n"
        "Untracked feature requests\n"
        "- The Tags field on each hike in HIKE OPTIONS reflects every feature this\n"
        "  system can currently search or filter on. If the user asks about something\n"
        "  with no equivalent in that tag vocabulary at all — a specific landmark name,\n"
        "  a wildlife sighting, cell service, trail surface, anything outside what Tags\n"
        "  can express — say plainly that you don't have data tracked for that specific\n"
        "  thing, rather than guessing from the trail name or staying silent on it.\n"
        "- This is different from a [DATA NOTE:] header (a tracked feature with zero\n"
        "  matches in this area) — this rule covers requests for things that aren't\n"
        "  tracked at all, anywhere.\n"
    )