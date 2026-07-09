/* ─── Field Journal palette (hikeStyle.md §5) — on-map overlay ───────────────
   Indicator swatches mirror the actual mapbox layer paint specs in MapPage. */
import { palette as P, fonts } from "../styles/theme";

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
      <span style={{ fontFamily: fonts.sans, fontSize: 11, color: P.inkSoft, letterSpacing: "0.3px" }}>
        {label}
      </span>
    </li>
  );
}

/* ─── Indicator shapes (match actual mapbox layer paint specs) ───────────── */

// "unclustered-point": red circle, cream stroke
const TrailPin = () => (
  <svg width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="6" fill={P.ember} stroke={P.paper} strokeWidth="2" />
  </svg>
);

// "trails-layer": red route line
const TrailLine = () => (
  <svg width="20" height="6" viewBox="0 0 20 6">
    <line x1="0" y1="3" x2="20" y2="3"
      stroke={P.ember} strokeWidth="2.5" strokeLinecap="round" strokeOpacity="0.9" />
  </svg>
);

// "clusters" + "cluster-count": ember bubble, paper stroke + count
const TrailCluster = () => (
  <svg width="20" height="20" viewBox="0 0 20 20">
    <circle cx="10" cy="10" r="9" fill={P.ember} stroke="rgba(235,224,194,0.7)" strokeWidth="2" />
    <text x="10" y="13.5" textAnchor="middle" fontSize="8" fontFamily="Arial, sans-serif"
      fontWeight="bold" fill={P.onEmber}>12</text>
  </svg>
);

// ".user-location-dot": ink dot, cream ring, faint ink halo
const UserLocationDot = () => (
  <svg width="16" height="16" viewBox="0 0 16 16">
    <circle cx="8" cy="8" r="7" fill="rgba(61,40,23,0.20)" />
    <circle cx="8" cy="8" r="4" fill={P.ink} stroke={P.paper} strokeWidth="1.5" />
  </svg>
);

/* ─── MapLegend ──────────────────────────────────────────────────────────── */
export default function MapLegend() {
  return (
    <div style={{
      position: "absolute", bottom: 28, left: 16, zIndex: 5,
      background: "rgba(235,224,194,0.92)", backdropFilter: "blur(10px)",
      border: `1px solid ${P.rule}`,
      borderRadius: 10,
      padding: "12px 16px",
      boxShadow: `0 4px 20px ${P.shadow}`,
      minWidth: 170,
    }}>
      <p style={{
        fontFamily: fonts.display, fontSize: 12, fontWeight: 500,
        color: P.ember, margin: "0 0 10px",
        letterSpacing: "0.6px", textTransform: "uppercase",
        borderBottom: `1px solid ${P.rule}`, paddingBottom: 8,
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
