"""
GroqClient.py

Assembles the full message payload (system + summary + window + new message)
and makes the Grok API call. Also tracks approximate token usage for
future session limiting.
"""

import logging
import os
from groq import Groq

logger = logging.getLogger(__name__)

CHAT_MODEL   = "llama-3.3-70b-versatile"   # swap to your preferred Grok model
MAX_TOKENS   = 1024
TEMPERATURE  = 0.6


class GroqClient:
    def __init__(self, api_key: str | None = None):
        self._groq = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])

    def chat(
        self,
        system_prompt:  str,
        summary:        str,
        window_messages: list[dict],   # from session.get_window_messages()
        user_message:   str,
    ) -> tuple[str, int]:
        """
        Makes a single chat completion call.

        Returns:
            (response_text, total_tokens_used)
        """
        messages = self._assemble(system_prompt, summary, window_messages, user_message)

        response = self._groq.chat.completions.create(
            model       = CHAT_MODEL,
            max_tokens  = MAX_TOKENS,
            temperature = TEMPERATURE,
            messages    = messages,
        )

        text         = response.choices[0].message.content.strip()
        tokens_used  = response.usage.total_tokens if response.usage else 0

        logger.info("GroqClient: %d tokens used this turn.", tokens_used)
        return text, tokens_used

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
          [system] → [summary as assistant note] → [window] → [new user msg]

        The summary is injected as a system turn so it doesn't eat into
        the conversational context and Grok doesn't treat it as something
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