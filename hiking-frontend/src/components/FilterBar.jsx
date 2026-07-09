import React from "react";

/* ─── Field Journal tokens (hikeStyle.md) ──────────────────────────────── */
const C = {
  fieldBg:      "#ccb98f", // paper-sunk
  fieldBorder:  "#a2855a", // rule
  fieldBorderHover: "#c9b488",
  heading:      "#3d2817", // ink
  muted:        "#6a4a26", // ink-muted
  label:        "#5c3a21", // ink-soft
  amber:        "#a83b2c", // ember
  amberText:    "#ebe0c2", // on-ember
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";

const fieldBase = {
  width: "100%",
  padding: "5px 8px",
  fontSize: 12,
  fontFamily: sans,
  color: C.heading,
  background: C.fieldBg,
  border: `1px solid ${C.fieldBorder}`,
  borderRadius: 6,
  outline: "none",
  transition: "border-color 0.15s",
  boxSizing: "border-box",
  /* Placeholder color handled globally in styles/global.css */
};

const labelStyle = {
  display: "block",
  fontFamily: sans,
  fontSize: 10,
  fontWeight: 600,
  color: C.label,
  textTransform: "uppercase",
  letterSpacing: "1px",
  marginBottom: 4,
};

const onFocus = (e) => (e.target.style.borderColor = C.amber);
const onBlur  = (e) => (e.target.style.borderColor = C.fieldBorder);

export default function FilterBar({ filters, onChange }) {
  const update = (key, value) => onChange({ ...filters, [key]: value });

  return (
    <div className="hike-filter" style={{ display: "flex", flexDirection: "column", gap: 10 }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontFamily: serif, fontSize: 14, fontWeight: "normal",
          color: C.heading, margin: 0 }}>
          Filters
        </h2>
        <button
          onClick={() => onChange({
            maxDistanceMiles: null, difficulty: null, minLengthMiles: null,
            maxLengthMiles: null, meetRequirementsOnly: false,
            state: null, region: null, month: null,
          })}
          style={{
            background: "none", border: "none", padding: 0, cursor: "pointer",
            fontFamily: sans, fontSize: 11, color: C.amber, textDecoration: "underline",
          }}
        >
          Reset
        </button>
      </div>

      {/* ── Row 1: State & Difficulty ────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div>
          <label style={labelStyle}>State</label>
          <select
            value={filters.state ?? ""}
            onChange={(e) => update("state", e.target.value || null)}
            style={fieldBase}
            onFocus={onFocus} onBlur={onBlur}
          >
            <option value="">All</option>
            <option value="CA">CA</option>
            <option value="CO">CO</option>
            <option value="WA">WA</option>
            <option value="OR">OR</option>
            <option value="MT">MT</option>
            <option value="WY">WY</option>
            <option value="UT">UT</option>
            <option value="AZ">AZ</option>
            <option value="NM">NM</option>
            <option value="ID">ID</option>
            <option value="NV">NV</option>
            <option value="TX">TX</option>
            <option value="NC">NC</option>
            <option value="TN">TN</option>
            <option value="VA">VA</option>
            <option value="PA">PA</option>
            <option value="NY">NY</option>
            <option value="VT">VT</option>
            <option value="NH">NH</option>
            <option value="ME">ME</option>
            <option value="RI">RI</option>
          </select>
        </div>
        <div>
          <label style={labelStyle}>Difficulty</label>
          <select
            value={filters.difficulty ?? ""}
            onChange={(e) => update("difficulty", e.target.value || null)}
            style={fieldBase}
            onFocus={onFocus} onBlur={onBlur}
          >
            <option value="">Any</option>
            <option value="EASY">Easy</option>
            <option value="MODERATE">Moderate</option>
            <option value="HARD">Hard</option>
          </select>
        </div>
      </div>

      {/* ── Row 2: Trail Length ──────────────────────────────────────────── */}
      <div>
        <label style={labelStyle}>Trail Length (mi)</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="number" min="0" step="0.1" placeholder="Min"
            value={filters.minLengthMiles ?? ""}
            onChange={(e) => update("minLengthMiles", e.target.value === "" ? null : Number(e.target.value))}
            style={{ ...fieldBase, flex: 1 }}
            onFocus={onFocus} onBlur={onBlur}
          />
          <input
            type="number" min="0" step="0.1" placeholder="Max"
            value={filters.maxLengthMiles ?? ""}
            onChange={(e) => update("maxLengthMiles", e.target.value === "" ? null : Number(e.target.value))}
            style={{ ...fieldBase, flex: 1 }}
            onFocus={onFocus} onBlur={onBlur}
          />
        </div>
      </div>

      {/* ── Row 3: Max Radius & Month ────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div>
          <label style={labelStyle}>Max Radius (mi)</label>
          <input
            type="number" min="0" step="1" placeholder="Any"
            value={filters.maxDistanceMiles ?? ""}
            onChange={(e) => update("maxDistanceMiles", e.target.value === "" ? null : Number(e.target.value))}
            style={fieldBase}
            onFocus={onFocus} onBlur={onBlur}
          />
        </div>
        <div>
          <label style={labelStyle}>Best Month</label>
          <select
            value={filters.month ?? ""}
            onChange={(e) => update("month", e.target.value === "" ? null : Number(e.target.value))}
            style={fieldBase}
            onFocus={onFocus} onBlur={onBlur}
          >
            <option value="">Any</option>
            {["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
              .map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
          </select>
        </div>
      </div>

      {/* ── Row 4: Gear requirement toggle ───────────────────────────────── */}
      <div
        onClick={() => update("meetRequirementsOnly", !filters.meetRequirementsOnly)}
        style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "8px 10px", borderRadius: 7, cursor: "pointer",
          background: filters.meetRequirementsOnly
            ? "rgba(168,59,44,0.1)"
            : "transparent",
          border: `1px solid ${filters.meetRequirementsOnly
            ? "rgba(168,59,44,0.35)"
            : C.fieldBorder}`,
          transition: "all 0.15s",
        }}
        onMouseEnter={e => {
          if (!filters.meetRequirementsOnly)
            e.currentTarget.style.borderColor = C.fieldBorderHover;
        }}
        onMouseLeave={e => {
          if (!filters.meetRequirementsOnly)
            e.currentTarget.style.borderColor = C.fieldBorder;
        }}
      >
        {/* Custom checkbox */}
        <div style={{
          width: 14, height: 14, flexShrink: 0, borderRadius: 3,
          border: `1.5px solid ${filters.meetRequirementsOnly ? C.amber : C.fieldBorder}`,
          background: filters.meetRequirementsOnly ? C.amber : "transparent",
          display: "flex", alignItems: "center", justifyContent: "center",
          transition: "all 0.15s",
        }}>
          {filters.meetRequirementsOnly && (
            <svg width="8" height="6" viewBox="0 0 10 8" fill="none">
              <path d="M1.5 4L3.5 6.5L8.5 1.5"
                stroke={C.amberText} strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </div>
        <span style={{
          fontFamily: sans, fontSize: 12, userSelect: "none",
          color: filters.meetRequirementsOnly ? C.label : C.muted,
        }}>
          My gear only
        </span>
      </div>
    </div>
  );
}