# HikeBuilder

A full-stack hiking app that pairs **trail discovery** on an interactive map with an **AI trip-planning assistant** that plans a trip end-to-end — picking a trail, checking it against the gear you actually own, and building a day-by-day itinerary. Trail data is sourced from OpenStreetMap and enriched with elevation, distance, and per-trail gear requirements via a custom geospatial pipeline.



<img width="931" height="525" alt="Screenshot 2026-05-09 210905" src="https://github.com/user-attachments/assets/872385d6-9152-4cf0-8ad7-fa4e1a715654" />

<img width="910" height="514" alt="Screenshot 2026-05-09 210939" src="https://github.com/user-attachments/assets/17d6ad01-0a62-402f-bb13-1f59c07a2268" />

---

## What's New

The app has grown from a trail-discovery map into a guided trip planner. Recent work:

- **🤖 AI Trip-Planning Assistant** — A conversational planner (Groq / Llama) that walks you through a trip in phases: `destination → gear review → itinerary → finalize`. It searches real trails from the database, discusses trade-offs, drafts a day-by-day itinerary grounded in the trail's real distance and elevation, and saves the finished plan.
- **🎒 Gear Adequacy System ("A+ model")** — Gear is no longer a flat catalog of products. Each trail derives its own **required capability levels** per category (e.g. footwear → `hiking_boot`, shelter → `4_season`, sleep → a temperature rating), and your kit is checked for *adequacy*, not just presence — "do you own boots good enough for **this** trail?", not merely "do you own shoes?".
- **✅ Trail Readiness Checklist** — Every trail and saved trip shows a live, per-category readiness view (✓ set / ✗ missing / ⚠ under-spec) computed against your current gear locker.
- **🗺️ Trip Lifecycle** — Plans move through `active → saved → completed → reviewed`, with a post-trip review flow and a "Past Hikes" summary. Active sessions live in Redis; saved trips persist to PostgreSQL.
- **🧰 Gear Locker** — A category-based gear manager and onboarding flow that captures what you own (and its capability level) instead of picking from a fixed product list.

---

## Features

- **Interactive Map** — Browse trails rendered as GeoJSON overlays on a Mapbox map
- **Smart Filtering** — Filter by state, difficulty, trail length, search radius, and best hiking month
- **AI Trip Planner** — Chat your way from "I want a weekend hike" to a saved, gear-checked itinerary
- **Gear Adequacy Matching** — Per-trail required gear *levels*, checked against your kit for adequacy
- **Elevation & Distance** — Each trail carries vertical gain and length computed from the source geometry
- **Naismith Time Estimates** — On-trail time estimated from a trail's real distance + gain

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, React Router, React Context, Tailwind v4, Mapbox GL |
| Backend | Python, FastAPI (ASGI) on Uvicorn |
| Database | PostgreSQL 15 (Docker) |
| Sessions / Cache | Redis (active chat sessions, 2h TTL) |
| AI | Groq — `llama-3.3-70b-versatile` (chat) + `llama-3.1-8b-instant` (structured extraction) |
| Auth | JWT (HS256) bearer tokens, bcrypt password hashing |
| Data Processing | OpenStreetMap Overpass API, geopy |
| Architecture | Controllers → Services → Repositories → PyObjects |

---

## Architecture

The backend follows a layered architecture. Full details in [`CLAUDE.md`](./CLAUDE.md).

```
/pythonBackend
├── Controllers/    # FastAPI routers + inline Pydantic schemas
├── Services/       # Business logic
├── Repos/          # Raw SQL via psycopg (all DB access through DBConnection)
├── PyObjects/      # Domain models (Hike, User, Trip, Item)
├── AI/             # Trip-chat orchestration, gear-gap analysis, prompt building
├── gear_levels.py  # Single source of truth for the gear capability vocabulary
├── ingestion/      # Standalone OSM ingestion pipeline (not part of the web server)
└── main.py         # App entry point (Uvicorn)

/hiking-frontend
├── src/pages/      # Page-level views (Map, HikeDetail, TripPlanner, GearManager, …)
├── src/components/ # Reusable UI
├── src/context/    # React Context state (Hike, User, Item, Trip)
└── src/api/        # Axios client + per-resource service modules
```

---

## Data Pipeline

The ingestion pipeline (`pythonBackend/ingestion/`) is **separate from the web server** — it seeds the trail data:

1. **Fetch** — Hiking routes are pulled from the OpenStreetMap [Overpass API](https://overpass-api.de/) for a configured bounding box (currently Rhode Island)
2. **Stitch** — Relation members are combined into complete route geometries
3. **Enrich** — Distance and elevation gain are computed; hikes are parsed, filtered, and tagged
4. **Infer Gear** — `GearInferenceEngine.infer_gear_levels()` derives each trail's required gear *levels* from its physical stats + tags (catalog-independent)
5. **Seed** — Processed trails + their gear requirements are persisted to PostgreSQL

**Proof of concept:** Rhode Island was used as the initial dataset due to its small footprint and manageable trail count.

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) (for PostgreSQL)
- [Redis](https://redis.io/) (for AI chat sessions)
- Python 3.10+
- Node.js 18+
- A [Groq API key](https://console.groq.com/) and a [Mapbox token](https://account.mapbox.com/)

### 1. Start the Database

```bash
cd pythonBackend
docker compose up -d          # PostgreSQL on :5432
```

Apply the schema and migrations. For a brand-new empty DB, `schema.sql` is the full from-scratch schema; the numbered files in `pythonBackend/migrations/` are applied by the `migrate.py` runner (which tracks applied versions in a `schema_migrations` table):

```bash
python migrate.py status     # applied vs pending
python migrate.py up         # apply pending migrations
python migrate.py baseline   # stamp existing .sql as applied WITHOUT running them (for a DB already hand-migrated)
```

### 2. Configure Environment Variables

Create `pythonBackend/.env`:

```env
# PostgreSQL (psycopg)
HOST=localhost
PORT=5432
DBNAME=HikingAppDB
DB_USER=your_db_user        # DB_USER is read first, so it never collides with the shell's USER
PASSWORD=your_db_password

# Services
HikeKey=your_groq_api_key
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your_hs256_signing_key

# Optional — rate limiting / AI usage quota (defaults shown; all env-tunable)
# AI_QUOTA_LIMIT=20          # AI chat messages per account per window
# AI_QUOTA_WINDOW_SEC=86400  # quota window (86400 = 24h; 18000 = 5h)
# AI_BURST_LIMIT=6           # per-account burst cap (messages per minute)
# AUTH_RATE_LIMIT=10         # login/registration attempts per IP per 5 min

# Optional — production hardening (see CLAUDE.md)
# APP_ENV=production         # refuses to boot on an unset/localhost ALLOWED_ORIGINS
# ALLOWED_ORIGINS=https://your.app
# ENABLE_HSTS=true
# GOOGLE_CLIENT_ID=...       # verifies "Sign in with Google" ID tokens
```

Create `hiking-frontend/.env`:

```env
VITE_MAPBOX_TOKEN=your_mapbox_token
VITE_API_BASE_URL=http://localhost:8000
```

> **Note:** on some systems `USER` collides with a shell-provided variable — the `.env` value must win.

### 3. Run the Backend

```bash
cd pythonBackend
pip install -r requirements.txt   # pinned runtime deps
uvicorn main:app --reload         # serves on :8000

# Or build the production image (single uvicorn worker, no --reload):
# docker build -t hikebuilder-api .
```

### 4. Run the Frontend

```bash
cd hiking-frontend
npm install
npm run dev                   # Vite dev server on :5173
```

---

## Tests

Three runners, all sharing a small harness (`_testkit.py`) with a CI-ready exit code (0 = pass, 1 = failure). They assert the **contract** (status codes, JSON shape, documented invariants), never LLM content quality.

```bash
python UnitTest.py                                   # pure logic — no server / DB / Redis / Groq
python IntegrationTest.py --register --base-url http://localhost:8000   # non-Groq HTTP surface (CI-safe)
python SystemTest.py --token <JWT> --base-url http://localhost:8000     # multi-turn trip-chat (spends Groq quota)
```

**CI** (`.github/workflows/ci.yml`, every push + PR): a backend job (install → byte-compile → `UnitTest.py` → boot against throwaway Postgres+Redis → `IntegrationTest.py --register`) and a frontend job (`npm ci` → lint → build). `SystemTest.py` is deliberately excluded from CI since it spends Groq quota.

---

## Roadmap — Working Toward Deployment

The current focus is getting HikeBuilder onto **AWS** as a public soft launch. Tracked work, roughly in order:

**Deployment blockers**
- [x] Pin dependencies (`requirements.txt`) for reproducible builds
- [x] Connection pooling for PostgreSQL (`psycopg_pool`, with a per-call fallback)
- [x] Environment-driven CORS (`ALLOWED_ORIGINS`, defaults to local)
- [x] Harden the `USER` env resolution (`DB_USER` preferred, `.env` override) — *secrets are now a deploy-time step; code is env-ready*
- [x] A migration runner (`migrate.py`: up / status / baseline)
- [x] Dockerfile (single uvicorn worker, prod-hardened boot)
- [ ] AWS deploy config (App Runner / ECS task definition)

**Before public**
- [x] Rate limiting (per-IP on auth, per-account burst on AI)
- [x] AI usage controls — per-account message quota to cap cost/abuse (keeps the capable model, caps volume)
- [x] Offload the blocking LLM + geocoding calls off the async request path

**Known data-quality issues (ingestion)**
- [ ] Lake tag applied as a default, producing false "lake" tags on trails without one
- [ ] Some out-and-back trails record only the one-way distance (elevation gain is correct)

**Product**
- [ ] Expand beyond Rhode Island (parameterize the ingestion bounding box)
- [ ] Richer gear recommendations informed by trip history

---

## License

MIT
