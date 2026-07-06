import os
import json
import logging
from typing import Optional

import redis

from .TripSession import TripSession

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60 * 60 * 2
KEY_PREFIX          = "trip_session:"
ACTIVE_SET_PREFIX   = "trip_session_active:"   # per-user set of active session_ids


def _key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


def _active_key(user_id: str) -> str:
    return f"{ACTIVE_SET_PREFIX}{user_id}"


class SessionStoreUnavailable(Exception):
    """
    Raised when Redis itself is unreachable (connection/timeout error) —
    distinct from a legitimate cache miss (raw is None, key just doesn't
    exist or expired).

    Callers MUST NOT catch this and silently fall back to creating a new
    session — that's exactly the bug this class exists to prevent. A
    Redis outage should surface as a clear error to the frontend, not as
    a phantom new conversation that's quietly forgotten everything.
    """
    pass


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
        url: Optional[str] = None,
        ttl: int           = DEFAULT_TTL_SECONDS,
    ):
        redis_url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl   = ttl

        # Confirm connection on startup
        try:
            self._redis.ping()
            logger.info("SessionStore connected to Redis at %s (TTL=%ds)", redis_url, ttl)
        except Exception as e:
            logger.error("SessionStore failed to connect to Redis at %s: %s", redis_url, e)

    # ── Core operations ───────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[TripSession]:
        # The GET call itself failing means Redis is unreachable — this is
        # NOT the same as a legitimate miss, so it must not be swallowed
        # into a None return (get_or_create would silently fabricate a
        # fresh session and the caller would have no idea history was lost).
        try:
            raw = self._redis.get(_key(session_id))
        except Exception as e:
            logger.error("get failed  session_id=%s  error=%s", session_id, e)
            raise SessionStoreUnavailable(
                f"Redis unreachable while fetching session_id={session_id}: {e}"
            ) from e

        if raw is None:
            logger.info("MISS  session_id=%s", session_id)
            return None

        # Corrupt/unparseable session data is a real miss, not a connection
        # problem — treat it as gone rather than raising, so a fresh
        # session can be created normally.
        try:
            session = TripSession.from_json(raw)
        except Exception as e:
            logger.error("get: corrupt session data  session_id=%s  error=%s", session_id, e)
            return None

        # TTL refresh riding on the same connection can fail independently
        # of the read that already succeeded above. Don't let a refresh
        # failure discard a perfectly good session.
        try:
            self._redis.expire(_key(session_id), self._ttl)
        except Exception as e:
            logger.warning("get: ttl refresh failed  session_id=%s  error=%s", session_id, e)

        logger.info("HIT   session_id=%s  ttl_reset=%ds", session_id, self._ttl)
        return session

    def save(self, session: TripSession) -> bool:
        try:
            self._redis.setex(
                name  = _key(session.session_id),
                time  = self._ttl,
                value = session.to_json(),
            )
            logger.info("SAVE  session_id=%s  ttl=%ds", session.session_id, self._ttl)
            return True
        except Exception as e:
            logger.error("save failed  session_id=%s  error=%s", session.session_id, e)
            return False

    def delete(self, session_id: str) -> bool:
        # Read first so the active-set entry (keyed by user_id, which the
        # caller doesn't necessarily have handy — /api/trip/save only takes
        # session_id) can be cleaned up too. Best-effort: a failure here
        # just leaves a stale set entry, which list_active() already
        # tolerates by dropping ids that no longer resolve via get().
        try:
            raw = self._redis.get(_key(session_id))
            if raw:
                user_id = json.loads(raw).get("user_id")
                if user_id:
                    self._redis.srem(_active_key(user_id), session_id)
        except Exception as e:
            logger.warning("delete: active-set cleanup failed  session_id=%s  error=%s", session_id, e)

        try:
            deleted = self._redis.delete(_key(session_id))
            if deleted > 0:
                logger.info("DEL   session_id=%s  key_existed=True", session_id)
            else:
                logger.info("DEL   session_id=%s  key_existed=False (already gone)", session_id)
            return deleted > 0
        except Exception as e:
            logger.error("delete failed  session_id=%s  error=%s", session_id, e)
            return False

    def list_active(self, user_id: str) -> list[TripSession]:
        """
        Lists this user's in-progress (Redis-only) sessions, for GET /chats
        with status=active. Backed by a per-user Redis SET maintained
        alongside create/delete — Redis has no native secondary index by
        user_id, so this is maintained by hand rather than scanned for.

        Self-healing: any session_id in the set that no longer resolves
        (expired TTL, or the raw data is corrupt) is dropped from the set
        here rather than left to accumulate.
        """
        try:
            ids = self._redis.smembers(_active_key(user_id))
        except Exception as e:
            logger.error("list_active failed  user_id=%s  error=%s", user_id, e)
            return []

        sessions: list[TripSession] = []
        stale:    list[str] = []
        for session_id in ids:
            session = self.get(session_id)
            if session is None:
                stale.append(session_id)
            else:
                sessions.append(session)

        if stale:
            try:
                self._redis.srem(_active_key(user_id), *stale)
            except Exception as e:
                logger.warning("list_active: stale cleanup failed  user_id=%s  error=%s", user_id, e)

        return sessions

    def exists(self, session_id: str) -> bool:
        try:
            found = self._redis.exists(_key(session_id)) > 0
            logger.debug("EXISTS session_id=%s  found=%s", session_id, found)
            return found
        except Exception as e:
            logger.error("exists failed  session_id=%s  error=%s", session_id, e)
            return False

    def get_or_create(self, session_id: Optional[str], user_id: str) -> tuple[TripSession, bool]:
        if session_id:
            # Deliberately NOT caught here. SessionStoreUnavailable must
            # propagate to the API layer so a Redis outage returns a clear
            # 503 instead of silently starting a new, context-free session.
            session = self.get(session_id)
            if session:
                logger.info("RESUME session_id=%s  user_id=%s", session_id, user_id)
                return session, False

        session = TripSession.new(user_id=user_id)
        if not self.save(session):
            # If we can't even persist a brand-new session, there's no
            # point burning a Groq call on a conversation that will evaporate
            # on the very next turn. Fail fast instead.
            raise SessionStoreUnavailable(
                f"Redis unreachable — could not create session for user_id={user_id}"
            )
        try:
            self._redis.sadd(_active_key(user_id), session.session_id)
        except Exception as e:
            # Best-effort — worst case this session just won't show up in
            # GET /chats?status=active until list_active's self-healing
            # logic is moot (there's nothing to self-heal without knowing
            # the id exists). The session itself is still fully usable.
            logger.warning(
                "get_or_create: active-set registration failed  session_id=%s  error=%s",
                session.session_id, e,
            )
        logger.info("CREATE session_id=%s  user_id=%s", session.session_id, user_id)
        return session, True

    def ttl(self, session_id: str) -> int:
        try:
            remaining = self._redis.ttl(_key(session_id))
            logger.debug("TTL   session_id=%s  remaining=%ds", session_id, remaining)
            return remaining
        except Exception:
            return -2

    def ping(self) -> bool:
        try:
            result = self._redis.ping()
            logger.debug("PING  reachable=%s", result)
            return result
        except Exception:
            logger.warning("PING  Redis unreachable")
            return False