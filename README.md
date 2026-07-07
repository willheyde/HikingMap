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

Apply the SQL migrations in `pythonBackend/migrations/` (they are applied by hand — there is no migration runner yet).

### 2. Configure Environment Variables

Create `pythonBackend/.env`:

```env
# PostgreSQL (psycopg)
HOST=localhost
PORT=5432
DBNAME=HikingAppDB
USER=your_db_user
PASSWORD=your_db_password

# Services
HikeKey=your_groq_api_key
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your_hs256_signing_key
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
# No requirements.txt yet — install runtime deps by hand:
pip install fastapi uvicorn "psycopg[binary]" pydantic python-dotenv apscheduler groq redis "python-jose[cryptography]" bcrypt httpx
# (the ingestion pipeline additionally needs: requests geopy)
uvicorn main:app --reload     # serves on :8000
```

### 4. Run the Frontend

```bash
cd hiking-frontend
npm install
npm run dev                   # Vite dev server on :5173
```

---

## Roadmap — Working Toward Deployment

The current focus is getting HikeBuilder onto **AWS** as a public soft launch. Tracked work, roughly in order:

**Deployment blockers**
- [ ] Pin dependencies (`requirements.txt` / Dockerfile) for reproducible builds
- [ ] Connection pooling for PostgreSQL (currently one connection per request)
- [ ] Environment-driven CORS (currently hard-coded to localhost)
- [ ] Move secrets to AWS Secrets Manager / SSM; harden the `USER` env resolution
- [ ] A migration runner (migrations are applied by hand today)

**Before public**
- [ ] Rate limiting (auth + AI endpoints)
- [ ] AI usage controls — per-account quota to cap cost/abuse (keep the capable model, cap volume)
- [ ] Offload blocking LLM / geocoding calls off the async request path

**Known data-quality issues (ingestion)**
- [ ] Lake tag applied as a default, producing false "lake" tags on trails without one
- [ ] Some out-and-back trails record only the one-way distance (elevation gain is correct)

**Product**
- [ ] Expand beyond Rhode Island (parameterize the ingestion bounding box)
- [ ] Richer gear recommendations informed by trip history

---

## License

MIT
