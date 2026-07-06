import { memo } from "react";
/* ─── Design tokens (matches Profile & GearSetup) ──────────────────────── */
const C = {
  heading: "#f0e6d0",
  muted:   "#6a4e30",
  label:   "#b8906a",
};
const serif = "Georgia, 'Times New Roman', serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";
const body  = "'Palatino Linotype', Palatino, Georgia, serif";
const mono  = "'Courier New', Courier, monospace";

const DIFFICULTY = {
  EASY:     { label: "Easy",     color: "#9dcc85", bg: "rgba(80,140,60,0.15)",  border: "rgba(90,160,60,0.3)"  },
  MODERATE: { label: "Moderate", color: "#c8a97a", bg: "rgba(193,122,46,0.15)", border: "rgba(193,122,46,0.3)" },
  HARD:     { label: "Hard",     color: "#e8907a", bg: "rgba(180,60,40,0.15)",  border: "rgba(180,60,40,0.3)"  },
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
    background: "#4a3520", flexShrink: 0 }} />
);

function getMonthName(n) {
  return ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"][n - 1] ?? "";
}