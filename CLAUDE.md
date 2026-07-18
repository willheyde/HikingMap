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
pip install -r requirements.txt    # pinned runtime deps
uvicorn main:app --reload          # dev: serves on :8000 (frontend + tests assume this port)
docker compose up -d               # local PostgreSQL on :5432 (creds via env — see .env)
docker build -t hikebuilder-api .  # prod image: single uvicorn worker, no --reload (see Dockerfile)
```
Deps are pinned in `requirements.txt` (fastapi, uvicorn, psycopg[binary], psycopg-pool, pydantic[email], python-dotenv, apscheduler, groq, redis, python-jose[cryptography], bcrypt, httpx, google-auth; the ingestion pipeline adds `requests`/`geopy`). Redis must be reachable (`REDIS_URL`) or the trip-chat endpoints return 503.

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

- **`UnitTest.py`** — deterministic unit tests for the bug-prone **pure** logic, needing **no server / DB / Redis / Groq / HTTP**: NL distance/difficulty parsing precedence, phase-transition signal banks, hike-selection parser, tag scoring/concept expansion, gear-adequacy levels, and the signal-token strip patterns. Reuses `_testkit.Suite` for the same exit-code contract.
  ```bash
  python UnitTest.py
  ```

**CI** (`.github/workflows/ci.yml`, runs on every push + PR): a **backend** job (installs `requirements.txt`, byte-compiles, runs `UnitTest.py`, then boots the app against throwaway Postgres+Redis service containers and runs `IntegrationTest.py --register`) and a **frontend** job (`npm ci` → lint → build). `SystemTest.py` is deliberately **not** in CI — it spends Groq quota.

### Database migrations
Numbered SQL files in `pythonBackend/migrations/` (currently through `010_scrub_future_trails.sql`), applied by the `migrate.py` runner, which tracks applied versions in a `schema_migrations` table:
```bash
python migrate.py status     # applied vs pending
python migrate.py up         # apply pending migrations
python migrate.py baseline   # stamp all current .sql as applied WITHOUT running them
```
`schema.sql` is the full from-scratch schema for a brand-new empty DB (CI applies it, then `migrate.py up`). **Adopting the runner on a DB already hand-migrated: run `baseline` ONCE first** — otherwise `up` re-runs non-idempotent early migrations (e.g. 001's `ADD CONSTRAINT`) and errors. `.py` data migrations (e.g. `004_purge_legacy_gear.py`) are **not** run by the tool — run them separately.

## Environment variables

Backend reads a `pythonBackend/.env` (via `python-dotenv` with `override=True`, so `.env` wins over exported vars — resolved relative to the source file, not the CWD; on AWS there's no `.env`, so injected env vars are used as-is). Required keys:
- DB (psycopg): `HOST`, `PORT`, `DBNAME`, `PASSWORD`, and `DB_USER` (preferred) or `USER` — `DBConnection` reads `DB_USER` first so injected credentials never collide with the shell's `USER`.
- `HikeKey` — Groq API key (`GroqClient` reads `os.environ["HikeKey"]`).
- `REDIS_URL` — defaults to `redis://localhost:6379/0`.
- `JWT_SECRET_KEY` — HS256 signing key for auth.
- `GOOGLE_CLIENT_ID` — verifies "Sign in with Google" ID tokens (`UserController`).
- Prod hardening (env-tunable): `APP_ENV=production` + `ALLOWED_ORIGINS` (CORS — the app **refuses to boot** in production on an unset/localhost origin), `ENABLE_HSTS=true`, `MAX_BODY_BYTES`, `TRUSTED_PROXY_HOPS`, `DB_POOL_MIN`/`DB_POOL_MAX`.

Frontend (Vite, `import.meta.env`): `VITE_MAPBOX_TOKEN` (required for the map to render), `VITE_API_BASE_URL` (defaults to `http://localhost:8000`).

## Backend architecture

Layered, wired up in `main.py`:

**Controller → Service → Repo → PyObject**
- `Controllers/` — FastAPI routers; Pydantic request/response schemas are defined **inline** in each controller (not in `Schemas/`, which only holds a few). Controllers instantiate their own service+repo as module-level singletons.
- `Services/` — business logic.
- `Repos/` — raw SQL via `psycopg` v3. All DB access goes through `DBConnection.get_connection()`, a context manager that yields a `dict_row` connection and commits/rolls-back automatically. `Repos/RepositoryBase.py` defines the abstract CRUD interface.
- `PyObjects/` — domain models (`Hike`, `User`, `Trip`, `Item`) with `to_dict`/`from_dict`.

**Note:** all routers are wired in `main.py` from `Controllers/` — there is no separate `Routers/` package (the old legacy `Routers/UserRouter.py` has been deleted). Each controller instantiates its own service+repo as module-level singletons.

Auth: JWT bearer tokens. `Auth/authentication.py` exposes `get_current_user_id` (gate any protected route) and `get_current_admin` (admin-only — reads `users.is_admin` live from the DB, so a demotion takes effect immediately). Passwords hashed with bcrypt. **Catalog writes are gated:** hike create/update/delete are **admin-only**; item writes require **any authenticated user** (items are user-customizable); reads on both stay public.

`main.py` also starts an APScheduler background job (every 6h) that flips `trips.needs_review` for trips completed more than `NEEDS_REVIEW_AFTER_DAYS` ago.

## AI trip-planner (`pythonBackend/AI/`)

This is the most intricate part of the codebase. `AI/TripChat.py` (~2300 lines) is a single FastAPI router mounted at `/api/trip` that orchestrates the whole conversation. Read its module docstring (steps 1–12) before changing it.

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
