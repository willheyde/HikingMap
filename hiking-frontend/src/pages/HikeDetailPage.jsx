import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { useHikes } from "../context/HikeContext";
import { useUser } from "../context/UserContext";
import ScrollBar from "../components/ScrollBar";
import { HikeDetailSkeleton } from "../components/Skeleton";
import { readinessForHike } from "../data/gearCategories";

/* ─── Field Journal tokens (shared with Profile / GearManager) — hikeStyle ── */
const C = {
  page:        "#dccaa0", // canvas
  card:        "#ebe0c2", // paper
  cardBorder:  "#a2855a", // rule
  fieldBg:     "#ccb98f", // paper-sunk
  fieldBorder: "#a2855a", // rule
  heading:     "#3d2817", // ink
  subtext:     "#5c3a21", // ink-soft
  muted:       "#6a4a26", // ink-muted
  label:       "#a83b2c", // ember
  amber:       "#a83b2c", // ember
  amberHover:  "#8e3022", // ember-hover
  amberDim:    "rgba(168,59,44,0.12)",
  amberBorder: "rgba(168,59,44,0.35)",
  amberText:   "#ebe0c2", // on-ember
  divider:     "#a2855a", // rule
  green:       "#7a6236", // sage
  greenDim:    "rgba(122,98,54,0.14)",
  red:         "#96301f", // rust
  redDim:      "rgba(150,48,31,0.10)",
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";

/* ─── Helpers ────────────────────────────────────────────────────────────── */
const kmToMiles    = (km) => (km * 0.621371).toFixed(1);
const metersToFeet = (m)  => Math.round(m * 3.28084);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const formatDifficulty = (d) => (d ? d.charAt(0) + d.slice(1).toLowerCase() : "Unknown");

/* Status → color + glyph for a readiness row. */
const STATUS = {
  ok:      { color: C.green, bg: C.greenDim,  border: "rgba(122,98,54,0.4)",  glyph: "✓" },
  missing: { color: C.red,   bg: C.redDim,    border: "rgba(150,48,31,0.4)",   glyph: "✗" },
  flag:    { color: C.amber, bg: C.amberDim,  border: C.amberBorder,           glyph: "!" },
};

/* ─── Stat card ──────────────────────────────────────────────────────────── */
const StatCard = ({ label, value, icon }) => (
  <div style={{
    background: C.card, border: `1px solid ${C.cardBorder}`,
    borderRadius: 14, padding: "18px 16px",
    display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 8,
  }}>
    <span style={{ color: C.amber, opacity: 0.8 }}>{icon}</span>
    <span style={{ fontFamily: sans, fontSize: 10.5, color: C.muted,
      textTransform: "uppercase", letterSpacing: "1.2px" }}>{label}</span>
    <span style={{ fontFamily: serif, fontSize: 20, color: C.heading }}>{value}</span>
  </div>
);

/* ─── Readiness row ──────────────────────────────────────────────────────── */
const ReadinessRow = ({ row }) => {
  const s = STATUS[row.status] || STATUS.flag;
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 12,
      padding: "12px 14px", borderRadius: 10,
      background: s.bg, border: `1px solid ${s.border}`,
    }}>
      <span style={{
        flexShrink: 0, width: 20, height: 20, borderRadius: "50%",
        background: s.color, color: C.page, fontFamily: sans, fontSize: 12, fontWeight: 700,
        display: "flex", alignItems: "center", justifyContent: "center", marginTop: 1,
      }}>{s.glyph}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontFamily: sans, fontSize: 13.5, fontWeight: 600, color: C.heading }}>
            {row.icon} {row.label}
          </span>
          {row.required && (
            <span style={{ fontFamily: sans, fontSize: 11, color: C.muted }}>
              needs {row.required}
            </span>
          )}
          {row.importance !== "required" && (
            <span style={{ fontFamily: sans, fontSize: 10, color: C.muted,
              textTransform: "uppercase", letterSpacing: "0.5px" }}>· recommended</span>
          )}
        </div>
        {row.note && (
          <p style={{ fontFamily: body, fontSize: 12.5, color: C.subtext, margin: "4px 0 0" }}>
            {row.note}
          </p>
        )}
      </div>
    </div>
  );
};

/* ─── Main ───────────────────────────────────────────────────────────────── */
export default function HikeDetailPage() {
  const { hikeId } = useParams();
  const navigate = useNavigate();

  const { selectedHike, loadHikeById, loading, error } = useHikes();
  const { user, items } = useUser();

  useEffect(() => {
    if (!selectedHike || String(selectedHike.id) !== String(hikeId)) {
      loadHikeById(hikeId);
    }
  }, [hikeId, selectedHike, loadHikeById]);

  // Resolve the trailhead's lat/lng to a real place label (town, state) — the
  // same reverse-geocode the trip planner uses — instead of the coarse DB
  // region. Stored with its hike id so a stale label from the previous hike is
  // ignored; the render falls back to region until (or unless) this resolves.
  const [place, setPlace] = useState(null);   // { id, label }
  const detailId = selectedHike?.id;
  const geoLat = selectedHike?.lat;
  const geoLng = selectedHike?.lng;
  useEffect(() => {
    if (geoLat == null || geoLng == null) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/reverse?format=json&lat=${geoLat}&lon=${geoLng}&zoom=12&addressdetails=1`,
          { headers: { "User-Agent": "HikePlannerApp/1.0" } }
        );
        const data = await res.json();
        const a = data.address || {};
        const p = a.town || a.city || a.village || a.hamlet || a.county || a.suburb;
        const label = [p, a.state].filter(Boolean).join(", ");
        if (!cancelled && label) setPlace({ id: detailId, label });
      } catch {
        /* leave place unset → render falls back to region */
      }
    })();
    return () => { cancelled = true; };
  }, [detailId, geoLat, geoLng]);
  const placeLabel = place?.id != null && String(place.id) === String(detailId)
    ? place.label
    : null;

  const readiness = useMemo(
    () => readinessForHike(selectedHike?.gear_requirements, items),
    [selectedHike, items]
  );
  const unmetCount = readiness.filter(r => r.status !== "ok").length;
  const essentialsMissing = readiness.filter(r => r.status === "missing").length;

  const formatSeason = () => {
    if (!selectedHike?.season_start_month || !selectedHike?.season_end_month) return "Year-round";
    return `${MONTHS[selectedHike.season_start_month - 1]} – ${MONTHS[selectedHike.season_end_month - 1]}`;
  };

  const startTrip = () => {
    // Pre-fill the planner's composer with wording that lands on the name-lookup
    // path (exact trail name → confident match) — the user reviews it and hits
    // send, rather than it firing automatically.
    navigate("/trip-planner", {
      state: { draftMessage: `I want to plan a trip to ${selectedHike.name}.` },
    });
  };

  /* ── Loading / error ─────────────────────────────────────────────────── */
  if (loading || (!selectedHike && !error)) {
    return (
      <div style={{ height: "100%", background: C.page, overflow: "auto" }}>
        <HikeDetailSkeleton />
      </div>
    );
  }
  if (error) {
    return (
      <ScrollBar style={{ background: C.page }}>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 20px" }}>
          <BackButton navigate={navigate} />
          <div style={{ marginTop: 20, padding: 24, borderRadius: 12, textAlign: "center",
            background: C.redDim, border: "1px solid rgba(150,48,31,0.4)",
            fontFamily: body, color: C.red }}>{error}</div>
        </div>
      </ScrollBar>
    );
  }
  if (!selectedHike) return null;

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div style={{ minHeight: "100%", background: C.page }}>
      <ScrollBar style={{ background: C.page }}>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "36px 20px 100px" }}>

          <BackButton navigate={navigate} />

          {/* Header */}
          <div style={{ marginTop: 20, marginBottom: 24 }}>
            <h1 style={{ fontFamily: serif, fontSize: 34, fontWeight: "normal",
              color: C.heading, margin: "0 0 8px" }}>{selectedHike.name}</h1>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <svg width="16" height="16" fill="none" stroke={C.subtext} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
              <span style={{ fontFamily: body, fontSize: 15, color: C.subtext }}>
                {placeLabel
                  || `${selectedHike.region}${selectedHike.state ? `, ${selectedHike.state}` : ""}`}
              </span>
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 12, marginBottom: 22 }}>
            <StatCard label="Length" value={`${kmToMiles(selectedHike.length_km)} mi`}
              icon={<Icon d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />} />
            <StatCard label="Elevation" value={`${metersToFeet(selectedHike.elevation_gain_m)} ft`}
              icon={<Icon d="M13 10V3L4 14h7v7l9-11h-7z" />} />
            <StatCard label="Difficulty" value={formatDifficulty(selectedHike.difficulty)}
              icon={<Icon d="M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />} />
            <StatCard label="Season" value={formatSeason()}
              icon={<Icon d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />} />
          </div>

          {/* Permits */}
          {selectedHike.permits_required && (
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start",
              padding: "14px 16px", borderRadius: 12, marginBottom: 22,
              background: C.amberDim, border: `1px solid ${C.amberBorder}` }}>
              <span style={{ fontSize: 20 }}>⚠️</span>
              <div>
                <div style={{ fontFamily: sans, fontSize: 13, fontWeight: 700, color: C.amber }}>
                  Permits required
                </div>
                <p style={{ fontFamily: body, fontSize: 12.5, color: C.subtext, margin: "3px 0 0" }}>
                  Check local regulations and obtain the necessary passes before heading out.
                </p>
              </div>
            </div>
          )}

          {/* Create this trip */}
          <button onClick={startTrip}
            style={{ width: "100%", padding: "15px 0", borderRadius: 12, marginBottom: 30,
              background: C.amber, border: `1px solid ${C.amberBorder}`, color: C.amberText,
              fontFamily: sans, fontSize: 15, fontWeight: 700, cursor: "pointer",
              letterSpacing: "0.3px", boxShadow: "0 6px 22px rgba(168,59,44,0.35)",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}
            onMouseEnter={e => e.currentTarget.style.background = C.amberHover}
            onMouseLeave={e => e.currentTarget.style.background = C.amber}>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
            </svg>
            Plan a trip to {selectedHike.name}
          </button>

          {/* Divider */}
          <div style={{ height: 1, margin: "0 0 26px",
            background: `linear-gradient(to right, transparent, ${C.divider} 30%, ${C.cardBorder} 50%, ${C.divider} 70%, transparent)` }} />

          {/* Trail readiness */}
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between",
            gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
            <div>
              <h2 style={{ fontFamily: serif, fontSize: 22, fontWeight: "normal",
                color: C.heading, margin: "0 0 4px" }}>Trail readiness</h2>
              <p style={{ fontFamily: body, fontSize: 13, color: C.subtext, margin: 0, fontStyle: "italic" }}>
                {user
                  ? "What this trail asks for, checked against your gear locker."
                  : "What this trail asks for — log in to check it against your gear."}
              </p>
            </div>
            {readiness.length > 0 && (
              <div style={{
                padding: "7px 14px", borderRadius: 999, fontFamily: sans, fontSize: 12, fontWeight: 600,
                display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap",
                background: unmetCount === 0 ? C.greenDim : C.amberDim,
                border: `1px solid ${unmetCount === 0 ? "rgba(122,98,54,0.4)" : C.amberBorder}`,
                color: unmetCount === 0 ? C.green : C.amber,
              }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%",
                  background: unmetCount === 0 ? C.green : C.amber }} />
                {unmetCount === 0
                  ? "You're set"
                  : essentialsMissing > 0
                    ? `${essentialsMissing} essential${essentialsMissing !== 1 ? "s" : ""} to sort`
                    : `${unmetCount} thing${unmetCount !== 1 ? "s" : ""} to check`}
              </div>
            )}
          </div>

          {readiness.length === 0 ? (
            <p style={{ fontFamily: body, fontSize: 14, color: C.muted, fontStyle: "italic",
              textAlign: "center", padding: "24px 0" }}>
              No gear requirements recorded for this trail.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {readiness.map(row => <ReadinessRow key={row.category} row={row} />)}
            </div>
          )}

          <p style={{ textAlign: "center", fontFamily: sans, fontSize: 11,
            color: C.muted, marginTop: 40, letterSpacing: "0.5px" }}>
            Leave no trace · Stay on the trail
          </p>
        </div>
      </ScrollBar>
    </div>
  );
}

/* ─── Small shared bits ──────────────────────────────────────────────────── */
const Icon = ({ d }) => (
  <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={d} />
  </svg>
);

const BackButton = ({ navigate }) => (
  <button onClick={() => navigate("/map")}
    style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none",
      padding: 0, cursor: "pointer", fontFamily: sans, fontSize: 13, color: C.label }}
    onMouseEnter={e => e.currentTarget.style.color = C.amber}
    onMouseLeave={e => e.currentTarget.style.color = C.label}>
    <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
    </svg>
    Back to Map
  </button>
);
