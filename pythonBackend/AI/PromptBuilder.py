"""
PromptBuilder.py

Pure function module — takes a TripSession + user gear list and returns
a fully assembled system prompt string ready for Grok.

Nothing stateful here. Keeping prompt logic isolated makes it easy to
iterate on wording without touching business logic.
"""

from .models.TripSession import TripSession
from .models.TripPlan import GearGap

# ── Phase goal definitions ────────────────────────────────────────────────────
#
# Each phase tells Grok exactly what its job is right now.
# The PhaseController decides when to advance; Grok just executes the phase.

PHASE_CONFIGS = {
    "destination": {
        "goal": (
            "Help the user choose and confirm a hiking destination. "
            "If a destination has already been parsed from their message, confirm it with them "
            "and ask about anything still missing (duration, difficulty). "
            "Once destination, duration, and difficulty are confirmed, tell the user you're "
            "ready to review their gear for this trip. Do not move on until confirmed."
        ),
        "tone": "exploratory and enthusiastic",
    },
    "gear_review": {
        "goal": (
            "Review the user's gear against the trip requirements. "
            "The GEAR GAPS section below lists exactly what is missing or marginal — "
            "present these clearly but conversationally, one category at a time if there are many. "
            "Let the user decide what they want to address. Once the user says their gear list "
            "is finalized or they're happy with it, confirm and say you're ready to build the itinerary."
        ),
        "tone": "practical and direct",
    },
    "itinerary": {
        "goal": (
            "Build a day-by-day trip itinerary. Include estimated mileage, elevation gain, "
            "campsite or turnaround suggestions, and any notable waypoints. "
            "Be specific — use real trail names and landmarks where you know them. "
            "If you're uncertain of exact figures, give reasonable estimates and say so. "
            "Once the user approves the itinerary, confirm it and say you're ready to save the trip."
        ),
        "tone": "detailed and structured",
    },
    "finalize": {
        "goal": (
            "Summarize the complete trip plan: destination, duration, gear list, and day-by-day itinerary. "
            "Ask the user if they'd like to save it. If yes, confirm the save. "
            "Keep this concise — the user has already seen all the details."
        ),
        "tone": "concise and warm",
    },
}

# ── Prompt assembly ───────────────────────────────────────────────────────────

def build_system_prompt(
    session:    TripSession,
    user_gear:  list[dict],         # raw item dicts from your DB
) -> str:
    """
    Assembles the full system prompt for a Grok API call.

    Args:
        session:   current TripSession (phase, plan, summary all read from here)
        user_gear: list of gear item dicts, each expected to have at minimum:
                   { name, category, weight, cost }

    Returns:
        A single string to be passed as the system message.
    """
    phase_cfg = PHASE_CONFIGS[session.phase]
    plan      = session.plan

    sections = [
        _persona(),
        _phase_block(session.phase, phase_cfg),
        _gear_block(user_gear),
    ]

    if plan.is_destination_set():
        sections.append(_trip_block(plan))

    if plan.gear_gaps:
        sections.append(_gaps_block(plan.gear_gaps))

    if plan.days:
        sections.append(_itinerary_block(plan))

    if session.summary:
        sections.append(_summary_block(session.summary))

    sections.append(_rules())

    return "\n\n".join(s.strip() for s in sections if s.strip())


# ── Section builders ──────────────────────────────────────────────────────────

def _persona() -> str:
    return (
        "You are Trail AI, a knowledgeable and practical hiking trip planner. "
        "You know gear well, respect trail safety, and give honest advice. "
        "You never invent trail statistics you don't know — you say so and give estimates instead."
    )


def _phase_block(phase: str, cfg: dict) -> str:
    return (
        f"CURRENT PHASE: {phase.upper().replace('_', ' ')}\n"
        f"YOUR GOAL: {cfg['goal']}\n"
        f"TONE: {cfg['tone']}."
    )


def _gear_block(user_gear: list[dict]) -> str:
    if not user_gear:
        return "USER'S GEAR:\nNo gear items on record."

    lines = ["USER'S GEAR (owned items):"]
    # Group by category for readability
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
    if plan.notes:
        lines.append(f"  Notes       : {plan.notes}")
    return "\n".join(lines)


def _gaps_block(gaps: list[GearGap]) -> str:
    lines = ["GEAR GAPS (use these to guide the gear review — do not re-derive them):"]
    missing  = [g for g in gaps if g.issue == "missing"]
    marginal = [g for g in gaps if g.issue == "marginal"]

    if missing:
        lines.append("  Missing entirely:")
        for g in missing:
            line = f"    • [{g.category}] {g.detail}"
            if g.suggestion:
                line += f" Suggestion: {g.suggestion}"
            lines.append(line)

    if marginal:
        lines.append("  Marginal / worth flagging:")
        for g in marginal:
            line = f"    • [{g.category}] {g.detail}"
            if g.suggestion:
                line += f" Suggestion: {g.suggestion}"
            lines.append(line)

    return "\n".join(lines)


def _itinerary_block(plan) -> str:
    if not plan.days:
        return ""
    lines = ["ITINERARY SO FAR:"]
    for day in plan.days:
        lines.append(f"  Day {day.day_number}: {day.title}")
        if day.distance_miles:
            lines.append(f"    Distance: {day.distance_miles} mi")
        if day.elevation_gain_ft:
            lines.append(f"    Elevation gain: {day.elevation_gain_ft} ft")
        if day.campsite:
            lines.append(f"    Camp: {day.campsite}")
        if day.notes:
            lines.append(f"    Notes: {day.notes}")
    return "\n".join(lines)


def _summary_block(summary: str) -> str:
    return f"CONVERSATION SUMMARY (decisions made in earlier turns):\n{summary}"


def _rules() -> str:
    return (
        "RULES:\n"
        "- Stay focused on the current phase goal. Don't jump ahead.\n"
        "- Keep responses under 220 words unless building an itinerary.\n"
        "- Never fabricate gear specs, trail distances, or elevation figures.\n"
        "- If the user wants to change destination mid-session, acknowledge it "
        "  and explicitly say 'DESTINATION RESET' so the system can handle it.\n"
        "- Do not repeat the full gear list back to the user unprompted.\n"
        "- Be direct. Avoid filler phrases like 'Great question!' or 'Certainly!'."
    )