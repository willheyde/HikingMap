# HikeBuilder

A full-stack hiking discovery application that lets users find, filter, and explore trails on an interactive map. Trail data is sourced from OpenStreetMap and enriched with elevation profiles and surface metrics via a custom geospatial processing pipeline.



<img width="931" height="525" alt="Screenshot 2026-05-09 210905" src="https://github.com/user-attachments/assets/872385d6-9152-4cf0-8ad7-fa4e1a715654" />

<img width="910" height="514" alt="Screenshot 2026-05-09 210939" src="https://github.com/user-attachments/assets/17d6ad01-0a62-402f-bb13-1f59c07a2268" />

---

## Features

- **Interactive Map** — Browse trails rendered as GeoJSON overlays on a Mapbox map
- **Smart Filtering** — Filter by state, difficulty, trail length, search radius, and best hiking month
- **Gear Matching** — Flag trails based on whether you own the required gear
- **Elevation Profiles** — Each trail includes vertical gain computed from SRTM elevation data
- **Recommended Hikes** — Highlighted trails based on filter criteria

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, component-based architecture |
| Backend | Python, Uvicorn (ASGI) |
| Database | PostgreSQL (Docker), pgAdmin 4 |
| Data Processing | Osmium (OSM parsing), Geopy, SRTM elevation data |
| Architecture | Controllers → Services → Repositories → Models |
| Dev Server | `npm run dev` (frontend), `uvicorn` (backend) |

---

## Architecture

The backend follows a layered architecture pattern:

```
/backend
├── models/         # Data models / schemas
├── controllers/    # Route handlers
├── services/       # Business logic
├── repositories/   # Database queries (PostgreSQL)
└── main.py         # App entry point (Uvicorn)

/frontend
├── components/     # Reusable UI components
├── pages/          # Page-level views
└── ...
```

The Python processing pipeline is separate from the web server — it parses raw OSM XML files, stitches trail segments into complete routes, computes geodesic distances and elevation gain, and persists the results to PostgreSQL.

---

## Data Pipeline

Trail data was sourced from [OpenStreetMap](https://www.openstreetmap.org/) and processed as follows:

1. **OSM Parsing** — Raw `.osm` XML files are parsed with [Osmium](https://osmcode.org/osmium-tool/) to extract trail way geometries
2. **Segment Stitching** — Disconnected trail segments sharing nodes are combined into complete route geometries
3. **Elevation Enrichment** — SRTM elevation data is overlaid on trail coordinates; vertical gain is computed per route
4. **Distance Calculation** — Geodesic distances are computed using [Geopy](https://geopy.readthedocs.io/)
5. **GeoJSON Export** — Processed trails are stored in PostgreSQL and served as optimized GeoJSON payloads to the frontend

**Proof of concept:** Rhode Island was used as the initial dataset due to its small geographic footprint and manageable trail count.

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) (for PostgreSQL)
- Python 3.10+
- Node.js 18+

### 1. Start the Database

```bash
docker compose up -d
```

This starts a PostgreSQL instance on port `5432`. You can manage it via pgAdmin 4.

### 2. Configure Environment Variables

Create a `.env` file in `/backend`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=HikingAppDB
DB_USER=your_user
DB_PASSWORD=your_password
```

### 3. Run the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 4. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Current Limitations & Future Work

- **Dataset** — Currently scoped to Rhode Island trails. Expanding to additional states requires re-running the OSM pipeline per state.
- **Hosting** — The app runs locally only; no public deployment yet.
- **Gear System** — The gear-matching feature is functional but the gear inventory management UI is minimal.
- **Auth** — Basic authentication exists but user account features are limited.

---

## What I'd Improve

- Automate the OSM pipeline to support any U.S. state on demand
- Add trail route rendering (draw the path on the map, not just a pin)
- Improve the gear recommendation engine with user history
- Deploy the backend to a cloud provider and host the DB externally rather than locally via Docker

---

## License

MIT
