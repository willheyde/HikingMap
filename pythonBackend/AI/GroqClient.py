"""
GroqClient.py

Assembles the full message payload (system + summary + window + new message)
and makes the Groq API call.  Also tracks approximate token usage for
future session limiting.

Two public methods:

    chat()     — full conversational call with session context assembly.
                 Used by trip_chat.py for every user-facing turn.

    extract()  — lightweight single-turn call for structured extraction.
                 No summary, no window, no session context.  Used by
                 ItineraryParser for the second-pass JSON extraction call.
                 Runs at low temperature (0.1) to maximise output stability.
"""

import logging
import os
from groq import Groq

logger = logging.getLogger(__name__)

CHAT_MODEL = "llama-3.3-70b-versatile"
EXTRACT_MODEL = "llama-3.1-8b-instant"  

# Per-call defaults used by chat().
# extract() overrides these internally with tighter values.
_CHAT_MAX_TOKENS  = 1024
_CHAT_TEMPERATURE = 0.6

# Extraction call parameters — deterministic and token-efficient.
_EXTRACT_MAX_TOKENS  = 700
_EXTRACT_TEMPERATURE = 0.1


class GroqClient:
    def __init__(self, api_key: str | None = None):
        self._groq = Groq(api_key=api_key or os.environ["HikeKey"])

    # ── Conversational call ───────────────────────────────────────────────────

    def chat(
        self,
        system_prompt:   str,
        summary:         str,
        window_messages: list[dict],   # from session.get_window_messages()
        user_message:    str,
        max_tokens:      int   = _CHAT_MAX_TOKENS,
        temperature:     float = _CHAT_TEMPERATURE,
    ) -> tuple[str, int]:
        """
        Full conversational call with session context assembly.

        The optional max_tokens / temperature overrides exist so trip_chat.py
        can tune per-phase without touching this class (e.g. itinerary phase
        needs more tokens; destination phase wants lower temperature).

        Returns:
            (response_text, total_tokens_used)
        """
        messages = self._assemble(system_prompt, summary, window_messages, user_message)

        response = self._groq.chat.completions.create(
            model       = CHAT_MODEL,
            max_tokens  = max_tokens,
            temperature = temperature,
            messages    = messages,
        )

        text        = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens if response.usage else 0

        logger.info("GroqClient.chat: %d tokens used this turn.", tokens_used)
        return text, tokens_used

    # ── Structured extraction call ────────────────────────────────────────────

    def extract(
        self,
        system_prompt: str,
        content:       str,
    ) -> str:
        """
        Lightweight single-turn call for structured extraction tasks.

        No summary, no conversation window — just a system prompt and a
        single user message containing the content to extract from.

        Used by ItineraryParser to convert a prose itinerary into JSON.
        Low temperature maximises stability; tighter token budget keeps
        cost minimal since the output is JSON, not prose.

        Returns:
            The raw response string (caller is responsible for parsing).
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": content},
        ]

        response = self._groq.chat.completions.create(
            model       = EXTRACT_MODEL,
            max_tokens  = _EXTRACT_MAX_TOKENS,
            temperature = _EXTRACT_TEMPERATURE,
            messages    = messages,
        )

        text        = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens if response.usage else 0

        logger.info("GroqClient.extract: %d tokens used.", tokens_used)
        return text

    # ── Internal ──────────────────────────────────────────────────────────────

    def _assemble(
        self,
        system_prompt:   str,
        summary:         str,
        window_messages: list[dict],
        user_message:    str,
    ) -> list[dict]:
        """
        Final message list structure:
          [system] → [summary as system note] → [window] → [new user msg]

        The summary is injected as a system turn so it doesn't eat into
        conversational context and Groq doesn't treat it as something
        the assistant said.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if summary:
            messages.append({
                "role":    "system",
                "content": f"[PRIOR CONTEXT SUMMARY]\n{summary}",
            })

        messages.extend(window_messages)
        messages.append({"role": "user", "content": user_message})

        return messages