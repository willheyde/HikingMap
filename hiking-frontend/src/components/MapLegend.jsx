/* ─── Design tokens (mirrored from MapPage) ──────────────────────────────── */
const C = {
  page:        "#0d0a07",
  card:        "#1c1510",
  cardBorder:  "#4a3520",
  heading:     "#f0e6d0",
  subtext:     "#a08060",
  muted:       "#6a4e30",
  label:       "#b8906a",
  amber:       "#c17a2e",
  amberBorder: "rgba(193,122,46,0.35)",
  divider:     "#3a2510",
};
const serif = "Georgia, 'Times New Roman', serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";

/* ─── Individual legend row ──────────────────────────────────────────────── */
function LegendItem({ indicator, label }) {
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{
        flexShrink: 0,
        width: 20, height: 20,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {indicator}
      </span>
      <span style={{ fontFamily: sans, fontSize: 11, color: C.subtext, letterSpacing: "0.3px" }}>
        {label}
      </span>
    </li>
  );
}

/* ─── Indicator shapes (match actual mapbox layer paint specs) ───────────── */

// Matches "unclustered-point": circle-color #22c55e, r=8, white stroke @ 0.6 opacity, width 2
const TrailPin = () => (
  <svg width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="6" fill="#22c55e" stroke="rgba(255,255,255,0.6)" strokeWidth="2" />
  </svg>
);

// Matches "trails-layer": line-color #22c55e, width 3, opacity 0.8 — solid, no dasharray
const TrailLine = () => (
  <svg width="20" height="6" viewBox="0 0 20 6">
    <line x1="0" y1="3" x2="20" y2="3"
      stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeOpacity="0.8" />
  </svg>
);

// Matches "clusters" + "cluster-count": step-colored circle, white count label
const TrailCluster = () => (
  <svg width="20" height="20" viewBox="0 0 20 20">
    <circle cx="10" cy="10" r="9" fill="#c17a2e" stroke="rgba(255,255,255,0.15)" strokeWidth="2" />
    <text x="10" y="13.5" textAnchor="middle" fontSize="8" fontFamily="Arial, sans-serif"
      fontWeight="bold" fill="#ffffff">12</text>
  </svg>
);

// Matches the .user-location-dot marker — adjust fill if your CSS class differs
const UserLocationDot = () => (
  <svg width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="7" fill="rgba(66,133,244,0.25)" />
    <circle cx="8" cy="8" r="4" fill="#4285f4" stroke="#ffffff" strokeWidth="1.5" />
  </svg>
);

/* ─── MapLegend ──────────────────────────────────────────────────────────── */
export default function MapLegend() {
  return (
    <div style={{
      position: "absolute", bottom: 28, left: 16, zIndex: 5,
      background: "rgba(20,13,7,0.92)", backdropFilter: "blur(10px)",
      border: `1px solid ${C.cardBorder}`,
      borderRadius: 10,
      padding: "12px 16px",
      boxShadow: "0 4px 24px rgba(0,0,0,0.5)",
      minWidth: 170,
    }}>
      <p style={{
        fontFamily: serif, fontSize: 12, fontWeight: "normal",
        color: C.label, margin: "0 0 10px",
        letterSpacing: "0.6px", textTransform: "uppercase",
        borderBottom: `1px solid ${C.divider}`, paddingBottom: 8,
      }}>
        Map Legend
      </p>

      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        <LegendItem indicator={<TrailPin />}        label="Trail Marker" />
        <LegendItem indicator={<TrailLine />}       label="Trail Path" />
        <LegendItem indicator={<TrailCluster />}    label="Multiple Trails" />
        <LegendItem indicator={<UserLocationDot />} label="Your Location" />
      </ul>
    </div>
  );
}