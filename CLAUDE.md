# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HikeBuilder is a full-stack hiking discovery + AI trip-planning app. Two independently-run pieces:

- `pythonBackend/` — FastAPI (ASGI) API, PostgreSQL, Redis, and a Groq-backed conversational trip planner.
- `hiking-frontend/` — React 19 + Vite SPA rendering trails on a Mapbox map.

There is also a standalone geospatial ingestion pipeline (`pythonBackend/ingestion/`) that is *not* part of the web server — it seeds the trail data.

## Commands

### Frontend (`hiking-frontend/`)
```bash
npm install
npm run dev        # Vite dev server on :5173
npm run build      # production build
npm run lint       # eslint (flat config in eslint.config.js)
```

### Backend (`pythonBackend/`)
```bash
uvicorn main:app --reload      # serves on :8000 (frontend + tests assume this port)
docker compose up -d           # PostgreSQL 15 on :5432
```
There is **no `requirements.txt`** — install deps by hand. Runtime imports: `fastapi uvicorn psycopg[binary] pydantic python-dotenv apscheduler groq redis python-jose[cryptography] bcrypt`. The ingestion pipeline additionally needs `requests`/`geopy`. Redis must be reachable (`REDIS_URL`) or the trip-chat endpoints return 503.

### Tests
Two HTTP integration runners, both hit a **running** server, both plain `requests` (no pytest). Shared harness in `_testkit.py` (Client + a PASS/FAIL/SKIP `Suite` with an exit code: 0 = no failures, 1 = a failure — CI-ready). The guiding rule: assert the **contract** (status codes, JSON shape, documented invariants), never LLM content quality.

- **`IntegrationTest.py`** — the non-Groq surface, so it's **unlimited / CI-safe** (no AI quota spent): health/readiness, security headers, hike reads + the difficulty search filter, a self-cleaning item CRUD cycle, auth gates (incl. `/api/trip/chat` 401ing *before* Groq), and the body-size cap. Run it on every push.
  ```bash
  python IntegrationTest.py --base-url http://localhost:8000
  python IntegrationTest.py --register     # auto-provision + delete a temp user for the authed checks
  ```
- **`SystemTest.py`** — replays multi-turn trip-chat conversations against `/api/trip/chat` and asserts the contract per turn (shape, valid phase, stable session, and the **signal-token strip-before-return invariant**). This one **does** hit Groq, so it's the rate-limited path: on a free tier a 429 (quota/burst) or 502 (Groq error) is recorded as **SKIP** (not FAIL) and the run stops calling the LLM. Needs a live server + a valid JWT.
  ```bash
  python SystemTest.py --base-url http://localhost:8000 --token <JWT>
  python SystemTest.py --test 4                    # single conversation
  python SystemTest.py --conversations mine.json   # bring your own turns
  ```

There is no unit-test framework and no CI yet (the exit codes above make wiring one up trivial).

### Database migrations
Plain SQL files in `pythonBackend/migrations/`, applied by hand (no migration tool). `001_trips_lifecycle.sql`, `002_completion_review.sql`.

## Environment variables

Backend reads a `pythonBackend/.env` (via `python-dotenv`). Required keys:
- DB (psycopg): `HOST`, `PORT`, `DBNAME`, `USER`, `PASSWORD` — note `USER` collides with a shell-provided var on some systems; the `.env` value must win.
- `HikeKey` — Groq API key (`GroqClient` reads `os.environ["HikeKey"]`).
- `REDIS_URL` — defaults to `redis://localhost:6379/0`.
- `JWT_SECRET_KEY` — HS256 signing key for auth.

Frontend (Vite, `import.meta.env`): `VITE_MAPBOX_TOKEN` (required for the map to render), `VITE_API_BASE_URL` (defaults to `http://localhost:8000`).

## Backend architecture

Layered, wired up in `main.py`:

**Controller → Service → Repo → PyObject**
- `Controllers/` — FastAPI routers; Pydantic request/response schemas are defined **inline** in each controller (not in `Schemas/`, which only holds a few). Controllers instantiate their own service+repo as module-level singletons.
- `Services/` — business logic.
- `Repos/` — raw SQL via `psycopg` v3. All DB access goes through `DBConnection.get_connection()`, a context manager that yields a `dict_row` connection and commits/rolls-back automatically. `Repos/RepositoryBase.py` defines the abstract CRUD interface.
- `PyObjects/` — domain models (`Hike`, `User`, `Trip`, `Item`) with `to_dict`/`from_dict`.

**Gotcha:** `Routers/UserRouter.py` is legacy/unused — `main.py` wires `Controllers/UserController.py` instead. Prefer `Controllers/` when editing; confirm what `main.py` actually includes before touching a router.

Auth: JWT bearer tokens. `Auth/authentication.py` exposes `get_current_user_id` — the FastAPI dependency to gate any protected route. Passwords hashed with bcrypt.

`main.py` also starts an APScheduler background job (every 6h) that flips `trips.needs_review` for trips completed more than `NEEDS_REVIEW_AFTER_DAYS` ago.

## AI trip-planner (`pythonBackend/AI/`)

This is the most intricate part of the codebase. `AI/TripChat.py` (~1900 lines) is a single FastAPI router mounted at `/api/trip` that orchestrates the whole conversation. Read its module docstring (steps 1–12) before changing it.

Key concepts:
- **Phase state machine** (`TripSession.PHASES`): `destination → gear_review → itinerary → finalize`. `PhaseController` decides transitions.
- **Sessions live in Redis** (`SessionStore`, 2h TTL) while a chat is `active`. On save (`POST /api/trip/save`) the session is converted to Postgres `trips` rows and deleted from Redis. There is **no `chat_sessions` table** — `trips.status` (`active`→ Redis-only, then `saved`→`completed`→`reviewed`) is the lifecycle. `SessionStoreUnavailable` (Redis down) must propagate as a 503 and must **not** be swallowed into a silent new session.
- **LLM is Groq** (`GroqClient`): `llama-3.3-70b-versatile` for chat, `llama-3.1-8b-instant` for structured extraction. Per-phase token/temperature settings come from `PromptBuilder.PHASE_GROQ_PARAMS`.
- **Signal tokens**: Groq is prompted to emit literal tokens that Python detects and then **strips before returning to the frontend**: `DESTINATION RESET`, `GEAR ADD: <category>`, `ADVANCE_PHASE`, `SEARCH_REFINE`, `SAVE CONFIRMED`. Most have both a pre-response Python detector (belt) and a post-response token scan (suspenders). When adding logic here, preserve that strip-before-return invariant.
- **Hike search**: `HikeSearchService` bridges parsed intent → `HikeService`. Hard filter (columns + tag arrays) → soft rank in Python by preferred-tag count → `format_for_context()` serializes top-N into the system prompt. Has fallback search, concept expansion (e.g. "water feature" → river/lake/pond/…), and priority/champion tags.
- Structured hike options are returned as `hike_options` (cards) so the frontend renders selectable buttons; clicking option N sends the chat message `"N"`.

## Data ingestion pipeline (`pythonBackend/ingestion/`)

Separate from the web server. `run_ingestion.py` is the entry point: fetches hiking routes from the OpenStreetMap **Overpass API** for a hardcoded `BBOX` (currently Rhode Island), stitches relation geometry, parses/filters hikes, infers gear requirements (`GearInferenceEngine`), and seeds Postgres (`seeder.py`). Run it from **inside** `ingestion/` — it uses sibling imports and appends the parent dir to `sys.path`.

## Frontend structure (`hiking-frontend/src/`)

React Router routes in `App.jsx` (`/map`, `/hike/:hikeId`, `/profile`, `/gear`, `/onboarding`, `/trip-planner`). State via React Context (`context/` — Hike, User, Item, Trip). API calls go through `api/client.js`, an axios instance that injects the `hike_token` bearer from localStorage on every request and hard-redirects to `/` on any 401 (except the login route). Styling is Tailwind v4. Map is Mapbox GL; trails render as GeoJSON overlays.
