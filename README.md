# HikeBuilder

> An AI-assisted hiking trip planner that turns a plain-language request ("I want a moderate day hike near Asheville with waterfalls") into a ranked list of real trails and a structured, gear-aware itinerary.

HikeBuilder pairs a conversational LLM layer with a real trail dataset ingested from OpenStreetMap. Instead of hallucinating trails, the assistant grounds every recommendation in a Postgres-backed catalog of actual hikes, then walks the user through a guided four-phase planning conversation.

<!-- TODO: add a screenshot or short GIF of the chat flow here — recruiters skim, and a visual sells the project fast. -->

---

## Why this exists

Most "AI trip planner" demos are a thin wrapper around a single prompt: they ask the model for hikes and print whatever it invents. That breaks the moment a user wants something real — the trails don't exist, the difficulty is wrong, or the "waterfall hike" has no water.

HikeBuilder takes the opposite approach. The LLM is used for what it's good at (understanding intent, holding a conversation, summarizing) while the actual trail matching runs against a real, enriched dataset with a deterministic ranking layer. The result is a system where recommendations are traceable back to source data.

---

## Features

- **Conversational, phase-driven planning.** A `PhaseController` state machine moves each conversation through four phases — `destination → gear_review → itinerary → finalize` — and is hardened against the LLM and backend drifting out of sync.
- **Grounded trail search.** `HikeSearchService` matches user intent against a real OSM-derived catalog using a graduated soft-ranking algorithm rather than brittle exact-match filters, so near-misses still surface sensibly.
- **Two-pass fallback search.** When a strict query returns too few results, a second pass widens the net using `TAG_FALLBACKS`, so users rarely hit an empty screen.
- **Dynamic LLM budgeting.** `_resolve_groq_params()` allocates token budgets per request based on the conversation phase, keeping short exchanges cheap and complex itinerary generation adequately sized.
- **Real data ingestion pipeline.** Trails are pulled from OpenStreetMap via Overpass, deduplicated, and enriched with human-readable characterizations before they ever reach a user.

---

## Architecture

HikeBuilder is a multi-service application:

```
┌─────────────┐      ┌──────────────────────────────┐      ┌────────────┐
│   React     │◄────►│         FastAPI backend        │◄────►│ PostgreSQL │
│  frontend   │ HTTP │                                │      │  (trails)  │
└─────────────┘      │  • PhaseController (state)     │      └────────────┘
                     │  • HikeSearchService (ranking) │      ┌────────────┐
                     │  • HikeRepository (data access)│◄────►│   Redis    │
                     │  • Groq/Llama client           │      │  (cache)   │
                     └───────────────┬────────────────┘      └────────────┘
                                     │
                                     ▼
                        ┌──────────────────────────┐
                        │   Groq / Llama LLM API    │
                        └──────────────────────────┘

        Offline: OSM ingestion pipeline → enriched trails → PostgreSQL
```

**Backend** — FastAPI orchestrates the conversation, calls the Groq/Llama API for language tasks, and delegates all trail lookups to the data layer.

**Data layer** — `HikeRepository` owns database access; `HikeSearchService` sits on top of it and handles ranking and fallbacks. PostgreSQL stores the trail catalog; Redis provides caching.

**LLM layer** — Groq-hosted Llama models handle intent parsing, conversation, and itinerary summarization. Token budgets are resolved dynamically per phase.

**Frontend** — A React single-page app drives the chat experience and renders results.

---

## Tech stack

| Layer        | Technology                                  |
| ------------ | ------------------------------------------- |
| Frontend     | React                                       |
| Backend      | FastAPI (Python)                            |
| Database     | PostgreSQL                                  |
| Cache        | Redis                                       |
| LLM          | Groq API (Llama models)                     |
| Data source  | OpenStreetMap via Overpass API              |

---

## Getting started

> **TODO:** These steps reflect the standard shape of the stack. Replace the placeholder commands, ports, and env var names with your actual project values before publishing.

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- A Groq API key

### 1. Clone and configure

```bash
git clone https://github.com/<your-username>/hikebuilder.git   # TODO: real repo URL
cd hikebuilder
cp .env.example .env                                            # TODO: confirm this file exists
```

### 2. Environment variables

Set these in `.env` (names are illustrative — align with your config):

```env
DATABASE_URL=postgresql://user:password@localhost:5432/hikebuilder
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.x-...        # TODO: the model string you actually use
```

### 3. Start dependencies

```bash
# TODO: if you have a docker-compose.yml, document `docker compose up` instead
# Otherwise ensure local PostgreSQL and Redis are running.
```

### 4. Backend

```bash
cd backend                      # TODO: adjust to your directory layout
pip install -r requirements.txt
# run migrations / create schema — TODO: your actual command
uvicorn app.main:app --reload   # TODO: confirm the module path
```

### 5. Ingest trail data

Populate the catalog before first use (see the pipeline section below):

```bash
# TODO: your ingestion entrypoint, e.g.
python -m ingestion.run --region "<bounding box or place>"
```

### 6. Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open the app at `http://localhost:<port>`.  <!-- TODO: real port -->

---

## Data ingestion pipeline

Trail data is not hand-curated — it's ingested and enriched from OpenStreetMap so the catalog can scale to new regions:

1. **`overpass_enrichment.py`** — queries the Overpass API and pulls raw trail geometry and tags for a target region.
2. **`merge_duplicates.py`** — collapses duplicate and fragmented trail records into single canonical entries.
3. **`characterizations.py`** — derives human-readable attributes (difficulty, features, terrain) that the search and ranking layers use.

The output is a clean, enriched set of trails written to PostgreSQL, ready for `HikeSearchService` to rank against.

---

## How the conversation works

The `PhaseController` is the backbone of the user experience. Each conversation advances through four phases, and the controller keeps the LLM's view of the world and the backend's actual state aligned:

1. **`destination`** — understand where and what kind of hike the user wants; run grounded search.
2. **`gear_review`** — surface relevant gear considerations for the selected trail(s).
3. **`itinerary`** — assemble a structured plan.
4. **`finalize`** — confirm and present the completed itinerary.

Because the LLM can wander, the controller treats model output as a proposal to be validated against real state rather than as ground truth — a design choice that keeps the assistant from confidently finalizing a plan the backend never actually built.

---

## Project structure

> **TODO:** Replace with your real tree (`tree -L 2` output is ideal). This is a representative sketch.

```
hikebuilder/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── phase_controller.py        # four-phase state machine
│   │   ├── services/
│   │   │   └── hike_search_service.py # soft-ranking + fallback search
│   │   ├── repositories/
│   │   │   └── hike_repository.py     # data access
│   │   └── llm/                       # Groq/Llama client, param resolution
│   ├── ingestion/
│   │   ├── overpass_enrichment.py
│   │   ├── merge_duplicates.py
│   │   └── characterizations.py
│   └── requirements.txt
├── frontend/
│   └── src/
└── README.md
```

---

## Roadmap

<!-- TODO: prune or expand to match your actual plans -->

- [ ] Map-based trail visualization in the frontend
- [ ] User accounts and saved itineraries
- [ ] Multi-day trip support
- [ ] Broader regional coverage in the ingestion pipeline
- [ ] Automated tests around the PhaseController state transitions

---

## License

<!-- TODO: pick one (MIT is a common default for portfolio projects) and add a LICENSE file. -->

---

*Built by Will — a portfolio project exploring grounded LLM applications, real-world data pipelines, and multi-service architecture.*  <!-- TODO: personalize / add contact or portfolio link -->
