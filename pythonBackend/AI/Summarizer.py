"""
Summarizer.py

Condenses the current sliding window of messages into a ~100-word
summary that gets stored on the session and injected into future
system prompts.

Uses llama-3.1-8b-instant (cheap + fast) — this should be fired
async so it never blocks the main chat response.
"""

import logging
from groq import Groq
import os

logger = logging.getLogger(__name__)

SUMMARIZER_MODEL   = "llama-3.1-8b-instant"
SUMMARIZER_TOKENS  = 180     # enough for ~100 words with some headroom
SUMMARIZER_TEMP    = 0.1     # near-deterministic; we want facts, not creativity

SYSTEM_PROMPT = """You are a compact summarizer for a hiking trip planning conversation.
Given a set of messages between a user and Trail AI, write a factual summary of:
- What destination (if any) has been discussed or confirmed
- What gear gaps were identified
- What decisions the user has made
- What phase the conversation is in

Write in third person. Maximum 100 words. No bullet points. Plain prose only.
Focus on decisions and facts — not pleasantries or filler."""

USER_TEMPLATE = """Summarize the following conversation excerpt:\n\n{transcript}

Previous summary (if any, incorporate it):\n{prev_summary}"""


class Summarizer:
    def __init__(self, api_key: str | None = None):
        self._groq = Groq(api_key=api_key or os.environ["HikeKey"])

    def summarize(
        self,
        messages:     list[dict],   # the current sliding window (role/content dicts)
        prev_summary: str = "",     # existing summary to incorporate
    ) -> str:
        """
        Produces a fresh ~100-word summary from the message window.
        Returns the summary string, or the previous summary on failure.

        Args:
            messages:     list of {"role": ..., "content": ...} dicts
            prev_summary: the session's existing summary string

        Returns:
            New summary string.
        """
        if not messages:
            return prev_summary

        transcript = self._format_transcript(messages)

        try:
            response = self._groq.chat.completions.create(
                model      = SUMMARIZER_MODEL,
                max_tokens = SUMMARIZER_TOKENS,
                temperature= SUMMARIZER_TEMP,
                messages   = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": USER_TEMPLATE.format(
                        transcript   = transcript,
                        prev_summary = prev_summary or "None.",
                    )},
                ],
            )
            summary = response.choices[0].message.content.strip()
            logger.info("Summarizer produced %d-word summary.", len(summary.split()))
            return summary

        except Exception as e:
            logger.error("Summarizer failed: %s — keeping previous summary.", e)
            return prev_summary     # safe fallback: old summary is better than nothing

    # ── Internal ──────────────────────────────────────────────────────────────

    def _format_transcript(self, messages: list[dict]) -> str:
        """
        Formats the message window into a readable transcript string.
        Strips timestamps if present.
        """
        lines = []
        for m in messages:
            role    = m.get("role", "unknown").upper()
            content = m.get("content", "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n\n".join(lines)