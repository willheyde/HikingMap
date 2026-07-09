import { useEffect, useState, useRef, useMemo, memo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import FilterBar from "../components/FilterBar";
import HikeSummaryCard from "../components/HikeSummaryCard";
import { HikeCardSkeletonList } from "../components/Skeleton";
import MapLegend from "../components/MapLegend";
import { useUserLocation } from "../components/UserLocation";
import { useHikes } from "../context/HikeContext";
import { palette as P } from "../styles/theme";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

/* ── Field Journal map palette (hikeStyle.md §5) ─────────────────────────────
   The base tiles come from Mapbox 'light-v11'; applyPaperBase() nudges its land
   + water toward aged paper. A true sepia/vintage tile set is a Mapbox Studio
   style (follow-up) — this is the in-code approximation. */
const MAP = {
  // Pinned to the rich ochre from before the UI-readability lightening —
  // the map keeps its deep parchment tone while the surrounding UI is lighter.
  land:     "#c6a46a",    // rich ochre landmass
  water:    P.water,      // flat tan "ocean" — same family, no blue
  trail:    P.ember,      // red route lines (the one accent hue)
  pin:      P.ember,      // red trail markers
  pinRing:  P.paper,      // cream stroke around pins
  cluster:  [P.ember, "#8e3022", "#7a2a1f"], // red cluster bubbles, darkening
  onEmber:  P.onEmber,    // cream text/stroke on red
};

/* Best-effort recolor of the light-v11 base layers toward paper. Each layer is
   guarded — Mapbox renames base layers between style versions, so a missing id
   is skipped rather than throwing. */
function applyPaperBase(m) {
  const setBG = (id, color) => {
    if (!m.getLayer(id)) return;
    try { m.setPaintProperty(id, "background-color", color); } catch { /* not a bg layer */ }
  };
  const setFill = (id, color) => {
    if (!m.getLayer(id)) return;
    try { m.setPaintProperty(id, "fill-color", color); } catch { /* not a fill layer */ }
  };
  setBG("background", MAP.land);
  ["land", "landcover", "landuse", "national-park", "park"].forEach((id) => setFill(id, MAP.land));
  ["water", "water-shadow"].forEach((id) => setFill(id, MAP.water));
}

/* ── Tuning constants ────────────────────────────────────────────────────── */
const RESULT_LIMIT  = 200;  // hard cap sent to backend; sidebar warns when hit
const CARD_HEIGHT   = 128;  // px – adjust if HikeSummaryCard renders taller/shorter
const MOVEEND_DELAY = 400;  // ms debounce on map pan / zoom end

/* ── Field Journal tokens (hikeStyle.md) — sidebar chrome ───────────────── */
const C = {
  page:        "#dccaa0", // canvas
  card:        "#ebe0c2", // paper
  cardBorder:  "#a2855a", // rule
  fieldBg:     "#ccb98f", // paper-sunk
  fieldBorder: "#a2855a", // rule
  heading:     "#3d2817", // ink
  subtext:     "#5c3a21", // ink-soft
  muted:       "#6a4a26", // ink-muted
  label:       "#a83b2c", // ember (accent)
  amber:       "#a83b2c", // ember
  amberDim:    "rgba(168,59,44,0.12)",
  amberBorder: "rgba(168,59,44,0.35)",
  amberText:   "#ebe0c2", // on-ember
  divider:     "#a2855a", // rule
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";

/* ── Mountain mark ───────────────────────────────────────────────────────── */
const MountainMark = () => (
  <svg width="28" height="22" viewBox="0 0 40 32" fill="none" style={{ flexShrink: 0 }}>
    <polygon points="20,2 38,30 2,30"  fill="none"    stroke="#a83b2c" strokeWidth="1.5" strokeLinejoin="round"/>
    <polygon points="10,30 20,12 30,30" fill="#e4cb9e" stroke="#5c3a21" strokeWidth="1"   strokeLinejoin="round"/>
  </svg>
);

/* ── [5] Dependency-free virtual list ───────────────────────────────────────
   Drop-in replacement for react-window's FixedSizeList.
   Only the rows currently visible in the scroll window are in the DOM.       */
const List = ({ height, itemCount, itemSize, itemData, width, children: Row }) => {
  const [range, setRange] = useState(() => ({
    start: 0,
    end: Math.min(itemCount - 1, Math.ceil(height / itemSize) + 1),
  }));

  if (!height || itemCount === 0) return null;

  const totalHeight = itemCount * itemSize;

  const handleScroll = (e) => {
    const scrollTop = e.currentTarget.scrollTop;
    const start = Math.max(0, Math.floor(scrollTop / itemSize) - 1);
    const end   = Math.min(itemCount - 1, Math.ceil((scrollTop + height) / itemSize) + 1);
    // Bail out of the state update if the visible row window hasn't moved —
    // this is what stops List (and every row) from re-rendering on every scroll pixel
    setRange(prev => (prev.start === start && prev.end === end) ? prev : { start, end });
  };

  // Clamp against the current itemCount: `range` is stored state and can lag a
  // frame behind a shrunken list, which would otherwise render rows off the end.
  const rows = [];
  const lastIndex = Math.min(range.end, itemCount - 1);
  for (let i = range.start; i <= lastIndex; i++) {
    rows.push(<Row key={i} index={i} top={i * itemSize} rowHeight={itemSize} data={itemData} />);
  }

  return (
    <div
      style={{
        height,
        width,
        overflowY:      "auto",
        position:       "relative",
        scrollbarWidth: "thin",
        scrollbarColor: `${C.cardBorder} transparent`,
      }}
      onScroll={handleScroll}
    >
      {/* Spacer div establishes the full scroll height */}
      <div style={{ height: totalHeight, position: "relative" }}>
        {rows}
      </div>
    </div>
  );
};

/* ── [5] Virtualised card row ────────────────────────────────────────────── */
const HikeRow = memo(function HikeRow({ index, top, rowHeight, data }) {
  const { hikes, onSelect } = data;
  const hike = hikes[index];
  // The List's visible range can briefly outrun `hikes` after a search returns
  // fewer results than were shown (range is only re-clamped on scroll), so an
  // index past the new end yields undefined — skip it rather than crash the card.
  if (!hike) return null;
  return (
    // box-sizing:border-box keeps padding inside the fixed height set by List
    <div style={{
      position: "absolute", top, left: 0, right: 0, height: rowHeight,
      boxSizing: "border-box", padding: "4px 12px",
    }}>
      <div
        onClick={() => onSelect(hike)}
        style={{
          cursor:       "pointer",
          background:   C.card,
          border:       `1px solid ${C.cardBorder}`,
          borderRadius: 12,
          overflow:     "hidden",
          height:       "100%",
          transition:   "border-color 0.15s, box-shadow 0.15s",
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = C.amber;
          e.currentTarget.style.boxShadow   = "0 4px 20px rgba(168,59,44,0.1)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = C.cardBorder;
          e.currentTarget.style.boxShadow   = "none";
        }}
      >
        <HikeSummaryCard hike={hike} />
      </div>
    </div>
  );
});

/* ── [1] Build two FeatureCollections from the hike array ───────────────── */
// Points drive the cluster layer; trails render the actual line geometry.
function buildGeoJSON(hikes) {
  const points = [];
  const trails = [];

  hikes.forEach((hike) => {
    if (!hike.geometry?.coordinates) return;

    if (hike.geometry.type === "LineString") {
      // Pin sits at the trailhead (first coordinate)
      points.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: hike.geometry.coordinates[0] },
        properties: { id: hike.id, name: hike.name ?? "" },
      });
      trails.push({
        type: "Feature",
        geometry: hike.geometry,
        properties: { id: hike.id },
      });
    } else if (hike.geometry.type === "MultiLineString") {
      // Trails stitched from multiple OSM segments come through as
      // MultiLineString (~16% of the table). The line layer renders these
      // natively; the pin sits at the first point of the first segment.
      points.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: hike.geometry.coordinates[0][0] },
        properties: { id: hike.id, name: hike.name ?? "" },
      });
      trails.push({
        type: "Feature",
        geometry: hike.geometry,
        properties: { id: hike.id },
      });
    } else if (hike.geometry.type === "Point") {
      points.push({
        type: "Feature",
        geometry: hike.geometry,
        properties: { id: hike.id, name: hike.name ?? "" },
      });
    }
  });

  return {
    pointsFC: { type: "FeatureCollection", features: points },
    trailsFC: { type: "FeatureCollection", features: trails },
  };
}

/* ── Radial "bloom" reveal ───────────────────────────────────────────────────
   Feeds features into the two WebGL sources over BLOOM_MS, ordered by distance
   from `center`, so trails open outward from the middle of the result cluster
   like a flower blooming. A growing radius threshold reveals both sources in
   lockstep (a hike's pin + line share the trailhead coord, so they appear
   together). Returns cancel(), which stops the animation and snaps both sources
   to their full data. Only ever runs on the first populated load — panning
   re-runs the search and must snap, not re-bloom, or it fights the camera. */
const BLOOM_MS = 900;
const easeInOutCubic = (t) =>
  (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

function bloomInSources(m, pointsFC, trailsFC, center) {
  // Re-fetched (not captured) + guarded so a mid-bloom unmount can't throw on a
  // torn-down style.
  const setFull = () => {
    try {
      m.getSource("hikes-source")?.setData(pointsFC);
      m.getSource("trails-source")?.setData(trailsFC);
    } catch { /* map removed mid-bloom */ }
  };

  const prefersReduced =
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (prefersReduced || pointsFC.features.length <= 1) {
    setFull();
    return () => {};
  }

  // Squared distance is enough for *ordering*; the cos(lat) term keeps the
  // reveal roughly circular rather than lng-stretched away from the equator.
  const cx = center.lng, cy = center.lat;
  const kx = Math.cos((cy * Math.PI) / 180) || 1;
  const head = (f) => {
    if (f.geometry.type === "LineString")      return f.geometry.coordinates[0];
    if (f.geometry.type === "MultiLineString") return f.geometry.coordinates[0][0];
    return f.geometry.coordinates; // Point
  };
  const dist2 = (f) => {
    const c = head(f);
    const dx = (c[0] - cx) * kx, dy = c[1] - cy;
    return dx * dx + dy * dy;
  };

  const pts  = pointsFC.features.map((f) => ({ f, d: dist2(f) }));
  const trls = trailsFC.features.map((f) => ({ f, d: dist2(f) }));
  const maxD = pts.reduce((m2, x) => Math.max(m2, x.d), 0) || 1;

  let cancelled = false;
  let raf = 0;
  const start = performance.now();

  const frame = (now) => {
    if (cancelled) return;
    const t = Math.min(1, (now - start) / BLOOM_MS);
    const threshold = easeInOutCubic(t) * maxD * 1.02;
    try {
      m.getSource("hikes-source")?.setData({
        type: "FeatureCollection",
        features: pts.filter((x) => x.d <= threshold).map((x) => x.f),
      });
      m.getSource("trails-source")?.setData({
        type: "FeatureCollection",
        features: trls.filter((x) => x.d <= threshold).map((x) => x.f),
      });
    } catch { return; /* map removed mid-bloom */ }
    if (t < 1) raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);

  return () => {
    cancelled = true;
    cancelAnimationFrame(raf);
    setFull();
  };
}

/* ── [1][3] Add all sources + layers once on map 'load' ─────────────────── */
function setupLayers(m) {
  // ── Trail polylines ──────────────────────────────────────────────────────
  m.addSource("trails-source", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });
  m.addLayer({
    id:     "trails-layer",
    type:   "line",
    source: "trails-source",
    layout: { "line-join": "round", "line-cap": "round" },
    paint:  { "line-color": MAP.trail, "line-width": 2.5, "line-opacity": 0.85 },
  });

  // ── Clustered point source ───────────────────────────────────────────────
  m.addSource("hikes-source", {
    type:           "geojson",
    data:           { type: "FeatureCollection", features: [] },
    cluster:        true,      // [3] WebGL-native clustering – zero extra deps
    clusterRadius:  50,
    clusterMaxZoom: 12,        // pins break apart at zoom 13+
  });

  // Cluster bubbles
  m.addLayer({
    id: "clusters", type: "circle", source: "hikes-source",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": [
        "step", ["get", "point_count"],
        MAP.cluster[0], 10, MAP.cluster[1], 50, MAP.cluster[2],
      ],
      "circle-radius": [
        "step", ["get", "point_count"],
        20, 10, 28, 50, 36,
      ],
      "circle-stroke-width": 2,
      "circle-stroke-color": "rgba(235,224,194,0.7)",
    },
  });

  // Cluster count labels
  m.addLayer({
    id: "cluster-count", type: "symbol", source: "hikes-source",
    filter: ["has", "point_count"],
    layout: {
      "text-field": "{point_count_abbreviated}",
      "text-font":  ["DIN Offc Pro Medium", "Arial Unicode MS Bold"],
      "text-size":  12,
    },
    paint: { "text-color": MAP.onEmber },
  });

  // Individual (unclustered) pins
  m.addLayer({
    id: "unclustered-point", type: "circle", source: "hikes-source",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color":        MAP.pin,
      "circle-radius":       7,
      "circle-stroke-width": 2,
      "circle-stroke-color": "rgba(235,224,194,0.9)",
    },
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   MapPage
   ══════════════════════════════════════════════════════════════════════════ */
export default function MapPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // ── Map refs ──────────────────────────────────────────────────────────────
  const mapContainer  = useRef(null);
  const map           = useRef(null);
  const popupRef      = useRef(null);       // hover popup, reused not recreated
  const moveTimerRef  = useRef(null);       // moveend debounce handle
  const hasAutoFitted = useRef(false);      // fit-to-results only on first load
  const userMarkerRef = useRef(null);
  const hasBloomed    = useRef(false);      // radial reveal plays once, on first load
  const bloomCancelRef = useRef(null);      // stops an in-flight bloom (snaps to full)

  // ── Stable function / data refs (prevent stale closures in WebGL callbacks)
  const hikesRef      = useRef([]);
  const selectHikeRef = useRef(null);
  const navigateRef   = useRef(navigate);
  const searchRef     = useRef(null);
  const filtersRef    = useRef(null);
  const locRef        = useRef(null);
  const buildParamsRef = useRef(null);      // always-current param builder

  // ── List-container height (measured by ResizeObserver for virtual List) ──
  const listContainerRef = useRef(null);
  const [listHeight, setListHeight] = useState(400);

  // ── Filter state ──────────────────────────────────────────────────────────
  const [filters, setFilters] = useState({
    maxDistanceMiles:     null,
    difficulty:           null,
    minLengthMiles:       null,
    maxLengthMiles:       null,
    meetRequirementsOnly: false,
    state:                null,
    region:               null,
    month:                null,
  });

  const { hikes, loading, error, searchHikes, selectHike } = useHikes();
  const {
    location: userLocation,
    loading:  locationLoading,
    error:    locationError,
  } = useUserLocation();

  /* ── Keep stable refs current ───────────────────────────────────────────── */
  useEffect(() => { hikesRef.current       = hikes;       }, [hikes]);
  useEffect(() => { selectHikeRef.current  = selectHike;  }, [selectHike]);
  useEffect(() => { navigateRef.current    = navigate;    }, [navigate]);
  useEffect(() => { searchRef.current      = searchHikes; }, [searchHikes]);
  useEffect(() => { filtersRef.current     = filters;     }, [filters]);
  useEffect(() => { locRef.current         = userLocation; }, [userLocation]);

  /* ── [2][4] Param builder – always reads latest state through refs ──────── */
  // Assigned each render so it always captures current filter + location state.
  // Reads map.current.getBounds() for the live viewport bbox.
  buildParamsRef.current = () => {
    const f  = filtersRef.current ?? {};
    const ul = locRef.current;
    const p  = { limit: RESULT_LIMIT }; // [4] hard cap

    if (f.minLengthMiles  && +f.minLengthMiles  > 0)
      p.min_length_km = +((f.minLengthMiles  * 1.60934).toFixed(3));
    if (f.maxLengthMiles  && +f.maxLengthMiles  > 0)
      p.max_length_km = +((f.maxLengthMiles  * 1.60934).toFixed(3));
    if (f.difficulty)             p.difficulty            = f.difficulty;
    if (f.region)                 p.region                = f.region;
    if (f.state)                  p.state                 = f.state;
    if (f.month)                  p.month                 = f.month;
    if (f.meetRequirementsOnly)   p.meet_requirements_only = true;
    if (f.maxDistanceMiles)
      p.max_dist = +((f.maxDistanceMiles * 1.60934).toFixed(3));
    if (ul) { p.user_lat = ul.lat; p.user_lon = ul.lng; }

    // [2] Viewport bbox – only included once the map has valid bounds
    if (map.current?.loaded()) {
      const b = map.current.getBounds();
      p.bbox_min_lng = b.getWest();
      p.bbox_min_lat = b.getSouth();
      p.bbox_max_lng = b.getEast();
      p.bbox_max_lat = b.getNorth();
    }

    return p;
  };

  /* ── Effect 1: Map init, sources, layers, and persistent event handlers ── */
  useEffect(() => {
    if (map.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style:     "mapbox://styles/mapbox/light-v11",
      center:    [-98.5795, 39.8283],
      zoom:      4,
    });
    map.current.addControl(new mapboxgl.NavigationControl(), "top-right");

    // Reusable hover popup – created once, moved on each mouseenter
    popupRef.current = new mapboxgl.Popup({
      closeButton:  false,
      closeOnClick: false,
      offset:       14,
    });

    map.current.on("load", () => {
      // Nudge the base tiles toward aged paper before adding our own layers
      applyPaperBase(map.current);
      // [1][3] One-time layer setup
      setupLayers(map.current);

      // ── [3] Cluster click → drill in ─────────────────────────────────────
      map.current.on("click", "clusters", (e) => {
        const [feat]    = map.current.queryRenderedFeatures(e.point, { layers: ["clusters"] });
        const clusterId = feat.properties.cluster_id;
        map.current.getSource("hikes-source")
          .getClusterExpansionZoom(clusterId, (err, zoom) => {
            if (!err) map.current.easeTo({ center: feat.geometry.coordinates, zoom });
          });
      });

      // ── [1] Pin click → navigate to hike detail ───────────────────────────
      // Uses hikesRef so the handler never captures stale hike data
      map.current.on("click", "unclustered-point", (e) => {
        const id   = e.features[0].properties.id;
        const hike = hikesRef.current.find((h) => h.id === id);
        if (!hike) return;
        selectHikeRef.current?.(hike);
        navigateRef.current(`/hike/${hike.id}`);
      });

      // ── Hover: cursor + tooltip popup ────────────────────────────────────
      map.current.on("mouseenter", "unclustered-point", (e) => {
        map.current.getCanvas().style.cursor = "pointer";
        const coords = [...e.features[0].geometry.coordinates];
        const name   = e.features[0].properties.name;
        popupRef.current
          .setLngLat(coords)
          .setHTML(
            `<span style="font-family:Georgia,serif;font-size:13px;color:#1a1209">${name}</span>`
          )
          .addTo(map.current);
      });
      map.current.on("mouseleave", "unclustered-point", () => {
        map.current.getCanvas().style.cursor = "";
        popupRef.current.remove();
      });
      map.current.on("mouseenter", "clusters", () => {
        map.current.getCanvas().style.cursor = "pointer";
      });
      map.current.on("mouseleave", "clusters", () => {
        map.current.getCanvas().style.cursor = "";
      });

      // ── [2] moveend → re-query with current viewport bbox ────────────────
      map.current.on("moveend", () => {
        clearTimeout(moveTimerRef.current);
        moveTimerRef.current = setTimeout(() => {
          searchRef.current?.(buildParamsRef.current());
        }, MOVEEND_DELAY);
      });

      // Initial search now that map.getBounds() returns valid data
      searchRef.current?.(buildParamsRef.current());
    });

    return () => {
      clearTimeout(moveTimerRef.current);
      bloomCancelRef.current?.();
      map.current?.remove();
      map.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Effect 2: User-location dot ──────────────────────────────────────── */
  useEffect(() => {
    if (!map.current || !userLocation) return;
    const el = Object.assign(document.createElement("div"), { className: "user-location-dot" });
    if (userMarkerRef.current) {
      userMarkerRef.current.setLngLat([userLocation.lng, userLocation.lat]);
    } else {
      userMarkerRef.current = new mapboxgl.Marker(el)
        .setLngLat([userLocation.lng, userLocation.lat])
        .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML("<strong>You are here</strong>"))
        .addTo(map.current);
    }
  }, [userLocation]);

    /* ── Effect 3: Debounced re-search on filter / location change ─────────── */
  useEffect(() => {
    if (!map.current?.loaded()) return;   // map's 'load' handler covers the first search
    const t = setTimeout(() => searchRef.current?.(buildParamsRef.current()), 300);
    return () => clearTimeout(t);
  }, [filters, userLocation]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Effect 4: Immediate re-fetch when navigating back to /map ─────────── */
  useEffect(() => {
    if (location.pathname !== "/map") return;
    if (!map.current?.loaded()) return;   // same — avoid duplicating the initial search
    searchRef.current?.(buildParamsRef.current());
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Effect 5: Push new hike data into the WebGL sources ──────────────── */
  // Single setData call per hikes change – no DOM marker creation at all
  useEffect(() => {
    if (!map.current?.loaded()) return;

    // A new result set supersedes any in-flight bloom — cancel it (which snaps
    // to full data) so a pan landing mid-bloom never leaves a half-revealed map.
    bloomCancelRef.current?.();
    bloomCancelRef.current = null;

    const { pointsFC, trailsFC } = buildGeoJSON(hikes);

    // First populated load blooms outward from the centroid of the results;
    // every later update (pan, zoom, filter change) snaps instantly. Re-blooming
    // on each moveend would look choppy and fight the camera.
    if (hikes.length > 0 && !hasBloomed.current) {
      hasBloomed.current = true;
      const sum = pointsFC.features.reduce(
        (a, f) => [a[0] + f.geometry.coordinates[0], a[1] + f.geometry.coordinates[1]],
        [0, 0],
      );
      const n = pointsFC.features.length || 1;
      bloomCancelRef.current = bloomInSources(
        map.current, pointsFC, trailsFC, { lng: sum[0] / n, lat: sum[1] / n },
      );
    } else {
      map.current.getSource("hikes-source")?.setData(pointsFC);
      map.current.getSource("trails-source")?.setData(trailsFC);
    }

    // Auto-fit to results once on first load only; panning after that is the
    // user's choice and shouldn't be interrupted.
    if (hikes.length > 0 && !hasAutoFitted.current) {
      hasAutoFitted.current = true;
      const bounds = new mapboxgl.LngLatBounds();
      hikes.forEach((h) => {
        if (h.geometry?.type === "LineString")
          h.geometry.coordinates.forEach((c) => bounds.extend(c));
        else if (h.geometry?.type === "Point")
          bounds.extend(h.geometry.coordinates);
      });
      map.current.fitBounds(bounds, { padding: 60, maxZoom: 14 });
    }
  }, [hikes]);

  /* ── Effect 6: [5] Measure list container height for virtual List ──────── */
  useEffect(() => {
    if (!listContainerRef.current) return;
    const ro = new ResizeObserver(([entry]) =>
      setListHeight(entry.contentRect.height)
    );
    ro.observe(listContainerRef.current);
    return () => ro.disconnect();
  }, []);

  /* ── Derived ─────────────────────────────────────────────────────────────── */
  // [4] True when the backend hit the hard cap – prompt the user to filter/zoom
  const atLimit = hikes.length >= RESULT_LIMIT;

  // Stable itemData object for virtual List (avoids re-rendering every row on
  // unrelated state changes)
  const listData = useMemo(
    () => ({
      hikes,
      onSelect: (hike) => { selectHike(hike); navigate(`/hike/${hike.id}`); },
    }),
    [hikes, selectHike, navigate]
  );

  /* ── Render ──────────────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", height: "100vh", background: C.page }}>

      {/* ── LEFT: Map ─────────────────────────────────────────────────────── */}
      <div style={{ position: "relative", flex: 1 }}>
        <div ref={mapContainer} style={{ height: "100%", width: "100%", background: MAP.land }} />

        {/* Trip Planner button */}
        <button
          onClick={() => navigate("/trip-planner")}
          title="Plan a Trip"
          style={{
            position: "absolute", top: 16, right: 96, zIndex: 10,
            background: "rgba(235,224,194,0.92)", backdropFilter: "blur(8px)",
            padding: "8px 10px", borderRadius: 8,
            border: `1px solid ${P.rule}`, cursor: "pointer",
            boxShadow: `0 2px 10px ${P.shadow}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "border-color 0.15s, background 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = P.ember;
            e.currentTarget.style.background  = "rgba(237,222,186,0.98)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = P.rule;
            e.currentTarget.style.background  = "rgba(235,224,194,0.92)";
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke={P.inkSoft} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
          </svg>
        </button>

        {/* Profile button */}
        <button
          onClick={() => navigate("/profile")}
          title="Go to Profile"
          style={{
            position: "absolute", top: 16, right: 56, zIndex: 10,
            background: "rgba(235,224,194,0.92)", backdropFilter: "blur(8px)",
            padding: "8px 10px", borderRadius: 8,
            border: `1px solid ${P.rule}`, cursor: "pointer",
            boxShadow: `0 2px 10px ${P.shadow}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "border-color 0.15s, background 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = P.ember;
            e.currentTarget.style.background  = "rgba(237,222,186,0.98)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = P.rule;
            e.currentTarget.style.background  = "rgba(235,224,194,0.92)";
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke={P.inkSoft} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </button>

        <MapLegend />
      </div>

      {/* ── RIGHT: Sidebar ────────────────────────────────────────────────── */}
      <div style={{
        width: 320, display: "flex", flexDirection: "column",
        background: C.page,
        borderLeft: `1px solid ${C.divider}`,
        boxShadow: "-4px 0 24px rgba(61,40,23,0.10)",
        zIndex: 10,
      }}>

        {/* Header */}
        <div style={{
          flexShrink: 0,
          background: "rgba(235,224,194,0.96)", backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(162,133,90,0.7)",
          boxShadow: "0 4px 20px rgba(61,40,23,0.08)",
          padding: "14px 20px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MountainMark />
            <div>
              <h1 style={{
                fontFamily: serif, fontSize: 18, fontWeight: "normal",
                color: C.heading, margin: 0, letterSpacing: "0.3px",
              }}>
                Trail Finder
              </h1>
              {/* [4] Limit hint replaces count when the cap is hit */}
              <p style={{
                fontFamily: body, fontSize: 12, color: atLimit ? C.label : C.muted,
                margin: "2px 0 0", fontStyle: "italic",
              }}>
                {loading
                  ? "Searching…"
                  : atLimit
                    ? `${RESULT_LIMIT}+ trails — zoom in or filter`
                    : `${hikes.length} trail${hikes.length !== 1 ? "s" : ""} found`}
              </p>
            </div>
          </div>

          {loading && (
            <div style={{
              width: 7, height: 7, borderRadius: "50%",
              background: C.amber, opacity: 0.8,
              animation: "pulse 1.2s ease-in-out infinite",
            }} />
          )}
        </div>

        {/* Filters */}
        <div style={{
          flexShrink: 0,
          padding: "14px 16px",
          background: C.card,
          borderBottom: `1px solid ${C.cardBorder}`,
        }}>
          <FilterBar filters={filters} onChange={setFilters} />

          <div style={{ marginTop: 8, minHeight: 14 }}>
            {locationLoading && (
              <p style={{ fontFamily: sans, fontSize: 10, color: C.muted, margin: 0 }}>
                Locating…
              </p>
            )}
            {locationError && (
              <p style={{ fontFamily: sans, fontSize: 10, color: "#96301f", margin: 0 }}>
                {locationError}
              </p>
            )}
            {userLocation && !locationLoading && (
              <p style={{
                fontFamily: sans, fontSize: 10, color: C.muted, margin: 0,
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span style={{
                  display: "inline-block", width: 5, height: 5,
                  borderRadius: "50%", background: "#7a6236", flexShrink: 0,
                }} />
                Location active
              </p>
            )}
          </div>
        </div>

        {/* ── Results – virtualised ──────────────────────────────────────── */}
        <div
          ref={listContainerRef}
          style={{ flex: 1, overflow: "hidden", position: "relative" }}
        >
          {/* Error state */}
          {error && !loading && (
            <p style={{
              fontFamily: sans, fontSize: 12, color: "#96301f",
              textAlign: "center", padding: "16px 0", margin: 0,
            }}>
              {error}
            </p>
          )}

          {/* Loading – no results yet: skeleton cards show the list's shape
              immediately instead of a bare spinner. */}
          {loading && hikes.length === 0 && (
            <HikeCardSkeletonList count={7} rowHeight={CARD_HEIGHT} />
          )}

          {/* Empty state */}
          {!loading && hikes.length === 0 && !error && (
            <div style={{ textAlign: "center", padding: "48px 16px" }}>
              <p style={{ fontFamily: serif, fontSize: 15, color: C.subtext,
                fontWeight: "normal", margin: "0 0 8px" }}>
                No trails found
              </p>
              <p style={{ fontFamily: body, fontSize: 12, color: C.muted,
                fontStyle: "italic", margin: 0 }}>
                Try broadening your filters or zooming out.
              </p>
            </div>
          )}

          {/* Updating nudge (floats above the list while results refresh) */}
          {loading && hikes.length > 0 && (
            <p style={{
              fontFamily: sans, fontSize: 10, color: C.muted, margin: 0,
              textAlign: "right",
              position: "absolute", top: 6, right: 14, zIndex: 1,
            }}>
              Updating…
            </p>
          )}

          {/* [5] Virtual list – only visible cards are in the DOM */}
          {hikes.length > 0 && (
            <List
              height={listHeight}
              itemCount={hikes.length}
              itemSize={CARD_HEIGHT}
              itemData={listData}
              width="100%"
            >
              {HikeRow}
            </List>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.9); }
          50%       { opacity: 1;   transform: scale(1.1); }
        }
      `}</style>
    </div>
  );
}