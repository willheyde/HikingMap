"""
rate_limit.py

Redis-backed fixed-window rate limiting + per-account AI usage quota. Reuses the
same Redis the chat sessions already run on (REDIS_URL). All limits are
env-tunable; the defaults are sized for a small soft launch.

Two things live here:

  • AI usage quota (cost control) — a per-account budget of trip-chat messages
    per window, sized for ~1-2 full trip-planning sessions. Enforced on the AI
    chat endpoint via the `ai_quota_guard` dependency (which also returns the
    authenticated user_id, so it slots in where get_current_user_id was used).

  • Brute-force / abuse limiting — a short-window per-IP cap on the auth
    endpoints (`auth_rate_limit`) and a short-window per-account burst cap on
    the AI endpoint (rolled into `ai_quota_guard`).

Fails OPEN: any Redis error is logged and the request is allowed through, so a
cache blip never hard-blocks legitimate traffic. (A true Redis outage already
surfaces as a 503 from the session store on the AI path.)
"""

import logging
import os

import redis
from fastapi import Depends, HTTPException, Request

from Auth.authentication import get_current_user_id

logger = logging.getLogger(__name__)

# Lazy client (from_url does not connect until first use) — safe to build at
# import even if Redis is down.
_redis = redis.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Tunables (env-overridable) ────────────────────────────────────────────────
#
# AI quota: each chat message fans out to 2-4 Groq calls (chat + structured
# extraction + sometimes a refine second call), so a "message" is a coarse proxy
# for real cost. 20/24h keeps a lid on it while still covering a full planning
# session. Raise AI_QUOTA_LIMIT (or shorten AI_QUOTA_WINDOW_SEC) to loosen.
AI_QUOTA_LIMIT      = _env_int("AI_QUOTA_LIMIT", 20)          # messages per window
AI_QUOTA_WINDOW_SEC = _env_int("AI_QUOTA_WINDOW_SEC", 86400)  # 24h

# Burst: stops scripted rapid-fire within the daily budget. Humans never exceed
# this (each turn waits on a multi-second Groq response).
AI_BURST_LIMIT      = _env_int("AI_BURST_LIMIT", 6)
AI_BURST_WINDOW_SEC = _env_int("AI_BURST_WINDOW_SEC", 60)

# Auth: per-IP cap on login/registration to blunt credential stuffing.
AUTH_RATE_LIMIT      = _env_int("AUTH_RATE_LIMIT", 10)
AUTH_RATE_WINDOW_SEC = _env_int("AUTH_RATE_WINDOW_SEC", 300)  # 5 min

# Number of trusted reverse proxies in front of the app (ALB = 1; front it with
# CloudFront too → 2). Determines which X-Forwarded-For entry is the real
# client, and MUST match the real topology — see _client_ip.
TRUSTED_PROXY_HOPS = _env_int("TRUSTED_PROXY_HOPS", 1)


def _hit(key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """
    Fixed-window counter. Increments `key`, setting the window TTL on the first
    hit. Returns (allowed, retry_after_seconds). Fails OPEN (allowed=True) on any
    Redis error so a cache problem never blocks real traffic.
    """
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, window_s)
        if count > limit:
            ttl = _redis.ttl(key)
            return False, ttl if ttl and ttl > 0 else window_s
        return True, 0
    except Exception as e:
        logger.warning("rate_limit: Redis error on %s — failing open: %s", key, e)
        return True, 0


def _enforce(key: str, limit: int, window_s: int, detail: str) -> None:
    allowed, retry_after = _hit(key, limit, window_s)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


def _client_ip(request: Request) -> str:
    # X-Forwarded-For is client-controlled and each proxy *appends* to it, so the
    # LEFT-most entry is whatever the original caller sent — spoofable, and using
    # it lets an attacker rotate a fake IP to dodge the per-IP cap entirely. The
    # trustworthy value is the hop our own proxy chain added: counting
    # TRUSTED_PROXY_HOPS from the right yields the address the outermost trusted
    # proxy actually observed. Anything further left is attacker-influenced.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if len(hops) >= TRUSTED_PROXY_HOPS:
            return hops[-TRUSTED_PROXY_HOPS]
        # Fewer hops than expected (misconfigured proxy count or a direct hit) —
        # fall back to the socket peer rather than trusting a short client chain.
    return request.client.host if request.client else "unknown"


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def ai_quota_guard(request: Request, user_id: str = Depends(get_current_user_id)) -> str:
    """
    Gate the AI chat endpoint: a short-window burst cap then the per-account
    usage quota. Returns the authenticated user_id, so it can replace
    Depends(get_current_user_id) directly on the route. Each accepted call counts
    one message against the quota.
    """
    _enforce(
        f"rl:ai:burst:{user_id}", AI_BURST_LIMIT, AI_BURST_WINDOW_SEC,
        "You're sending messages too quickly — give it a few seconds.",
    )
    _enforce(
        f"rl:ai:quota:{user_id}", AI_QUOTA_LIMIT, AI_QUOTA_WINDOW_SEC,
        f"You've hit your AI planning limit for now (about {AI_QUOTA_LIMIT} messages). "
        "It resets soon, and your saved trips are unaffected.",
    )
    return user_id


def auth_rate_limit(request: Request) -> None:
    """Per-IP cap for login / registration to slow brute-force attempts."""
    _enforce(
        f"rl:auth:{_client_ip(request)}", AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_SEC,
        "Too many attempts. Please wait a few minutes and try again.",
    )
