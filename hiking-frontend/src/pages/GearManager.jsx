import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "../context/UserContext";
import { GEAR_SECTIONS, resolveGearCategory, levelLabelFor } from "../data/gearCategories";
import ScrollBar from "../components/ScrollBar";

/* ─── Field Journal tokens (shared with GearOnboarding) — hikeStyle.md ────── */
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
  ownedBorder: "rgba(122,98,54,0.45)",
  ownedText:   "#6e5a2e",              // deep sage
  errorText:   "#96301f",              // rust
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";

/* ─── Mountain mark ─────────────────────────────────────────────────────── */
const MountainMark = () => (
  <svg width="28" height="22" viewBox="0 0 40 32" fill="none" style={{ flexShrink: 0 }}>
    <polygon points="20,2 38,30 2,30" fill="none" stroke="#a83b2c" strokeWidth="1.5" strokeLinejoin="round"/>
    <polygon points="10,30 20,12 30,30" fill="#e4cb9e" stroke="#5c3a21" strokeWidth="1" strokeLinejoin="round"/>
  </svg>
);

const LevelChip = ({ label, selected, onClick }) => (
  <button onClick={onClick} style={{
    padding: "7px 12px", borderRadius: 999, cursor: "pointer",
    fontFamily: sans, fontSize: 12, fontWeight: selected ? 600 : 400,
    background: selected ? C.amberDim : C.fieldBg,
    border: `1.5px solid ${selected ? C.amber : C.fieldBorder}`,
    color: selected ? "#3d2817" : "#5c3a21", transition: "all 0.15s",
  }}>
    {label}
  </button>
);

/* ─── One category card: existing items + inline add ─────────────────────── */
const SectionCard = ({ section, items, onAdd, onRemove }) => {
  const needsLevel = Array.isArray(section.levels);
  const [pendingLevel, setPendingLevel] = useState(null);
  const [pendingName, setPendingName]   = useState("");
  const [pendingTemp, setPendingTemp]   = useState("");
  const [busy, setBusy]                 = useState(false);
  const [error, setError]               = useState(null);

  const canAdd = !busy && (!needsLevel || pendingLevel !== null);

  const submit = async () => {
    if (!canAdd) return;
    const levelObj = section.levels?.find(l => l.value === pendingLevel);
    const name = pendingName.trim() || levelObj?.label || section.label;
    const payload = { name, gear_category: section.key, level: needsLevel ? pendingLevel : null };
    if (section.sleepTemp && pendingTemp !== "") {
      const t = Number(pendingTemp);
      if (!Number.isNaN(t)) payload.temp_rating_f = t;
    }
    setBusy(true); setError(null);
    try {
      await onAdd(payload);
      setPendingLevel(null); setPendingName(""); setPendingTemp("");
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      background: C.card, border: `1px solid ${C.cardBorder}`,
      borderRadius: 16, padding: "20px 22px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontSize: 20 }}>{section.icon}</span>
        <span style={{ fontFamily: serif, fontSize: 17, color: C.heading }}>{section.label}</span>
        <span style={{ fontFamily: sans, fontSize: 11, color: C.muted }}>
          · {items.length} item{items.length !== 1 ? "s" : ""}
        </span>
      </div>
      <p style={{ fontFamily: body, fontSize: 12.5, color: C.subtext, margin: "0 0 14px" }}>
        {section.prompt}
      </p>

      {/* Existing items */}
      {items.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 14 }}>
          {items.map(item => {
            const lvl = levelLabelFor(section.key, item.attributes?.level);
            const temp = item.attributes?.temp_rating_f;
            return (
              <div key={item.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "9px 12px", borderRadius: 9,
                background: C.ownedBg, border: `1px solid ${C.ownedBorder}`,
              }}>
                <span style={{ fontFamily: sans, fontSize: 12.5, color: C.ownedText }}>
                  {item.name}
                  {lvl && lvl !== item.name && (
                    <span style={{ color: C.muted }}>{"  ·  " + lvl}</span>
                  )}
                  {temp != null && (
                    <span style={{ color: C.muted }}>{`  ·  ${Math.round(temp)}°F`}</span>
                  )}
                </span>
                <button onClick={() => onRemove(item)} title="Remove"
                  style={{ background: "none", border: "none", cursor: "pointer",
                    color: C.muted, fontSize: 15, lineHeight: 1, padding: "2px 4px" }}>
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Add row */}
      {needsLevel && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 10 }}>
          {section.levels.map(l => (
            <LevelChip key={l.value} label={l.label}
              selected={pendingLevel === l.value}
              onClick={() => setPendingLevel(v => (v === l.value ? null : l.value))} />
          ))}
        </div>
      )}
      {section.sleepTemp && (
        <input type="number" value={pendingTemp}
          onChange={e => setPendingTemp(e.target.value)}
          placeholder="Temp rating °F (e.g. 20) — optional"
          style={{ width: "100%", boxSizing: "border-box", marginBottom: 8,
            padding: "10px 12px", background: C.fieldBg,
            border: `1.5px solid ${C.fieldBorder}`, borderRadius: 9,
            color: C.heading, fontFamily: sans, fontSize: 12.5 }} />
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <input value={pendingName}
          onChange={e => setPendingName(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") submit(); }}
          placeholder={needsLevel
            ? (section.levels.find(l => l.value === pendingLevel)?.label || "Name it (optional)")
            : `e.g. my ${section.label.toLowerCase()}`}
          style={{ flex: 1, boxSizing: "border-box", padding: "10px 12px",
            background: C.fieldBg, border: `1.5px solid ${C.fieldBorder}`,
            borderRadius: 9, color: C.heading, fontFamily: sans, fontSize: 12.5 }} />
        <button onClick={submit} disabled={!canAdd}
          title={needsLevel && !pendingLevel ? "Pick a level first" : "Add"}
          style={{ padding: "0 18px", borderRadius: 9, flexShrink: 0,
            background: canAdd ? C.amber : C.fieldBg,
            border: `1px solid ${canAdd ? C.amber : C.fieldBorder}`,
            color: canAdd ? C.amberText : C.muted,
            fontFamily: sans, fontSize: 12.5, fontWeight: 600,
            cursor: canAdd ? "pointer" : "default" }}>
          {busy ? "…" : "Add"}
        </button>
      </div>
      {error && (
        <div style={{ fontFamily: sans, fontSize: 11.5, color: C.errorText, marginTop: 8 }}>
          {error}
        </div>
      )}
    </div>
  );
};

/* ─── Main ───────────────────────────────────────────────────────────────── */
const GearManager = () => {
  const { user, items, createGear, deleteItem } = useUser();
  const navigate = useNavigate();

  const itemsBySection = useMemo(() => {
    const map = {};
    (items || []).forEach(item => {
      const key = resolveGearCategory(item);
      (map[key] = map[key] || []).push(item);
    });
    return map;
  }, [items]);

  const otherItems = itemsBySection["misc"] || [];

  const totalWeightKg = useMemo(
    () => (items || []).reduce((s, i) => s + (Number(i.weight) || 0), 0) / 1000,
    [items]);

  const handleAdd = (payload) => createGear(user.id, payload);
  const handleRemove = (item) => deleteItem(user.id, item.id);

  if (!user) return (
    <div style={{ height: "100vh", background: C.page, display: "flex",
      alignItems: "center", justifyContent: "center" }}>
      <p style={{ fontFamily: body, color: C.muted, fontStyle: "italic" }}>
        Please log in to manage your gear.
      </p>
    </div>
  );

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column",
      background: C.page, overflow: "hidden" }}>

      {/* Header */}
      <div style={{ flexShrink: 0, background: "rgba(235,224,194,0.94)",
        backdropFilter: "blur(12px)", borderBottom: `1px solid rgba(162,133,90,0.7)`,
        boxShadow: "0 4px 20px rgba(61,40,23,0.08)" }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "14px 20px",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MountainMark />
            <div>
              <h1 style={{ fontFamily: serif, fontSize: 18, fontWeight: "normal",
                color: C.heading, margin: 0 }}>Gear Locker</h1>
              <p style={{ fontFamily: body, fontSize: 12, color: C.muted,
                margin: "2px 0 0", fontStyle: "italic" }}>
                What you own — we plan trips around it.
              </p>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: sans, fontSize: 10, color: C.muted,
                textTransform: "uppercase", letterSpacing: "1.5px" }}>Pack Weight</div>
              <div style={{ fontFamily: "monospace", fontSize: 15, color: C.amber }}>
                {totalWeightKg.toFixed(2)} kg
              </div>
            </div>
            <button onClick={() => navigate("/profile")}
              style={{ padding: "8px 16px", borderRadius: 8, fontSize: 12.5,
                fontFamily: sans, fontWeight: 600, background: "#ccb98f",
                color: "#5c3a21", border: "1px solid #a2855a", cursor: "pointer" }}>
              Done
            </button>
          </div>
        </div>
      </div>

      {/* Body */}
      <ScrollBar className="!h-auto flex-1" style={{ background: C.page }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "24px 20px 100px",
          display: "flex", flexDirection: "column", gap: 14 }}>
          {GEAR_SECTIONS.map(section => (
            <SectionCard key={section.key} section={section}
              items={itemsBySection[section.key] || []}
              onAdd={handleAdd} onRemove={handleRemove} />
          ))}

          {/* Anything that doesn't map to a functional category (legacy misc). */}
          {otherItems.length > 0 && (
            <div style={{ background: C.card, border: `1px solid ${C.cardBorder}`,
              borderRadius: 16, padding: "20px 22px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 20 }}>📦</span>
                <span style={{ fontFamily: serif, fontSize: 17, color: C.heading }}>Other gear</span>
                <span style={{ fontFamily: sans, fontSize: 11, color: C.muted }}>
                  · {otherItems.length} item{otherItems.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {otherItems.map(item => (
                  <div key={item.id} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "9px 12px", borderRadius: 9,
                    background: C.fieldBg, border: `1px solid ${C.fieldBorder}` }}>
                    <span style={{ fontFamily: sans, fontSize: 12.5, color: "#3d2817" }}>{item.name}</span>
                    <button onClick={() => handleRemove(item)} title="Remove"
                      style={{ background: "none", border: "none", cursor: "pointer",
                        color: C.muted, fontSize: 15, lineHeight: 1, padding: "2px 4px" }}>✕</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p style={{ textAlign: "center", fontFamily: sans, fontSize: 11,
            color: C.muted, marginTop: 12, letterSpacing: "0.5px" }}>
            Leave no trace · Stay on the trail
          </p>
        </div>
      </ScrollBar>
    </div>
  );
};

export default GearManager;
