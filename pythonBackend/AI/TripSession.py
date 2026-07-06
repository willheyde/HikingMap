import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from AI.TripPlan import TripPlan

# ── Constants ─────────────────────────────────────────────────────────────────

PHASES = ["destination", "gear_review", "itinerary", "finalize"]

# How many turns to keep in the raw window before summarization kicks in.
# A "turn" = one user message + one assistant message.
MESSAGE_WINDOW = 12

# ── Message helper ────────────────────────────────────────────────────────────

def _msg(role: str, content: str) -> dict:
    """Convenience constructor so callers don't build dicts by hand."""
    return {"role": role, "content": content, "ts": datetime.utcnow().isoformat()}


# ── TripSession ───────────────────────────────────────────────────────────────

@dataclass
class TripSession:
    # Identity
    session_id: str
    user_id: str

    # Phase
    phase: str = "destination"          # one of PHASES
    phase_data: dict = field(default_factory=dict)   # scratch space per phase

    # The growing trip plan
    plan: TripPlan = field(default_factory=TripPlan)

    # Memory
    summary: str = ""                   # rolling ~100-word summary of old turns
    messages: list[dict] = field(default_factory=list)   # sliding window of raw turns
    total_turns: int = 0                # ever-incrementing, used to trigger summarization

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def new(cls, user_id: str) -> "TripSession":
        return cls(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
        )

    # ── Phase helpers ─────────────────────────────────────────────────────────

    def advance_phase(self) -> None:
        """Move to the next phase. No-op if already at finalize."""
        idx = PHASES.index(self.phase)
        if idx < len(PHASES) - 1:
            self.phase = PHASES[idx + 1]
            self.phase_data = {}        # clear scratch space on transition
            self._touch()

    def is_final_phase(self) -> bool:
        return self.phase == "finalize"

    # ── Message window ────────────────────────────────────────────────────────

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        """
        Append a completed turn (user + assistant) to the sliding window.
        Prunes oldest turns when the window exceeds MESSAGE_WINDOW.
        Callers should check needs_summarization() after this and fire
        the Summarizer if True.
        """
        self.messages.append(_msg("user",      user_content))
        self.messages.append(_msg("assistant", assistant_content))
        self.total_turns += 1
        self._prune_window()
        self._touch()

    def _prune_window(self) -> None:
        """
        Keep only the most recent MESSAGE_WINDOW turns (each turn = 2 messages).
        Anything older has already been folded into self.summary by the Summarizer.
        """
        max_messages = MESSAGE_WINDOW * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def needs_summarization(self) -> bool:
        """
        True when total turn count crosses a summarization threshold.
        We re-summarize every MESSAGE_WINDOW turns so the summary stays fresh.
        """
        return self.total_turns > 0 and self.total_turns % MESSAGE_WINDOW == 0
    def clear_window(self) -> None:
        """Wipe conversation history. Called on destination reset so Groq
        doesn't carry stale phase context into the next turn."""
        self.messages.clear()
        self.total_turns = 0    # prevent spurious summarization on near-empty window
    def get_window_messages(self) -> list[dict]:
        """
        Return the sliding window stripped of internal 'ts' field,
        ready to be passed directly to Grok.
        """
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def update_summary(self, new_summary: str) -> None:
        self.summary = new_summary.strip()
        self._touch()

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps({
            "session_id":  self.session_id,
            "user_id":     self.user_id,
            "phase":       self.phase,
            "phase_data":  self.phase_data,
            "plan":        self.plan.to_dict(),
            "summary":     self.summary,
            "messages":    self.messages,
            "total_turns": self.total_turns,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        })

    @classmethod
    def from_json(cls, raw: str) -> "TripSession":
        d = json.loads(raw)
        session = cls(
            session_id  = d["session_id"],
            user_id     = d["user_id"],
            phase       = d["phase"],
            phase_data  = d.get("phase_data", {}),
            plan        = TripPlan.from_dict(d.get("plan", {})),
            summary     = d.get("summary", ""),
            messages    = d.get("messages", []),
            total_turns = d.get("total_turns", 0),
            created_at  = d["created_at"],
            updated_at  = d["updated_at"],
        )
        return session

    # ── Internal ──────────────────────────────────────────────────────────────

    def _touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()

    def __repr__(self) -> str:
        return (
            f"<TripSession {self.session_id[:8]}… "
            f"user={self.user_id} phase={self.phase} turns={self.total_turns}>"
        )