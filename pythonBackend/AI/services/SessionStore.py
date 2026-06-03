import os
import logging
from typing import Optional

import redis

from models.TripSession import TripSession

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_TTL_SECONDS = 60 * 60 * 2      # 2 hours idle expiry
KEY_PREFIX          = "trip_session:"


def _key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


# ── SessionStore ──────────────────────────────────────────────────────────────

class SessionStore:
    """
    Thin Redis wrapper. All session persistence goes through here so
    nothing else in the codebase knows about Redis directly.

    Usage:
        store = SessionStore()
        session = TripSession.new(user_id="u_123")
        store.save(session)

        loaded = store.get(session.session_id)
        store.delete(session.session_id)
    """

    def __init__(
        self,
        url: Optional[str]  = None,
        ttl: int            = DEFAULT_TTL_SECONDS,
    ):
        """
        Args:
            url: Redis connection URL. Falls back to REDIS_URL env var,
                 then localhost:6379.
            ttl: Seconds before an idle session expires. Reset on every save.
        """
        redis_url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl   = ttl

    # ── Core operations ───────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[TripSession]:
        """
        Load a session by ID. Returns None if not found or expired.
        Bumps the TTL on every successful read (sliding expiry).
        """
        try:
            raw = self._redis.get(_key(session_id))
            if raw is None:
                return None
            session = TripSession.from_json(raw)
            # Slide the TTL forward on access
            self._redis.expire(_key(session_id), self._ttl)
            return session
        except Exception as e:
            logger.error("SessionStore.get failed for %s: %s", session_id, e)
            return None

    def save(self, session: TripSession) -> bool:
        """
        Persist a session. Resets the TTL.
        Returns True on success, False on failure.
        """
        try:
            self._redis.setex(
                name  = _key(session.session_id),
                time  = self._ttl,
                value = session.to_json(),
            )
            return True
        except Exception as e:
            logger.error("SessionStore.save failed for %s: %s", session.session_id, e)
            return False

    def delete(self, session_id: str) -> bool:
        """
        Explicitly delete a session (e.g. after trip is saved to DB).
        Returns True if the key existed and was deleted.
        """
        try:
            deleted = self._redis.delete(_key(session_id))
            return deleted > 0
        except Exception as e:
            logger.error("SessionStore.delete failed for %s: %s", session_id, e)
            return False

    # ── Utility ───────────────────────────────────────────────────────────────

    def exists(self, session_id: str) -> bool:
        """Quick existence check without deserializing."""
        try:
            return self._redis.exists(_key(session_id)) > 0
        except Exception as e:
            logger.error("SessionStore.exists failed for %s: %s", session_id, e)
            return False

    def get_or_create(self, session_id: Optional[str], user_id: str) -> tuple[TripSession, bool]:
        """
        Convenience method for the chat endpoint.

        Returns (session, created) where created=True if a new session was made.
        Pass session_id=None to always create fresh.
        """
        if session_id:
            session = self.get(session_id)
            if session:
                return session, False

        session = TripSession.new(user_id=user_id)
        self.save(session)
        return session, True

    def ttl(self, session_id: str) -> int:
        """Returns remaining TTL in seconds, or -2 if key doesn't exist."""
        try:
            return self._redis.ttl(_key(session_id))
        except Exception:
            return -2

    def ping(self) -> bool:
        """Health check — True if Redis is reachable."""
        try:
            return self._redis.ping()
        except Exception:
            return False