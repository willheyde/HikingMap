import { memo } from "react";
/* ─── Field Journal tokens (hikeStyle.md) ──────────────────────────────── */
const C = {
  heading: "#3d2817", // ink
  muted:   "#6a4a26", // ink-muted
  label:   "#5c3a21", // ink-soft (stat text)
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";
const mono  = "'Courier New', Courier, monospace";

const DIFFICULTY = {
  EASY:      { label: "Easy",      color: "#6e5a2e", bg: "#d8c48e", border: "rgba(122,98,54,0.4)" },
  MODERATE:  { label: "Moderate",  color: "#9a5f1f", bg: "#e4cb9e", border: "rgba(168,59,44,0.45)" },
  // DB difficulty tiers are EASY/MODERATE/DIFFICULT/EXPERT (PyObjects/Hike.py).
  DIFFICULT: { label: "Difficult", color: "#96301f", bg: "#e6c29a", border: "rgba(150,48,31,0.4)" },
  EXPERT:    { label: "Expert",    color: "#7a1f14", bg: "#e0b48c", border: "rgba(122,31,20,0.5)" },
  HARD:      { label: "Hard",      color: "#96301f", bg: "#e6c29a", border: "rgba(150,48,31,0.4)" }, // legacy alias
};

function HikeSummaryCard({ hike , onClick }) {
  const miles  = ((hike.length_km || 0) * 0.621371).toFixed(1);
  const elevFt = Math.round((hike.elevation_gain_m || 0) * 3.28084);
  const diff   = DIFFICULTY[hike.difficulty];

  return (
    <div onClick={onClick} style={{ padding: "14px 16px" }}>

      {/* ── Name + difficulty badge ──────────────────────────────────────── */}
      <div style={{
        display: "flex", justifyContent: "space-between",
        alignItems: "flex-start", gap: 8, marginBottom: 5,
      }}>
        <h3 style={{
          fontFamily: serif, fontSize: 14, fontWeight: "normal",
          color: C.heading, margin: 0, lineHeight: 1.35,
        }}>
          {hike.name}
        </h3>

        {diff && (
          <span style={{
            flexShrink: 0,
            fontFamily: sans, fontSize: 10, fontWeight: 700,
            textTransform: "uppercase", letterSpacing: "0.5px",
            color: diff.color, background: diff.bg,
            border: `1px solid ${diff.border}`,
            padding: "2px 7px", borderRadius: 9999,
          }}>
            {diff.label}
          </span>
        )}
      </div>

      {/* ── Region ──────────────────────────────────────────────────────── */}
      {hike.region && (
        <p style={{
          fontFamily: body, fontSize: 11, color: C.muted,
          fontStyle: "italic", margin: "0 0 10px",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          📍 {hike.region}
        </p>
      )}

      {/* ── Stats row ───────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontFamily: mono, fontSize: 11, color: C.label }}>
          {miles} mi
        </span>

        {elevFt > 0 && (
          <>
            <Dot />
            <span style={{ fontFamily: mono, fontSize: 11, color: C.label }}>
              ↑ {elevFt.toLocaleString()} ft
            </span>
          </>
        )}

        {hike.season_start_month && hike.season_end_month && (
          <>
            <Dot />
            <span style={{ fontFamily: sans, fontSize: 10, color: C.muted }}>
              {getMonthName(hike.season_start_month)}–{getMonthName(hike.season_end_month)}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
export default memo(HikeSummaryCard);

/* ─── Helpers ───────────────────────────────────────────────────────────── */
const Dot = () => (
  <span style={{ display: "inline-block", width: 3, height: 3, borderRadius: "50%",
    background: "#6a4a26", flexShrink: 0 }} />
);

function getMonthName(n) {
  return ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"][n - 1] ?? "";
}