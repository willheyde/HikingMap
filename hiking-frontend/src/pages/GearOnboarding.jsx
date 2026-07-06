import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "../context/UserContext";
import { listItems } from "../api/itemsService";

/* ─── Design tokens (matches AuthModal) ─────────────────────────────────── */
const C = {
  page:        "#0d0a07",
  card:        "#1c1510",
  cardBorder:  "#4a3520",
  fieldBg:     "#241a10",
  fieldBorder: "#5a3e22",
  heading:     "#f0e6d0",
  subtext:     "#a08060",
  muted:       "#6a4e30",
  label:       "#b8906a",
  amber:       "#c17a2e",
  amberHover:  "#d98c38",
  amberText:   "#fff8ee",
  amberDim:    "rgba(193,122,46,0.15)",
  amberBorder: "rgba(193,122,46,0.4)",
  ownedBg:     "rgba(60,100,40,0.25)",
  ownedBorder: "rgba(90,160,60,0.5)",
  ownedText:   "#9dcc85",
  divider:     "#3a2510",
};
const serif = "Georgia, 'Times New Roman', serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";
const body  = "'Palatino Linotype', Palatino, Georgia, serif";

/* ─── Step definitions ───────────────────────────────────────────────────── */
const STEPS = [
  { key: "backpack",       label: "Backpack",       icon: "🎒", multi: false },
  { key: "footwear",       label: "Footwear",        icon: "👟", multi: true  },
  { key: "shelter",        label: "Shelter",         icon: "⛺", multi: false },
  { key: "sleeping_bag",   label: "Sleeping Bag",    icon: "🛌", multi: false },
  { key: "sleeping_pad",   label: "Sleeping Pad",    icon: "🟫", multi: false },
  { key: "clothing",       label: "Clothing",        icon: "🧥", multi: true  },
  { key: "water",          label: "Water System",    icon: "💧", multi: true  },
  { key: "kitchen",        label: "Kitchen",         icon: "🔥", multi: false },
  { key: "navigation",     label: "Navigation",      icon: "🗺️", multi: true  },
  { key: "safety",         label: "Safety",          icon: "🚨", multi: true  },
  { key: "lighting",       label: "Lighting",        icon: "🔦", multi: false },
  { key: "trekking_poles", label: "Trekking Poles",  icon: "🥢", multi: false },
  { key: "technical",      label: "Technical Gear",  icon: "⛏️", multi: true  },
];

/* ─── Mountain mark ─────────────────────────────────────────────────────── */
const MountainMark = ({ size = 40 }) => (
  <svg width={size} height={size * 0.75} viewBox="0 0 56 42"
    style={{ display: "block", margin: "0 auto" }} xmlns="http://www.w3.org/2000/svg">
    <polygon points="28,2 52,40 4,40" fill="none" stroke="#7a5030" strokeWidth="1.2" strokeLinejoin="round" />
    <polygon points="14,40 28,14 42,40" fill="#2a1810" stroke="#5a3820" strokeWidth="1" strokeLinejoin="round" />
    <polygon points="28,2 33,10 23,10" fill="#8a6a50" />
    <path d="M0,40 Q14,36 28,39 Q42,42 56,38" fill="none" stroke="#1e3048" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/* ─── Progress bar ──────────────────────────────────────────────────────── */
const ProgressBar = ({ step, total }) => (
  <div style={{ marginBottom: 24 }}>
    <div style={{ display: "flex", justifyContent: "space-between",
      fontFamily: sans, fontSize: 11, color: C.muted, marginBottom: 7 }}>
      <span style={{ textTransform: "uppercase", letterSpacing: "1px" }}>
        Step {step + 1} of {total}
      </span>
      <span>{Math.round(((step + 1) / total) * 100)}%</span>
    </div>
    <div style={{ height: 3, background: C.fieldBg, borderRadius: 2 }}>
      <div style={{
        height: 3, borderRadius: 2, background: C.amber,
        width: `${((step + 1) / total) * 100}%`,
        transition: "width 0.4s ease",
      }} />
    </div>
  </div>
);

/* ─── Selectable item row ────────────────────────────────────────────────── */
const ItemRow = ({ item, selected, onClick }) => (
  <button
    onClick={onClick}
    style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      width: "100%", padding: "13px 16px", marginBottom: 8, textAlign: "left",
      background: selected ? C.amberDim : C.fieldBg,
      border: `1.5px solid ${selected ? C.amber : C.fieldBorder}`,
      borderRadius: 10, cursor: "pointer", transition: "all 0.15s",
      boxShadow: selected ? `0 0 12px rgba(193,122,46,0.18)` : "none",
    }}
    onMouseEnter={e => { if (!selected) e.currentTarget.style.borderColor = "#7a5a30"; }}
    onMouseLeave={e => { if (!selected) e.currentTarget.style.borderColor = C.fieldBorder; }}
  >
    <div style={{ flex: 1 }}>
      <div style={{ fontFamily: body, fontSize: 14, color: selected ? "#c8a97a" : "#c8bfb0", fontWeight: selected ? 600 : 400 }}>
        {item.name}
      </div>
      <div style={{ fontFamily: sans, fontSize: 11, color: C.muted, marginTop: 3 }}>
        {(Number(item.weight) / 1000).toFixed(2)} kg · ${Number(item.cost).toFixed(0)}
      </div>
    </div>
    <div style={{
      width: 18, height: 18, borderRadius: "50%", flexShrink: 0, marginLeft: 12,
      background: selected ? C.amber : "transparent",
      border: `1.5px solid ${selected ? C.amber : C.fieldBorder}`,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {selected && (
        <svg width="10" height="7" viewBox="0 0 10 7" fill="none">
          <path d="M1 3L3.5 5.5L9 1" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
    </div>
  </button>
);

/* ─── Main component ─────────────────────────────────────────────────────── */
const GearOnboarding = () => {
  const { user, addItemsBatch } = useUser();
  const navigate = useNavigate();

  const [stepIndex, setStepIndex]     = useState(0);
  const [stepItems, setStepItems]     = useState([]);
  const [loadingStep, setLoadingStep] = useState(true);
  const [selections, setSelections]   = useState({}); // { [item_type]: Set<id> }
  const [saving, setSaving]           = useState(false);

  const step = STEPS[stepIndex];

  /* Fetch items for the current step */
  useEffect(() => {
    setLoadingStep(true);
    listItems(step.key)
      .then(setStepItems)
      .catch(console.error)
      .finally(() => setLoadingStep(false));
  }, [step.key]);

  /* Selection helpers */
  const currentSel = selections[step.key] ?? new Set();

  const toggle = (itemId) => {
    setSelections(prev => {
      const set = new Set(prev[step.key] ?? []);
      if (step.multi) {
        set.has(itemId) ? set.delete(itemId) : set.add(itemId);
      } else {
        set.clear();
        set.add(itemId);
      }
      return { ...prev, [step.key]: set };
    });
  };

  const skipStep = () => {
    setSelections(prev => ({ ...prev, [step.key]: new Set() }));
    advance();
  };

  const advance = () => {
    if (stepIndex < STEPS.length - 1) {
      setStepIndex(i => i + 1);
    } else {
      finish();
    }
  };

  const finish = async () => {
    setSaving(true);
    const allIds = Object.values(selections).flatMap(s => Array.from(s));
    try {
      if (allIds.length > 0 && user) {
        await addItemsBatch(user.id, allIds);
      }
      navigate("/gear");
    } catch (err) {
      console.error("Failed to save gear:", err);
      navigate("/gear");
    } finally {
      setSaving(false);
    }
  };

  const isLast = stepIndex === STEPS.length - 1;

  /* ── Render ─────────────────────────────────────────────────────────────── */
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
        boxShadow: "0 32px 80px rgba(0,0,0,0.55)",
      }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
          <MountainMark size={44} />
          <h1 style={{
            fontFamily: serif, fontSize: 24, fontWeight: "normal",
            color: C.heading, margin: "14px 0 5px", letterSpacing: "0.3px",
          }}>
            Build your kit
          </h1>
          <p style={{ fontFamily: body, fontSize: 13, color: C.subtext, margin: 0, fontStyle: "italic" }}>
            Select what you own — we'll plan around it.
          </p>
        </div>

        {/* Divider */}
        <div style={{
          height: 1, marginBottom: "1.5rem",
          background: `linear-gradient(to right, transparent, ${C.divider} 30%, ${C.cardBorder} 50%, ${C.divider} 70%, transparent)`,
        }} />

        {/* Skip onboarding */}
        <div style={{ textAlign: "right", marginBottom: "1rem", marginTop: "-0.75rem" }}>
          <button
            onClick={() => navigate("/gear")}
            style={{
              background: "none", border: "none", padding: 0,
              fontFamily: sans, fontSize: 11, color: C.muted,
              letterSpacing: "0.5px", cursor: "pointer",
              textDecoration: "underline", textUnderlineOffset: "3px",
            }}
            onMouseEnter={e => e.currentTarget.style.color = C.label}
            onMouseLeave={e => e.currentTarget.style.color = C.muted}
          >
            Skip onboarding →
          </button>
        </div>

        {/* Item list */}
        <div style={{ maxHeight: 340, overflowY: "auto", marginBottom: 4,
          scrollbarWidth: "thin", scrollbarColor: `${C.cardBorder} transparent` }}>
          {loadingStep ? (
            <div style={{ textAlign: "center", padding: "40px 0",
              fontFamily: sans, fontSize: 12, color: C.muted, letterSpacing: "1px" }}>
              Loading…
            </div>
          ) : stepItems.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 0",
              fontFamily: body, fontSize: 14, color: C.muted, fontStyle: "italic" }}>
              No items found for this category.
            </div>
          ) : (
            stepItems.map(item => (
              <ItemRow
                key={item.id}
                item={item}
                selected={currentSel.has(item.id)}
                onClick={() => toggle(item.id)}
              />
            ))
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          {/* Back / Skip */}
          <button
            onClick={stepIndex === 0 ? skipStep : () => setStepIndex(i => i - 1)}
            style={{
              flex: 1, padding: "12px 0", borderRadius: 10,
              background: "transparent",
              border: `1px solid ${C.fieldBorder}`,
              color: C.muted, fontFamily: sans, fontSize: 12,
              cursor: "pointer", letterSpacing: "0.5px",
            }}
            onMouseEnter={e => e.currentTarget.style.color = C.label}
            onMouseLeave={e => e.currentTarget.style.color = C.muted}
          >
            {stepIndex === 0 ? "Skip" : "← Back"}
          </button>

          {/* Continue */}
          <button
            onClick={currentSel.size > 0 ? advance : skipStep}
            disabled={saving}
            style={{
              flex: 3, padding: "12px 0", borderRadius: 10,
              background: saving ? "#7a4a1e" : C.amber,
              border: `1px solid ${saving ? "#5a3010" : "rgba(255,220,150,0.15)"}`,
              color: C.amberText, fontFamily: sans, fontSize: 13,
              fontWeight: 600, cursor: saving ? "not-allowed" : "pointer",
              letterSpacing: "0.5px", transition: "background 0.2s",
            }}
            onMouseEnter={e => { if (!saving) e.currentTarget.style.background = C.amberHover; }}
            onMouseLeave={e => { if (!saving) e.currentTarget.style.background = C.amber; }}
          >
            {saving
              ? "Saving…"
              : currentSel.size > 0
                ? isLast ? `Finish  ✓` : `Continue  →`
                : isLast ? "Finish without this" : "Skip this category"}
          </button>
        </div>

        <p style={{
          textAlign: "center", fontFamily: sans, fontSize: 11,
          color: C.muted, marginTop: 20, letterSpacing: "0.5px",
        }}>
          Leave no trace · Stay on the trail
        </p>
      </div>
    </div>
  );
};

export default GearOnboarding;