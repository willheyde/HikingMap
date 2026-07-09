# main.py
from dotenv import load_dotenv
load_dotenv(override=True)   # .env is authoritative locally; no-op on AWS (no file)
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from Controllers.HikeController import router as hike_router
from Controllers.UserController import router as user_router
from Controllers.TripController import router as trip_router
from Controllers.ItemController import router as item_router
from AI.TripChat import router as trip_chat_router
from Repos.TripRepo import TripRepository
from DBConnection import close_pool, get_connection
import redis
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Background job: needs_review nudge ─────────────────────────────────────
#
# Flips trips.needs_review for anything 'completed' more than N days ago
# (anchored off completed_at, set by "Mark as done" — not planned_date,
# which nothing in the AI flow ever populates today). Drives a dismissible
# banner client-side; never gates or blocks anything. APScheduler was
# already an installed, unused dependency — this is its first real use.
NEEDS_REVIEW_AFTER_DAYS = 2
_scheduler = BackgroundScheduler()


def _run_needs_review_check() -> None:
    try:
        flipped = TripRepository().flip_needs_review(days=NEEDS_REVIEW_AFTER_DAYS)
        if flipped:
            logger.info("needs_review job: flagged %d trip(s) for review.", flipped)
    except Exception as e:
        logger.error("needs_review job failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once immediately on startup too (APScheduler's default for a
    # fresh interval trigger) — harmless and arguably useful: it catches
    # anything that should've flipped while the server was down, and the
    # UPDATE is a cheap no-op once nothing new qualifies.
    _scheduler.add_job(_run_needs_review_check, "interval", hours=6, id="needs_review_check")
    _scheduler.start()
    logger.info("APScheduler started — needs_review check runs every 6h.")
    yield
    _scheduler.shutdown()
    close_pool()   # release pooled DB connections on graceful shutdown


app = FastAPI(title="Hiking App API", lifespan=lifespan)

# ── Request body size cap ──────────────────────────────────────────────────
# Neither uvicorn nor an ALB caps request body size by default, so without this
# a single client could stream a multi-hundred-MB body and exhaust memory. Every
# legitimate request here (login, profile update, chat turn, trip save) is a few
# KB at most; 1 MB is a generous ceiling. Env-tunable via MAX_BODY_BYTES.
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(1 * 1024 * 1024)))


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
    return await call_next(request)

# Allowed CORS origins are env-driven so the same code serves local dev and a
# deployed frontend. Set ALLOWED_ORIGINS to a comma-separated list in prod
# (e.g. "https://hikebuilder.app"); it DEFAULTS to the local Vite origins, so
# unset (local dev) keeps working without any configuration.
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_origins_raw = os.getenv("ALLOWED_ORIGINS")
_allowed_origins = [
    o.strip() for o in (_origins_raw or _DEFAULT_ORIGINS).split(",") if o.strip()
]

# Fail loud on a misconfigured production deploy. With allow_credentials=True an
# unset ALLOWED_ORIGINS silently falls back to localhost, and the real frontend's
# requests get rejected by CORS with nothing obvious in the server logs. When
# APP_ENV marks a production deploy we instead refuse to start unless the var is
# set to real (non-localhost) origins, so the mistake surfaces at boot rather
# than as a browser console error. (JWT_SECRET_KEY already fails this way via
# os.environ[...].)
_is_production = os.getenv("APP_ENV", "").strip().lower() in {"production", "prod"}
_has_localhost = any(("localhost" in o) or ("127.0.0.1" in o) for o in _allowed_origins)
if _is_production and (not _origins_raw or _has_localhost):
    raise RuntimeError(
        f"ALLOWED_ORIGINS must be set to the deployed frontend origin(s) when "
        f"APP_ENV=production (got {_origins_raw!r}). Refusing to start with a "
        f"localhost CORS default in production."
    )
if not _origins_raw:
    logger.warning(
        "ALLOWED_ORIGINS is unset — defaulting to local dev origins %s. "
        "Set ALLOWED_ORIGINS in any deployed environment.", _allowed_origins,
    )
logger.info("CORS allowed origins: %s", _allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security response headers ──────────────────────────────────────────────
# Defense-in-depth headers on every API response. These are cheap and cannot
# break a JSON API. Note the SPA's Content-Security-Policy is deliberately NOT
# set here: a CSP only protects the document that carries it, and this API never
# serves the HTML — the SPA is static-hosted (CloudFront / S3). The CSP that
# mitigates the localStorage-token XSS concern must be set on that static host,
# and must allow-list Mapbox + Google Sign-In + Google Fonts. See SECURITY_NOTES.md.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # HSTS only makes sense once served over HTTPS end-to-end; gate it so local
    # HTTP dev is unaffected. Enable in prod (ENABLE_HSTS=true) behind the ALB.
    if os.getenv("ENABLE_HSTS", "").strip().lower() in {"1", "true", "yes"}:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


app.include_router(hike_router, prefix="/hikes", tags=["Hikes"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(trip_router, prefix="/trips", tags=["Trips"])
app.include_router(item_router, prefix="/items", tags=["Items"])
app.include_router(trip_chat_router)
@app.get("/")
def read_root():
    return {"message": "Hiking App API is running"}


# ── Health checks ──────────────────────────────────────────────────────────
# Two levels, on purpose:
#
#   /health        liveness — is the process up and serving? No dependency
#                  checks, so it never flaps when the DB/Redis hiccup. This is
#                  the safe target for an ALB target-group health check: keying
#                  the ALB off DB reachability risks a cascade (DB blips → every
#                  instance fails health → ALB has nothing to route to).
#
#   /health/ready  readiness — actually pings Postgres and Redis and reports
#                  each. Returns 503 if either is down. Point deploy smoke tests
#                  and deeper monitoring/alerting at this one; use it as the ALB
#                  check only if you deliberately want DB-down to drain traffic.
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    checks: dict[str, str] = {}

    # Postgres: a trivial round-trip through the same pool the app uses.
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        checks["database"] = "ok"
    except Exception as e:
        logger.warning("health/ready: database check failed: %s", e)
        checks["database"] = "error"

    # Redis: short-timeout ping so a hung Redis can't hang the health check.
    try:
        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning("health/ready: redis check failed: %s", e)
        checks["redis"] = "error"

    healthy = all(v == "ok" for v in checks.values())
    body = {"status": "ok" if healthy else "degraded", "checks": checks}
    if not healthy:
        return JSONResponse(status_code=503, content=body)
    return body

