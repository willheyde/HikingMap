# HikeBuilder — Frontend

The React 19 + Vite SPA for [HikeBuilder](../README.md): a Mapbox map for trail discovery plus the conversational AI trip-planner UI. It talks to the FastAPI backend in [`../pythonBackend`](../pythonBackend).

## Tech Stack

| Concern | Technology |
|---|---|
| Framework | React 19 + Vite 7 |
| Routing | React Router 7 |
| State | React Context (Hike, User, Item, Trip) |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Map | Mapbox GL (trails as GeoJSON overlays) |
| HTTP | Axios (`api/client.js`) |
| Lists | `react-window` (virtualized) |

## Getting Started

```bash
npm install
npm run dev        # Vite dev server on :5173
```

### Environment variables

Create `hiking-frontend/.env` (Vite exposes `import.meta.env`):

```env
VITE_MAPBOX_TOKEN=your_mapbox_token       # required — the map won't render without it
VITE_API_BASE_URL=http://localhost:8000   # defaults to http://localhost:8000
```

Get a Mapbox token at [account.mapbox.com](https://account.mapbox.com/). The backend must be running (see the [root README](../README.md)) for anything beyond the static map to work.

## Scripts

```bash
npm run dev        # dev server with HMR on :5173
npm run build      # production build → dist/
npm run preview    # serve the production build locally
npm run lint       # eslint (flat config in eslint.config.js)
```

## Project Structure

```
src/
├── pages/       # Page-level views: MapPage, HikeDetailPage, TripPlanner,
│                #   GearManager, GearOnboarding, Profile
├── components/  # Reusable UI
├── context/     # React Context state + hooks (Hike, User, Item, Trip)
└── api/         # Axios client + per-resource service modules
```

### Routing

Routes are declared in `App.jsx`: `/map`, `/hike/:hikeId`, `/profile`, `/gear`, `/onboarding`, `/trip-planner`.

### API client

All API calls go through `api/client.js`, an Axios instance that injects the `hike_token` bearer from `localStorage` on every request and hard-redirects to `/` on any `401` (except the login route). Per-resource wrappers live alongside it (`hikesService.js`, `usersService.js`, `itemsService.js`, `tripService.js`).

## License

MIT
