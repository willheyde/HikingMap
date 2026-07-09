import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "../context/useUser";
import { GEAR_SECTIONS } from "../data/gearCategories";

/* ─── Field Journal tokens (matches AuthModal / old onboarding) — hikeStyle ── */
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
  amberText:   "#ebe0c2", // on-ember
  amberDim:    "rgba(168,59,44,0.15)",
  amberBorder: "rgba(168,59,44,0.4)",
  ownedBg:     "#d8c48e",              // sage-wash
  ownedBorder: "rgba(122,98,54,0.5)",
  ownedText:   "#6e5a2e",              // deep sage
  errorText:   "#96301f",              // rust
  divider:     "#a2855a",              // rule
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";

/* ─── Mountain mark ─────────────────────────────────────────────────────── */
const MountainMark = ({ size = 44 }) => (
  <svg width={size} height={size * 0.75} viewBox="0 0 56 42"
    style={{ display: "block", margin: "0 auto" }} xmlns="http://www.w3.org/2000/svg">
    <polygon points="28,2 52,40 4,40" fill="none" stroke="#a83b2c" strokeWidth="1.2" strokeLinejoin="round" />
    <polygon points="14,40 28,14 42,40" fill="#e4cb9e" stroke="#5c3a21" strokeWidth="1" strokeLinejoin="round" />
    <polygon points="28,2 33,10 23,10" fill="#ebe0c2" />
    <path d="M0,40 Q14,36 28,39 Q42,42 56,38" fill="none" stroke="#a2855a" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/* ─── Progress bar ──────────────────────────────────────────────────────── */
const ProgressBar = ({ step, total }) => (
  <div style={{ marginBottom: 22 }}>
    <div style={{ display: "flex", justifyContent: "space-between",
      fontFamily: sans, fontSize: 11, color: C.muted, marginBottom: 7 }}>
      <span style={{ textTransform: "uppercase", letterSpacing: "1px" }}>Step {step + 1} of {total}</span>
      <span>{Math.round(((step + 1) / total) * 100)}%</span>
    </div>
    <div style={{ height: 3, background: C.fieldBg, borderRadius: 2 }}>
      <div style={{ height: 3, borderRadius: 2, background: C.amber,
        width: `${((step + 1) / total) * 100}%`, transition: "width 0.4s ease" }} />
    </div>
  </div>
);

/* ─── Level chip ────────────────────────────────────────────────────────── */
const LevelChip = ({ label, selected, onClick }) => (
  <button
    onClick={onClick}
    style={{
      padding: "9px 14px", borderRadius: 999, cursor: "pointer",
      fontFamily: sans, fontSize: 12.5, fontWeight: selected ? 600 : 400,
      background: selected ? C.amberDim : C.fieldBg,
      border: `1.5px solid ${selected ? C.amber : C.fieldBorder}`,
      color: selected ? "#3d2817" : "#5c3a21", transition: "all 0.15s",
    }}
    onMouseEnter={e => { if (!selected) e.currentTarget.style.borderColor = "#c9b488"; }}
    onMouseLeave={e => { if (!selected) e.currentTarget.style.borderColor = C.fieldBorder; }}
  >
    {label}
  </button>
);

/* ─── Main component ────────────────────────────────────────────────────── */
const GearOnboarding = () => {
  const { user, createGear, deleteItem } = useUser();
  const navigate = useNavigate();

  const [sectionIndex, setSectionIndex]   = useState(0);
  const [addedBySection, setAddedBySection] = useState({}); // { key: [{id,name,levelLabel}] }
  const [pendingLevel, setPendingLevel]   = useState(null);
  const [pendingName, setPendingName]     = useState("");
  const [pendingTemp, setPendingTemp]     = useState("");
  const [busy, setBusy]                   = useState(false);
  const [error, setError]                 = useState(null);

  const section = GEAR_SECTIONS[sectionIndex];
  const added   = addedBySection[section.key] || [];
  const isLast  = sectionIndex === GEAR_SECTIONS.length - 1;
  const needsLevel = Array.isArray(section.levels);
  const canAdd  = !busy && (!needsLevel || pendingLevel !== null);

  // Clear the per-section draft whenever the section changes.
  useEffect(() => {
    setPendingLevel(null);
    setPendingName("");
    setPendingTemp("");
    setError(null);
  }, [sectionIndex]);

  const addItem = async () => {
    if (!canAdd || !user) return;
    const levelObj = section.levels?.find(l => l.value === pendingLevel);
    const name = pendingName.trim() || levelObj?.label || section.label;
    const payload = { name, gear_category: section.key, level: needsLevel ? pendingLevel : null };
    if (section.sleepTemp && pendingTemp !== "") {
      const t = Number(pendingTemp);
      if (!Number.isNaN(t)) payload.temp_rating_f = t;
    }
    setBusy(true); setError(null);
    try {
      const item = await createGear(user.id, payload);
      setAddedBySection(prev => ({
        ...prev,
        [section.key]: [...(prev[section.key] || []), { id: item.id, name, levelLabel: levelObj?.label }],
      }));
      setPendingLevel(null);
      setPendingName("");
      setPendingTemp("");
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeItem = async (item) => {
    setError(null);
    try {
      await deleteItem(user.id, item.id);
      setAddedBySection(prev => ({
        ...prev,
        [section.key]: (prev[section.key] || []).filter(i => i.id !== item.id),
      }));
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const next = () => (isLast ? navigate("/") : setSectionIndex(i => i + 1));
  const back = () => setSectionIndex(i => Math.max(0, i - 1));

  return (
    <div style={{
      minHeight: "100vh", background: C.page,
      display: "flex", alignItems: "flex-start", justifyContent: "center",
      padding: "40px 16px 80px",
    }}>
      <div style={{
        width: "100%", maxWidth: 460,
        background: C.card, border: `1px solid ${C.cardBorder}`,
        borderRadius: 20, padding: "2rem 1.75rem",
        boxShadow: "0 24px 60px rgba(61,40,23,0.16)",
      }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <MountainMark size={44} />
          <h1 style={{ fontFamily: serif, fontSize: 24, fontWeight: "normal",
            color: C.heading, margin: "14px 0 5px", letterSpacing: "0.3px" }}>
            Build your kit
          </h1>
          <p style={{ fontFamily: body, fontSize: 13, color: C.subtext, margin: 0, fontStyle: "italic" }}>
            Tell us what you own — we plan trips around it.
          </p>
        </div>

        <ProgressBar step={sectionIndex} total={GEAR_SECTIONS.length} />

        {/* Skip onboarding */}
        <div style={{ textAlign: "right", marginBottom: "0.75rem", marginTop: "-0.5rem" }}>
          <button
            onClick={() => navigate("/")}
            style={{ background: "none", border: "none", padding: 0,
              fontFamily: sans, fontSize: 11, color: C.muted, letterSpacing: "0.5px",
              cursor: "pointer", textDecoration: "underline", textUnderlineOffset: "3px" }}
            onMouseEnter={e => e.currentTarget.style.color = C.label}
            onMouseLeave={e => e.currentTarget.style.color = C.muted}
          >
            Skip onboarding →
          </button>
        </div>

        {/* Section */}
        <div style={{ marginBottom: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 22 }}>{section.icon}</span>
            <span style={{ fontFamily: serif, fontSize: 18, color: C.heading }}>{section.label}</span>
          </div>
          <p style={{ fontFamily: body, fontSize: 13, color: C.subtext, margin: "0 0 14px" }}>
            {section.prompt}
          </p>

          {/* Level chips */}
          {needsLevel && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
              {section.levels.map(l => (
                <LevelChip
                  key={l.value}
                  label={l.label}
                  selected={pendingLevel === l.value}
                  onClick={() => setPendingLevel(v => (v === l.value ? null : l.value))}
                />
              ))}
            </div>
          )}

          {/* Sleep temp */}
          {section.sleepTemp && (
            <input
              type="number"
              value={pendingTemp}
              onChange={e => setPendingTemp(e.target.value)}
              placeholder="Temp rating °F (e.g. 20) — optional"
              style={{
                width: "100%", boxSizing: "border-box", marginBottom: 10,
                padding: "11px 13px", background: C.fieldBg,
                border: `1.5px solid ${C.fieldBorder}`, borderRadius: 10,
                color: C.heading, fontFamily: sans, fontSize: 13,
              }}
            />
          )}

          {/* Name + Add */}
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={pendingName}
              onChange={e => setPendingName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") addItem(); }}
              placeholder={needsLevel
                ? (section.levels.find(l => l.value === pendingLevel)?.label || "Name it (optional)")
                : `e.g. my ${section.label.toLowerCase()}`}
              style={{
                flex: 1, boxSizing: "border-box", padding: "11px 13px",
                background: C.fieldBg, border: `1.5px solid ${C.fieldBorder}`,
                borderRadius: 10, color: C.heading, fontFamily: sans, fontSize: 13,
              }}
            />
            <button
              onClick={addItem}
              disabled={!canAdd}
              title={needsLevel && !pendingLevel ? "Pick a level first" : "Add"}
              style={{
                padding: "0 18px", borderRadius: 10, flexShrink: 0,
                background: canAdd ? C.amber : C.fieldBg,
                border: `1px solid ${canAdd ? C.amber : C.fieldBorder}`,
                color: canAdd ? C.amberText : C.muted,
                fontFamily: sans, fontSize: 13, fontWeight: 600,
                cursor: canAdd ? "pointer" : "default", transition: "all 0.15s",
              }}
            >
              {busy ? "…" : "Add"}
            </button>
          </div>

          {error && (
            <div style={{ fontFamily: sans, fontSize: 11.5, color: C.errorText, marginTop: 8 }}>
              {error}
            </div>
          )}

          {/* Added items */}
          {added.length > 0 && (
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
              {added.map(item => (
                <div key={item.id} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "9px 12px", borderRadius: 9,
                  background: C.ownedBg, border: `1px solid ${C.ownedBorder}`,
                }}>
                  <span style={{ fontFamily: sans, fontSize: 12.5, color: C.ownedText }}>
                    {item.name}
                    {item.levelLabel && item.levelLabel !== item.name && (
                      <span style={{ color: C.muted }}>{"  ·  " + item.levelLabel}</span>
                    )}
                  </span>
                  <button
                    onClick={() => removeItem(item)}
                    title="Remove"
                    style={{ background: "none", border: "none", cursor: "pointer",
                      color: C.muted, fontSize: 15, lineHeight: 1, padding: "2px 4px" }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Nav */}
        <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
          <button
            onClick={back}
            disabled={sectionIndex === 0}
            style={{
              flex: 1, padding: "12px 0", borderRadius: 10, background: "transparent",
              border: `1px solid ${C.fieldBorder}`,
              color: sectionIndex === 0 ? C.muted : C.label,
              opacity: sectionIndex === 0 ? 0.4 : 1,
              fontFamily: sans, fontSize: 12, letterSpacing: "0.5px",
              cursor: sectionIndex === 0 ? "default" : "pointer",
            }}
          >
            ← Back
          </button>
          <button
            onClick={next}
            style={{
              flex: 3, padding: "12px 0", borderRadius: 10, background: C.amber,
              border: `1px solid ${C.amberBorder}`, color: C.amberText,
              fontFamily: sans, fontSize: 13, fontWeight: 600, cursor: "pointer",
              letterSpacing: "0.5px", transition: "background 0.2s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = C.amberHover}
            onMouseLeave={e => e.currentTarget.style.background = C.amber}
          >
            {isLast ? "Finish  ✓" : added.length > 0 ? "Next  →" : "Skip this  →"}
          </button>
        </div>

        <p style={{ textAlign: "center", fontFamily: sans, fontSize: 11,
          color: C.muted, marginTop: 20, letterSpacing: "0.5px" }}>
          Leave no trace · Stay on the trail
        </p>
      </div>
    </div>
  );
};

export default GearOnboarding;
