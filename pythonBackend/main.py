# main.py
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from Controllers.HikeController import router as hike_router
from Controllers.UserController import router as user_router
from Controllers.TripController import router as trip_router
from Controllers.ItemController import router as item_router
from AI.TripChat import router as trip_chat_router
from Repos.TripRepo import TripRepository
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


app = FastAPI(title="Hiking App API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hike_router, prefix="/hikes", tags=["Hikes"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(trip_router, prefix="/trips", tags=["Trips"])
app.include_router(item_router, prefix="/items", tags=["Items"])
app.include_router(trip_chat_router)
@app.get("/")
def read_root():
    return {"message": "Hiking App API is running"}

