import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import GlobalStyles    from "./Globalstyles";
import AmbientHue     from "../components/Ambienthue";
import { useTrip }    from "../context/useTrip";
import { useUser } from "../context/useUser";
import { createUserGear } from "../api/usersService";
import { GEAR_SECTION_BY_KEY, levelLabelFor } from "../data/gearCategories";

// Gap categories (GearGapAnalyzer) → functional gear_category the
// POST /users/:id/gear endpoint expects. Most already match; these don't.
const GAP_TO_GEAR_CATEGORY = {
  rain_gear:     "shell",
  sleep_system:  "sleep",
  trekking_poles: "misc",
};
const toGearCategory = (c) => GAP_TO_GEAR_CATEGORY[c] || c;

/* ─── Design tokens ───────────────────────────────────────────────────── */
const C = {
  page:         "#dccaa0", // canvas
  sidebar:      "#ebe0c2", // paper
  sidebarBorder:"#a2855a", // rule
  fieldBg:      "#ccb98f", // paper-sunk
  fieldBorder:  "#a2855a", // rule
  heading:      "#3d2817", // ink
  subtext:      "#5c3a21", // ink-soft
  muted:        "#6a4a26", // ink-muted
  label:        "#a83b2c", // ember
  amber:        "#a83b2c", // ember
  amberHover:   "#8e3022", // ember-hover
  amberText:    "#ebe0c2", // on-ember
  amberDim:     "rgba(168,59,44,0.12)",
  amberBorder:  "rgba(168,59,44,0.35)",
  userBubble:   "#ccb98f", // paper-sunk
  assistBg:     "transparent",
  inputBg:      "#ccb98f", // paper-sunk
  inputBorder:  "#a2855a", // rule
  errorBg:      "rgba(150,48,31,0.12)",
  errorBorder:  "rgba(150,48,31,0.35)",
  errorText:    "#96301f", // rust
  successBg:    "rgba(122,98,54,0.16)",
  successBorder:"rgba(122,98,54,0.4)",
  successText:  "#6e5a2e", // deep sage
};

const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const mono  = "'Courier New', Courier, monospace";

// Persists which needs_review nudges the user has dismissed — "dismissible,
// user can ignore it indefinitely" means the dismissal has to survive a
// reload, not just clear local state.
const DISMISSED_REVIEW_KEY = "hikebuilder_dismissed_review_nudges";

/* ─── Phase config ───────────────────────────────────────────────────── */
const PHASES = [
  { key: "destination", label: "Destination" },
  { key: "gear_review", label: "Gear Review" },
  { key: "itinerary",   label: "Itinerary"   },
  { key: "finalize",    label: "Finalize"     },
];

const phaseIndex = (key) => PHASES.findIndex(p => p.key === key);

/* ─── Mountain logo ──────────────────────────────────────────────────── */
const Logo = ({ size = 22 }) => (
  <svg width={size} height={size * 0.85} viewBox="0 0 56 48" xmlns="http://www.w3.org/2000/svg" style={{ display: "block" }}>
    <polygon points="28,3 53,43 3,43"  fill="none"    stroke="#5c3a21" strokeWidth="1.4" strokeLinejoin="round"/>
    <polygon points="14,43 28,16 42,43" fill="#e4cb9e" stroke="#a83b2c" strokeWidth="1"   strokeLinejoin="round"/>
    <polygon points="28,3 33,11 23,11"  fill="#a83b2c" opacity="0.8"/>
  </svg>
);

/* ─── Typing indicator ───────────────────────────────────────────────── */
const TypingDots = () => (
  <div style={{ display: "flex", gap: 5, alignItems: "center", padding: "4px 0" }}>
    {[0,1,2].map(i => (
      <div key={i} style={{
        width: 6, height: 6, borderRadius: "50%",
        background: C.amber, opacity: 0.7,
        animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
      }}/>
    ))}
  </div>
);

/* ─── Phase breadcrumb bar ───────────────────────────────────────────── */
const PhaseBreadcrumb = ({ currentPhase }) => {
  const current = phaseIndex(currentPhase);
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      gap: 0, padding: "8px 24px",
      borderBottom: `1px solid ${C.sidebarBorder}`,
      position: "relative", zIndex: 1, background: "transparent",
    }}>
      {PHASES.map((phase, i) => {
        const done   = i < current;
        const active = i === current;
        const future = i > current;
        return (
          <div key={phase.key} style={{ display: "flex", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%",
                background: done || active ? C.amber : C.muted,
                opacity: future ? 0.4 : 1,
                boxShadow: active ? `0 0 6px ${C.amber}` : "none",
                transition: "all 0.3s ease",
              }}/>
              <span style={{
                fontFamily: sans, fontSize: 11, letterSpacing: "0.06em",
                color: active ? C.amber : done ? C.label : C.muted,
                opacity: future ? 0.5 : 1,
                fontWeight: active ? 600 : 400, transition: "all 0.3s ease",
              }}>
                {phase.label}
              </span>
            </div>
            {i < PHASES.length - 1 && (
              <div style={{
                width: 28, height: 1, margin: "0 10px",
                background: i < current ? C.amber : C.muted,
                opacity: i < current ? 0.5 : 0.25,
                transition: "background 0.3s ease",
              }}/>
            )}
          </div>
        );
      })}
    </div>
  );
};

/* ─── Toast notification ─────────────────────────────────────────────── */
const Toast = ({ message, type = "success", visible }) => (
  <div style={{
    position: "absolute", top: 20, left: "50%",
    transform: `translateX(-50%) translateY(${visible ? 0 : -16}px)`,
    opacity: visible ? 1 : 0, transition: "all 0.3s ease",
    pointerEvents: "none", zIndex: 100,
    background: type === "success" ? C.successBg : C.errorBg,
    border: `1px solid ${type === "success" ? C.successBorder : C.errorBorder}`,
    borderRadius: 10, padding: "8px 18px",
    fontFamily: sans, fontSize: 12.5,
    color: type === "success" ? C.successText : C.errorText,
    whiteSpace: "nowrap", backdropFilter: "blur(4px)",
  }}>
    {message}
  </div>
);

/* ─── Gear suggestion modal ──────────────────────────────────────────── */
//
// Shown after a trip is saved when SaveResponse.gear_suggestions is non-empty.
// Each suggestion is a gear gap the user didn't have — they can check off
// items they actually own and those get added to their gear list via
// POST /api/trip/gear/suggestions.
//
// NOTE: This component calls POST /api/trip/gear/suggestions directly using
// fetch with credentials: "include".  If your app uses Authorization headers
// instead of cookies, replace the fetch call in handleGearConfirm() with
// whatever auth pattern TripContext uses for API calls.
const GearSuggestionModal = ({ suggestions, onConfirm, onDismiss, adding }) => {
  const [selected, setSelected] = useState(
    // Default all to unchecked — user should actively confirm what they own
    new Set()
  );

  const toggle = (category) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(category) ? next.delete(category) : next.add(category);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(suggestions.map(s => s.category)));
  const allSelected = selected.size === suggestions.length;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(61,40,23,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center",
      backdropFilter: "blur(5px)",
      animation: "fadeIn 0.2s ease",
    }}>
      <div style={{
        background: C.sidebar,
        border: `1px solid ${C.sidebarBorder}`,
        borderRadius: 18, padding: "28px 30px 24px",
        width: "100%", maxWidth: 500,
        maxHeight: "82vh", display: "flex", flexDirection: "column",
        boxShadow: "0 24px 60px rgba(61,40,23,0.18)",
      }}>
        {/* Header */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <div style={{
              width: 34, height: 34, borderRadius: "50%",
              background: C.amberDim, border: `1px solid ${C.amberBorder}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16,
            }}>🎒</div>
            <h2 style={{
              fontFamily: serif, fontSize: 19, color: C.heading,
              margin: 0, fontWeight: 400, letterSpacing: "-0.01em",
            }}>
              One more thing before you go
            </h2>
          </div>
          <p style={{
            fontFamily: sans, fontSize: 12.5, color: C.subtext,
            margin: 0, lineHeight: 1.65,
          }}>
            We flagged some gear gaps for this trip. Check off anything you already own
            and we'll add it to your kit — so next time the analysis is more accurate.
          </p>
        </div>

        {/* Select all toggle */}
        <div style={{ marginBottom: 10, display: "flex", justifyContent: "flex-end" }}>
          <button
            onClick={allSelected ? () => setSelected(new Set()) : selectAll}
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontFamily: sans, fontSize: 11.5, color: C.muted,
              padding: "2px 4px", transition: "color 0.15s",
            }}
            onMouseEnter={e => e.currentTarget.style.color = C.label}
            onMouseLeave={e => e.currentTarget.style.color = C.muted}
          >
            {allSelected ? "Deselect all" : "Select all"}
          </button>
        </div>

        {/* Suggestion list */}
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8, marginBottom: 22 }}>
          {suggestions.map(s => {
            const checked = selected.has(s.category);
            return (
              <label key={s.category} style={{
                display: "flex", alignItems: "flex-start", gap: 13,
                background: checked ? C.amberDim : C.fieldBg,
                border: `1px solid ${checked ? C.amberBorder : C.fieldBorder}`,
                borderRadius: 11, padding: "12px 14px",
                cursor: "pointer", transition: "all 0.15s",
                userSelect: "none",
              }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(s.category)}
                  style={{ marginTop: 3, accentColor: C.amber, cursor: "pointer", flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    display: "flex", alignItems: "baseline",
                    justifyContent: "space-between", gap: 8, marginBottom: 3,
                  }}>
                    <span style={{
                      fontFamily: sans, fontSize: 13.5, color: C.heading, fontWeight: 600,
                    }}>
                      {s.display_name}
                    </span>
                    <span style={{
                      fontFamily: mono, fontSize: 10.5, color: C.muted, flexShrink: 0,
                    }}>
                      {s.weight_g}g · ${s.cost % 1 === 0 ? s.cost.toFixed(0) : s.cost.toFixed(2)}
                    </span>
                  </div>
                  <div style={{
                    fontFamily: sans, fontSize: 12, color: C.subtext, lineHeight: 1.5,
                  }}>
                    {s.name}
                  </div>
                  {s.detail && (
                    <div style={{
                      fontFamily: sans, fontSize: 11, color: C.muted,
                      marginTop: 4, lineHeight: 1.4, fontStyle: "italic",
                    }}>
                      {s.detail}
                    </div>
                  )}
                </div>
              </label>
            );
          })}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            onClick={onDismiss}
            disabled={adding}
            style={{
              background: "none",
              border: `1px solid ${C.fieldBorder}`,
              borderRadius: 10, padding: "9px 20px",
              fontFamily: sans, fontSize: 12.5, color: C.muted,
              cursor: adding ? "default" : "pointer",
              transition: "all 0.15s", opacity: adding ? 0.5 : 1,
            }}
            onMouseEnter={e => { if (!adding) e.currentTarget.style.borderColor = C.label; }}
            onMouseLeave={e => { if (!adding) e.currentTarget.style.borderColor = C.fieldBorder; }}
          >
            Skip
          </button>
          <button
            onClick={() => selected.size > 0 && !adding && onConfirm([...selected])}
            disabled={selected.size === 0 || adding}
            style={{
              background: selected.size > 0 && !adding ? C.amber : C.fieldBg,
              border: "none", borderRadius: 10, padding: "9px 22px",
              fontFamily: sans, fontSize: 12.5, fontWeight: 600,
              color: selected.size > 0 && !adding ? C.amberText : C.muted,
              cursor: selected.size > 0 && !adding ? "pointer" : "default",
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { if (selected.size > 0 && !adding) e.currentTarget.style.background = C.amberHover; }}
            onMouseLeave={e => { if (selected.size > 0 && !adding) e.currentTarget.style.background = C.amber; }}
          >
            {adding
              ? "Adding…"
              : selected.size > 0
                ? `Add to my kit (${selected.size})`
                : "Add to my kit"
            }
          </button>
        </div>
      </div>
    </div>
  );
};

/* ─── Suggestion chips ───────────────────────────────────────────────── */
const suggestions = [
  { icon: "🥾", text: "Plan a weekend of hikes" },
  { icon: "🌊", text: "Find an easy trail with a water feature" },
  { icon: "🏞️", text: "Show me a moderate hike under 5 miles" },
  { icon: "🌲", text: "Find a scenic forest trail near me" },
];

/* ─── Rigor (prep-level) badge metadata ──────────────────────────────────── */
// Ordinal prep tier from the backend (rigor.RIGOR_TIERS). The badge tells the
// user at a glance how much a trip demands — casual = "just go", expedition =
// "full kit + consumables" — reinforcing the "easier than a map" goal.
const RIGOR_META = {
  casual:     { label: "Casual",     color: C.successText },
  standard:   { label: "Standard",   color: C.muted },
  serious:    { label: "Serious",    color: C.amber },
  expedition: { label: "Expedition", color: C.errorText },
};

/* ─── Option-card tag curation ───────────────────────────────────────────── */
// The option cards only have room for a few tag chips. Two rules so the chips
// that show are the ones the user cares about:
//   1. Hide ingestion/internal bookkeeping tags — they're noise to a hiker and
//      waste a slot (they'd otherwise sort ahead of real features alphabetically).
//   2. Surface FEATURE tags (lake, waterfall, summit, forest…) ahead of generic
//      terrain/season descriptors, so a hike that genuinely matches "a hike with
//      a lake" shows its `lake` chip instead of truncating it off behind
//      `dem_elevation`/`flat`/`forest`/`full_day` (the bug that made two real
//      lake trails look like non-matches). Stable-sorts within each group.
const HIDDEN_CARD_TAGS = new Set([
  "dem_elevation", "overpass_enriched", "osm_ele",
]);
const FEATURE_CARD_TAGS = new Set([
  "lake", "river", "stream", "waterfall", "pond", "wetland",
  "summit", "viewpoint", "ridge", "meadow", "forest", "beach",
  "cave", "canyon", "wildlife", "historic", "shelter",
]);
function curateCardTags(tags, limit = 4) {
  const visible = (tags || []).filter(t => !HIDDEN_CARD_TAGS.has(t));
  const features = visible.filter(t => FEATURE_CARD_TAGS.has(t));
  const rest     = visible.filter(t => !FEATURE_CARD_TAGS.has(t));
  return [...features, ...rest].slice(0, limit);
}

/* ─── Message bubble ─────────────────────────────────────────────────── */
const Message = ({ msg }) => {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex", flexDirection: isUser ? "row-reverse" : "row",
      gap: 12, marginBottom: 24, animation: "slideUp 0.25s ease",
    }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: "50%",
          border: `1px solid ${C.amberBorder}`, background: C.fieldBg,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, marginTop: 2,
        }}>
          <Logo size={16} />
        </div>
      )}
      <div style={{
        maxWidth: "72%",
        background: isUser ? C.userBubble : C.assistBg,
        border: isUser ? `1px solid ${C.fieldBorder}` : "none",
        borderRadius: isUser ? 16 : 0, borderTopRightRadius: isUser ? 4 : 0,
        padding: isUser ? "10px 16px" : "2px 0",
      }}>
        {!isUser && (
          <div style={{
            fontFamily: sans, fontSize: 11, color: C.amber,
            letterSpacing: "0.08em", textTransform: "uppercase",
            marginBottom: 6, fontWeight: 600,
          }}>
            Trail AI
          </div>
        )}
        <div style={{
          fontFamily: serif, fontSize: 14.5, lineHeight: 1.75,
          color: isUser ? C.heading : "#3d2817", whiteSpace: "pre-wrap",
        }}>
          {msg.content}
        </div>
        {!isUser && (
          <div style={{ display: "flex", gap: 12, marginTop: 10, alignItems: "center" }}>
            {["copy","thumb-up","thumb-down","refresh"].map(action => (
              <button key={action} title={action}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  padding: "4px 6px", borderRadius: 6,
                  color: C.muted, fontSize: 13, fontFamily: sans, transition: "color 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.color = C.label}
                onMouseLeave={e => e.currentTarget.style.color = C.muted}
              >
                {action === "copy" ? "⎘" : action === "thumb-up" ? "↑" : action === "thumb-down" ? "↓" : "↺"}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Inline gear-entry "blip" form (gear_review) ─────────────────────────── */
// Styled as a margin note in the field journal, not an app form: a left ink
// rule, fill-in-the-blank underline inputs in the reading serif, ink-tag chips,
// and an understated "add it" link.
const serifBody = "'Spectral', Georgia, serif";

const GearLevelChip = ({ label, selected, disabled, onClick }) => (
  <button onClick={disabled ? undefined : onClick} disabled={disabled}
    title={disabled ? "Below what this trail calls for" : undefined}
    style={{
      padding: "5px 11px", borderRadius: 5,
      cursor: disabled ? "not-allowed" : "pointer",
      fontFamily: sans, fontSize: 11.5, fontWeight: selected ? 600 : 400,
      background: selected ? C.amberDim : "transparent",
      border: `1px solid ${selected ? C.amber : C.fieldBorder}`,
      color: disabled ? C.muted : (selected ? C.amber : C.subtext),
      opacity: disabled ? 0.45 : 1, transition: "all 0.15s",
    }}>
    {label}
  </button>
);

// Underline "fill-in-the-blank" input — writing on a ruled line.
const journalLineStyle = {
  background: "transparent", border: "none", borderRadius: 0,
  borderBottom: `1.5px solid ${C.fieldBorder}`, padding: "5px 2px",
  color: C.heading, fontFamily: serifBody, fontSize: 13.5, outline: "none",
  boxSizing: "border-box",
};
const lineFocus = (e) => { e.target.style.borderBottomColor = C.amber; };
const lineBlur  = (e) => { e.target.style.borderBottomColor = C.fieldBorder; };

// Rendered under an assistant message when Groq emitted a GEAR ADD signal.
// Reuses the gear-page vocabulary (GEAR_SECTIONS): a level-chip row with the
// minimum acceptable level preselected and lower levels disabled ("do more,
// never less"), an optional temp input for sleep, and a name field. Non-binding
// — the user can ignore it and keep chatting. On submit it persists to their
// global kit and syncs the session so the AI won't re-flag the gap.
const GearPromptForm = ({ prompt, onAdd }) => {
  const gearCategory = prompt.gear_category || toGearCategory(prompt.category);
  const section = GEAR_SECTION_BY_KEY[gearCategory];
  const levels  = Array.isArray(section?.levels) ? section.levels : null;
  const minIdx  = levels && prompt.min_level
    ? levels.findIndex(l => l.value === prompt.min_level)
    : -1;

  // Preselect the minimum acceptable level (the user may go higher, not lower).
  const [level, setLevel] = useState(minIdx >= 0 ? levels[minIdx].value : null);
  const [name,  setName]  = useState("");
  const [temp,  setTemp]  = useState(prompt.min_temp_f != null ? String(prompt.min_temp_f) : "");
  const [busy,  setBusy]  = useState(false);
  const [error, setError] = useState(null);

  // Unmappable category (e.g. trekking_poles → misc, not a create_user_gear
  // category): render nothing rather than a form that would fail to submit.
  if (!section) return null;
  const isSleep = !!section.sleepTemp;
  const canAdd  = !busy && (!levels || level !== null);

  const submit = async () => {
    if (!canAdd) return;
    const payload = {
      category:      prompt.category,
      gear_category: gearCategory,
      name:          name.trim(),
      level:         levels ? level : null,
    };
    if (isSleep && temp !== "") {
      const t = Number(temp);
      if (!Number.isNaN(t)) payload.temp_rating_f = t;
    }
    setBusy(true); setError(null);
    try {
      await onAdd(payload);   // on success chat.plan drops the gap → this form un-renders
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
      setBusy(false);
    }
  };

  return (
    <div style={{ margin: "2px 0 16px 44px", maxWidth: 440,
      padding: "8px 0 10px 14px", borderLeft: `2px solid ${C.amberBorder}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginBottom: 8 }}>
        <span style={{ fontSize: 14 }}>{section.icon}</span>
        <span style={{ fontFamily: serifBody, fontStyle: "italic", fontSize: 13.5, color: C.subtext }}>
          {section.label.toLowerCase()}
        </span>
      </div>

      {levels && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: minIdx > 0 ? 6 : 10 }}>
          {levels.map((l, i) => (
            <GearLevelChip key={l.value} label={l.label}
              selected={level === l.value}
              disabled={minIdx >= 0 && i < minIdx}
              onClick={() => setLevel(l.value)} />
          ))}
        </div>
      )}
      {minIdx > 0 && (
        <div style={{ fontFamily: serifBody, fontStyle: "italic", fontSize: 11.5, color: C.muted, marginBottom: 10 }}>
          at least {levelLabelFor(gearCategory, prompt.min_level)} for this one.
        </div>
      )}

      {isSleep && (
        <input type="number" value={temp} onChange={e => setTemp(e.target.value)}
          onFocus={lineFocus} onBlur={lineBlur}
          placeholder="temp rating °F"
          style={{ ...journalLineStyle, width: 150, marginBottom: 10 }} />
      )}

      <div style={{ display: "flex", alignItems: "flex-end", gap: 14 }}>
        <input value={name} onChange={e => setName(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") submit(); }}
          onFocus={lineFocus} onBlur={lineBlur}
          placeholder="name it, if you like"
          style={{ ...journalLineStyle, flex: 1, minWidth: 0 }} />
        <button onClick={submit} disabled={!canAdd}
          style={{ background: "transparent", border: "none", padding: "4px 2px", flexShrink: 0,
            color: canAdd ? C.amber : C.muted, fontFamily: sans, fontSize: 12.5, fontWeight: 600,
            letterSpacing: "0.03em", textDecoration: "underline", textUnderlineOffset: 3,
            cursor: canAdd ? "pointer" : "default" }}>
          {busy ? "adding…" : "add it"}
        </button>
      </div>
      {error && (
        <div style={{ fontFamily: serifBody, fontStyle: "italic", fontSize: 11.5, color: C.errorText, marginTop: 7 }}>
          {error}
        </div>
      )}
    </div>
  );
};

/* ─── Hike option cards ───────────────────────────────────────────────── */
// Renders the structured hike options (ChatResponse.hike_options) as
// clickable cards instead of the old plain-text numbered list. Clicking a
// card sends the same 1-based index a typed number would — the backend's
// selection logic (PhaseController.extract_hike_selection) is unchanged.
const HikeOptionCards = ({ options, onPick }) => {
  if (!options?.length) return null;
  // No onPick → read-only record of an earlier offer (a hike is already
  // selected). Render the same cards, dimmed and non-interactive.
  const interactive = typeof onPick === "function";
  return (
    <div style={{
      display: "grid", gap: 10, marginBottom: 24,
      gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))",
      animation: "slideUp 0.25s ease",
      opacity: interactive ? 1 : 0.5,
    }}>
      {options.map((opt) => (
        <button
          key={opt.index}
          onClick={interactive ? () => onPick(opt) : undefined}
          disabled={!interactive}
          style={{
            textAlign: "left", cursor: interactive ? "pointer" : "default",
            background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
            borderRadius: 12, padding: "14px 16px",
            transition: "all 0.15s",
            display: "flex", flexDirection: "column", gap: 6,
          }}
          onMouseEnter={e => { if (interactive) { e.currentTarget.style.borderColor = C.amber; e.currentTarget.style.background = C.amberDim; } }}
          onMouseLeave={e => { if (interactive) { e.currentTarget.style.borderColor = C.fieldBorder; e.currentTarget.style.background = C.fieldBg; } }}
        >
          <div style={{ fontFamily: sans, fontSize: 13.5, fontWeight: 600, color: C.heading }}>
            {opt.name}
          </div>
          <div style={{ fontFamily: sans, fontSize: 11.5, color: C.subtext }}>
            {[
              opt.length_km != null ? `${opt.length_km} km` : null,
              opt.difficulty || null,
              opt.elevation_gain_m != null ? `${Math.round(opt.elevation_gain_m)} m gain` : null,
            ].filter(Boolean).join(" · ")}
          </div>
          {RIGOR_META[opt.rigor_tier] && (
            <div>
              <span style={{
                fontFamily: sans, fontSize: 10, fontWeight: 600, letterSpacing: 0.4,
                textTransform: "uppercase", color: RIGOR_META[opt.rigor_tier].color,
                background: C.amberDim, border: `1px solid ${C.amberBorder}`,
                borderRadius: 999, padding: "2px 8px",
              }}>
                {RIGOR_META[opt.rigor_tier].label} prep
              </span>
            </div>
          )}
          {(opt.distance_km != null || opt.state) && (
            <div style={{ fontFamily: sans, fontSize: 11, color: C.muted }}>
              {[
                opt.distance_km != null
                  ? `${opt.distance_km.toFixed(0)} km ${opt.distance_anchor ? `from ${opt.distance_anchor}` : "away"}`
                  : null,
                opt.state || null,
              ].filter(Boolean).join(", ")}
            </div>
          )}
          {opt.tags?.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 2 }}>
              {curateCardTags(opt.tags).map(tag => (
                <span key={tag} style={{
                  fontFamily: sans, fontSize: 10, color: C.label,
                  background: C.amberDim, border: `1px solid ${C.amberBorder}`,
                  borderRadius: 999, padding: "2px 8px",
                }}>
                  {tag.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
          {opt.gear_summary && (
            <div style={{
              fontFamily: sans, fontSize: 11, marginTop: 2,
              // Red only for an actual gap ("missing:" / "worth noting:"); the
              // casual nudge and "kit looks solid" read as reassurance, not alarm.
              color: /^(missing|worth noting):/.test(opt.gear_summary) ? C.errorText : C.successText,
            }}>
              {opt.gear_summary}
            </div>
          )}
        </button>
      ))}
    </div>
  );
};

/* ─── Chat status badge ──────────────────────────────────────────────── */
// Accessibility: every state pairs its color with an icon + text label —
// never color alone (matters most for "reviewed", which would otherwise
// just be "the green one").
const CHAT_STATUS_META = {
  active:    { label: "In progress",     icon: "●", color: "#a83b2c" },
  saved:     { label: "Upcoming",        icon: "◐", color: "#6a4a26" },
  completed: { label: "Awaiting review", icon: "○", color: "#6a4a26" },
  reviewed:  { label: "Reviewed",        icon: "✓", color: "#7a6236" },
};

const StatusBadge = ({ status, size = 11, color }) => {
  const meta = CHAT_STATUS_META[status] || CHAT_STATUS_META.saved;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontFamily: sans, fontSize: size, color: color || meta.color, fontWeight: 600,
    }}>
      <span aria-hidden="true">{meta.icon}</span>
      <span>{meta.label}</span>
    </span>
  );
};

/* ─── Read-only trip view ────────────────────────────────────────────── */
// Rendered instead of the live chat thread for saved/completed/reviewed
// chats. There's no stored message transcript for these (planning already
// finished and the Redis session is gone) — this recaps the structured
// trip data GET /chats/:id returns, same information the finalize-phase
// summary showed at save time.
const ReadOnlyTripView = ({ trip, onMarkDone, marking, onCancel, cancelling, onOpenReview, onGoAgain, duplicating }) => {
  const stop = trip.stops?.[0];
  const trail = stop?.trail_data || {};
  const days = stop?.itinerary?.days || [];
  const completion = trip.completion;

  // Real trail stats (metric, from the DB at selection) → imperial for display.
  // These are authoritative; the per-day itinerary figures below are the LLM's.
  const distanceMi = trail.length_km != null ? (trail.length_km / 1.60934).toFixed(1) : null;
  const gainFt     = trail.elevation_gain_m != null ? Math.round(trail.elevation_gain_m * 3.28084) : null;
  // Prefer the on-trail time estimate over the calendar-day span — a 3.4 km
  // trail is "~45 min", not "1 day".
  const durationLabel = trail.estimated_duration
    || (stop?.duration_days ? `${stop.duration_days} day${stop.duration_days !== 1 ? "s" : ""}` : null);

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "32px 24px" }}>
      <div style={{ maxWidth: 680, width: "100%", margin: "0 auto" }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginBottom: 18, gap: 12, flexWrap: "wrap",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h2 style={{ fontFamily: serif, fontSize: 22, fontWeight: "normal", color: C.heading, margin: 0 }}>
              {trip.title}
            </h2>
            <StatusBadge status={trip.status} size={12} />
          </div>

          {trip.status === "saved" && (
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={onMarkDone} disabled={marking || cancelling}
                style={{
                  padding: "8px 16px", borderRadius: 9, cursor: (marking || cancelling) ? "default" : "pointer",
                  background: C.amber, border: "none", color: C.amberText,
                  fontFamily: sans, fontSize: 12.5, fontWeight: 600, opacity: (marking || cancelling) ? 0.7 : 1,
                }}
              >
                {marking ? "Marking…" : "Mark as done"}
              </button>
              <button onClick={onCancel} disabled={marking || cancelling}
                title="Remove this trip — you've decided not to go"
                style={{
                  padding: "8px 16px", borderRadius: 9, cursor: (marking || cancelling) ? "default" : "pointer",
                  background: "none", border: `1px solid ${C.fieldBorder}`, color: C.muted,
                  fontFamily: sans, fontSize: 12.5, fontWeight: 600, opacity: (marking || cancelling) ? 0.6 : 1,
                }}
                onMouseEnter={e => { if (!marking && !cancelling) { e.currentTarget.style.borderColor = C.errorBorder; e.currentTarget.style.color = C.errorText; } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.fieldBorder; e.currentTarget.style.color = C.muted; }}
              >
                {cancelling ? "Removing…" : "Not going"}
              </button>
            </div>
          )}

          {trip.status === "completed" && (
            <button onClick={onOpenReview}
              style={{
                padding: "8px 16px", borderRadius: 9, cursor: "pointer",
                background: C.amber, border: "none", color: C.amberText,
                fontFamily: sans, fontSize: 12.5, fontWeight: 600,
              }}
            >
              Write a review
            </button>
          )}

          {(trip.status === "completed" || trip.status === "reviewed") && (
            <button onClick={onGoAgain} disabled={duplicating}
              title="Re-run this search against current trail data — not a replay of the original results"
              style={{
                padding: "8px 16px", borderRadius: 9, cursor: duplicating ? "default" : "pointer",
                background: "#ccb98f", border: `1px solid ${C.fieldBorder}`,
                color: C.label, fontFamily: sans, fontSize: 12.5, fontWeight: 600,
                opacity: duplicating ? 0.7 : 1,
              }}
            >
              {duplicating ? "Searching…" : "Go again"}
            </button>
          )}
        </div>

        {completion && (
          <div style={{
            background: C.amberDim, border: `1px solid ${C.amberBorder}`,
            borderRadius: 14, padding: "16px 22px", marginBottom: 18,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: completion.notes ? 8 : 0 }}>
              <div style={{ fontFamily: sans, fontSize: 11, color: C.label, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
                Your review
              </div>
              {completion.rating && (
                <div style={{ color: C.amber, fontSize: 14 }}>
                  {"★".repeat(completion.rating)}{"☆".repeat(5 - completion.rating)}
                </div>
              )}
            </div>
            {!completion.went && (
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.subtext }}>Marked as not attended.</div>
            )}
            {completion.difficulty_felt && (
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.subtext, textTransform: "capitalize" }}>
                Felt: {completion.difficulty_felt.toLowerCase()}
                {trail.difficulty && trail.difficulty.toLowerCase() !== completion.difficulty_felt.toLowerCase()
                  ? ` (predicted ${trail.difficulty.toLowerCase()})` : ""}
              </div>
            )}
            {completion.elevation_felt && (
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.subtext }}>{completion.elevation_felt}</div>
            )}
            {completion.notes && (
              <div style={{ fontFamily: serif, fontSize: 13, color: C.subtext, fontStyle: "italic", marginTop: 6 }}>
                “{completion.notes}”
              </div>
            )}
          </div>
        )}

        <div style={{
          background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
          borderRadius: 14, padding: "18px 22px", marginBottom: 18,
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 14,
        }}>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Destination</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3 }}>{stop?.destination || "—"}</div>
          </div>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Time on trail</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3 }}>
              {durationLabel || "—"}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Distance</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3 }}>
              {distanceMi != null ? `${distanceMi} mi` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Elevation gain</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3 }}>
              {gainFt != null ? `${gainFt} ft` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Difficulty</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3, textTransform: "capitalize" }}>
              {trail.difficulty || "—"}
            </div>
          </div>
          <div>
            <div style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>Gear packed</div>
            <div style={{ fontFamily: sans, fontSize: 13.5, color: C.heading, marginTop: 3 }}>
              {trip.gear?.length ? `${trip.gear.length} item${trip.gear.length !== 1 ? "s" : ""}` : "None recorded"}
            </div>
          </div>
        </div>

        {/* Trail readiness — live per-category check of the user's kit vs what
            THIS trail needs (computed server-side in GET /chats/:id). */}
        {Array.isArray(trip.readiness) && trip.readiness.length > 0 && (
          <div style={{
            background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
            borderRadius: 14, padding: "18px 22px", marginBottom: 18,
          }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12, gap: 10, flexWrap: "wrap" }}>
              <div style={{ fontFamily: sans, fontSize: 11, color: C.label, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
                Trail readiness
              </div>
              {(() => {
                const missing = trip.readiness.filter(r => r.status === "missing").length;
                return (
                  <div style={{ fontFamily: sans, fontSize: 11.5, color: missing > 0 ? C.errorText : C.successText }}>
                    {missing > 0
                      ? `${missing} essential${missing !== 1 ? "s" : ""} to sort before you go`
                      : `Set on all ${trip.readiness.length} — you're good to go`}
                  </div>
                );
              })()}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {trip.readiness.map(r => {
                const meta = {
                  ok:      { icon: "✓", color: C.successText },
                  missing: { icon: "✗", color: C.errorText },
                  flag:    { icon: "!", color: C.amber },
                }[r.status] || { icon: "•", color: C.muted };
                const title = r.label.charAt(0).toUpperCase() + r.label.slice(1);
                return (
                  <div key={r.category} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span aria-hidden="true" style={{
                      flexShrink: 0, marginTop: 1, width: 17, height: 17, borderRadius: "50%",
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      fontSize: 11, fontWeight: 700, color: meta.color,
                      background: `${meta.color}22`, border: `1px solid ${meta.color}55`,
                    }}>{meta.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontFamily: sans, fontSize: 13, color: C.heading }}>
                        {title}
                        {r.required && (
                          <span style={{ color: C.muted, fontWeight: 400 }}>{`  ·  needs ${r.required}`}</span>
                        )}
                        {r.status !== "ok" && r.importance === "recommended" && (
                          <span style={{ color: C.muted, fontSize: 11 }}>{"  (recommended)"}</span>
                        )}
                      </div>
                      {r.note && r.status !== "ok" && (
                        <div style={{ fontFamily: serif, fontSize: 12, color: C.subtext, marginTop: 1 }}>
                          {r.note}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {days.length > 0 && (
          <div style={{
            background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
            borderRadius: 14, padding: "18px 22px", marginBottom: 18,
          }}>
            <div style={{ fontFamily: sans, fontSize: 11, color: C.label, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12, fontWeight: 600 }}>
              Itinerary
            </div>
            {days.map(day => (
              <div key={day.day_number} style={{ marginBottom: 10 }}>
                <div style={{ fontFamily: sans, fontSize: 13, color: C.heading }}>
                  Day {day.day_number}: {day.title}
                  {(day.distance_miles || day.elevation_gain_ft) && (
                    <span style={{ color: C.subtext, fontWeight: 400 }}>
                      {" — "}
                      {[
                        day.distance_miles ? `${day.distance_miles} mi` : null,
                        day.elevation_gain_ft ? `${day.elevation_gain_ft} ft gain` : null,
                      ].filter(Boolean).join(", ")}
                    </span>
                  )}
                </div>
                {day.notes && (
                  <div style={{ fontFamily: serif, fontSize: 12.5, color: C.subtext, marginTop: 2 }}>{day.notes}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {trip.goal && (
          <p style={{ fontFamily: serif, fontSize: 13, color: C.subtext, fontStyle: "italic", lineHeight: 1.6 }}>
            {trip.goal}
          </p>
        )}
      </div>
    </div>
  );
};

/* ─── Review questionnaire modal ─────────────────────────────────────── */
// Single screen, non-blocking (the dismissible needs_review banner is what
// invites the user here — this modal itself just has to exist somewhere to
// go to). went/didn't go, difficulty felt, optional elevation/conditions
// notes, 1-5 rating, optional free text. POST /chats/:id/review on submit.
const DIFFICULTY_OPTIONS = ["EASY", "MODERATE", "DIFFICULT", "EXPERT"];

const ReviewModal = ({ trip, onSubmit, onClose, submitting }) => {
  const [went,           setWent]           = useState(true);
  const [difficultyFelt, setDifficultyFelt] = useState(null);
  const [elevationFelt,  setElevationFelt]  = useState("");
  const [rating,         setRating]         = useState(0);
  const [notes,          setNotes]          = useState("");

  const handleSubmit = () => {
    if (submitting) return;
    onSubmit({
      went,
      difficulty_felt: went ? difficultyFelt : null,
      elevation_felt:  elevationFelt.trim() || null,
      rating:          rating > 0 ? rating : null,
      notes:           notes.trim() || null,
    });
  };

  const pillStyle = (active) => ({
    padding: "8px 16px", borderRadius: 9, cursor: "pointer",
    background: active ? C.amberDim : C.fieldBg,
    border: `1px solid ${active ? C.amberBorder : C.fieldBorder}`,
    color: active ? C.amberText : C.label,
    fontFamily: sans, fontSize: 12.5, fontWeight: active ? 600 : 400,
    transition: "all 0.15s",
  });

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(61,40,23,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center",
      backdropFilter: "blur(5px)",
      animation: "fadeIn 0.2s ease",
    }}>
      <div style={{
        background: C.sidebar,
        border: `1px solid ${C.sidebarBorder}`,
        borderRadius: 18, padding: "28px 30px 24px",
        width: "100%", maxWidth: 460,
        maxHeight: "85vh", overflowY: "auto",
        boxShadow: "0 24px 60px rgba(61,40,23,0.18)",
      }}>
        <h2 style={{ fontFamily: serif, fontSize: 19, color: C.heading, margin: "0 0 4px", fontWeight: 400 }}>
          How was {trip.title}?
        </h2>
        <p style={{ fontFamily: sans, fontSize: 12.5, color: C.subtext, margin: "0 0 20px" }}>
          Takes a minute — helps us get gear and difficulty right next time.
        </p>

        {/* Went? */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontFamily: sans, fontSize: 11.5, color: C.label, marginBottom: 8, fontWeight: 600 }}>Did you go?</div>
          <div style={{ display: "flex", gap: 8 }}>
            <button style={pillStyle(went === true)} onClick={() => setWent(true)}>Yes, I went</button>
            <button style={pillStyle(went === false)} onClick={() => setWent(false)}>Didn't make it</button>
          </div>
        </div>

        {went && (
          <>
            {/* Difficulty felt */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontFamily: sans, fontSize: 11.5, color: C.label, marginBottom: 8, fontWeight: 600 }}>
                Difficulty felt (vs. predicted)
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {DIFFICULTY_OPTIONS.map(d => (
                  <button key={d} style={pillStyle(difficultyFelt === d)} onClick={() => setDifficultyFelt(d)}>
                    {d.charAt(0) + d.slice(1).toLowerCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Rating */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontFamily: sans, fontSize: 11.5, color: C.label, marginBottom: 8, fontWeight: 600 }}>Rating</div>
              <div style={{ display: "flex", gap: 4 }}>
                {[1, 2, 3, 4, 5].map(n => (
                  <button key={n} onClick={() => setRating(n === rating ? 0 : n)}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 24, lineHeight: 1, padding: 2,
                      color: n <= rating ? C.amber : C.muted, transition: "color 0.15s",
                    }}
                    aria-label={`${n} star${n !== 1 ? "s" : ""}`}
                  >★</button>
                ))}
              </div>
            </div>

            {/* Elevation / conditions */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontFamily: sans, fontSize: 11.5, color: C.label, marginBottom: 8, fontWeight: 600 }}>
                Elevation / conditions <span style={{ color: C.muted, fontWeight: 400 }}>(optional)</span>
              </div>
              <input
                value={elevationFelt}
                onChange={e => setElevationFelt(e.target.value)}
                placeholder="e.g. muddier than expected, gain felt steeper…"
                style={{
                  width: "100%", boxSizing: "border-box", padding: "9px 12px",
                  background: C.inputBg, border: `1px solid ${C.inputBorder}`,
                  borderRadius: 9, color: C.heading, fontFamily: sans, fontSize: 12.5,
                }}
              />
            </div>
          </>
        )}

        {/* Notes */}
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontFamily: sans, fontSize: 11.5, color: C.label, marginBottom: 8, fontWeight: 600 }}>
            Notes <span style={{ color: C.muted, fontWeight: 400 }}>(optional)</span>
          </div>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder="Anything else worth remembering for next time?"
            style={{
              width: "100%", boxSizing: "border-box", padding: "9px 12px",
              background: C.inputBg, border: `1px solid ${C.inputBorder}`,
              borderRadius: 9, color: C.heading, fontFamily: sans, fontSize: 12.5,
              resize: "vertical",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} disabled={submitting}
            style={{
              background: "none", border: `1px solid ${C.fieldBorder}`,
              borderRadius: 10, padding: "9px 20px",
              fontFamily: sans, fontSize: 12.5, color: C.muted,
              cursor: submitting ? "default" : "pointer", opacity: submitting ? 0.5 : 1,
            }}
          >
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={submitting}
            style={{
              background: C.amber, border: "none", borderRadius: 10, padding: "9px 22px",
              fontFamily: sans, fontSize: 12.5, fontWeight: 600, color: C.amberText,
              cursor: submitting ? "default" : "pointer", opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Saving…" : "Submit review"}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ─── Needs-review banner ────────────────────────────────────────────── */
// Dismissible, never a gate — the background job flips needs_review N days
// after "Mark as done"; this just surfaces it. Dismissal persists in
// localStorage per chat id so it doesn't reappear every reload, but the
// trip itself stays "completed" (not silently marked reviewed) until the
// user actually submits the questionnaire.
const NeedsReviewBanner = ({ items, onReview, onDismiss }) => {
  if (!items.length) return null;
  const item = items[0];
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      gap: 12, padding: "10px 20px",
      background: C.amberDim, borderBottom: `1px solid ${C.amberBorder}`,
      fontFamily: sans, fontSize: 12.5, color: C.label,
      position: "relative", zIndex: 1,
    }}>
      <span>
        How was <strong style={{ color: C.heading }}>{item.title}</strong>? A quick review helps get gear and difficulty right next time.
        {items.length > 1 && ` (+${items.length - 1} more waiting)`}
      </span>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={() => onReview(item)}
          style={{ background: C.amber, border: "none", borderRadius: 8, padding: "5px 12px", color: C.amberText, fontFamily: sans, fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}
        >
          Review now
        </button>
        <button onClick={() => onDismiss(item.id)} title="Dismiss"
          style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", fontSize: 14, padding: "2px 6px", lineHeight: 1 }}
        >
          ✕
        </button>
      </div>
    </div>
  );
};

/* ─── Welcome view ───────────────────────────────────────────────────── */
const WelcomeView = ({ onSend, serviceReady }) => (
  <div style={{
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    padding: "40px 24px", animation: "fadeIn 0.4s ease",
  }}>
    <div style={{ marginBottom: 16 }}><Logo size={48} /></div>
    <h1 style={{
      fontFamily: serif, fontSize: 32, fontWeight: 400, color: C.heading,
      textAlign: "center", margin: "0 0 10px", letterSpacing: "-0.02em",
    }}>
      Plan your next adventure
    </h1>
    <p style={{
      fontFamily: sans, fontSize: 14, color: C.subtext, textAlign: "center",
      margin: "0 0 40px", maxWidth: 380, lineHeight: 1.6,
    }}>
      {serviceReady === false
        ? "AI service is unavailable right now. Please try again later."
        : "AI-powered trip planning with your gear, your pace, your terrain."
      }
    </p>
    {serviceReady !== false && (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, maxWidth: 520, width: "100%" }}>
        {suggestions.map((s, i) => (
          <button key={i} onClick={() => onSend(s.text)}
            style={{
              background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
              borderRadius: 12, padding: "12px 16px",
              textAlign: "left", cursor: "pointer", transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = C.amber; e.currentTarget.style.background = C.amberDim; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = C.fieldBorder; e.currentTarget.style.background = C.fieldBg; }}
          >
            <div style={{ fontSize: 18, marginBottom: 5 }}>{s.icon}</div>
            <div style={{ fontFamily: sans, fontSize: 12.5, color: C.label, lineHeight: 1.5 }}>{s.text}</div>
          </button>
        ))}
      </div>
    )}
  </div>
);

/* ─── Main component ─────────────────────────────────────────────────── */
export default function TripPlanner() {

  const {
    chat,
    sendMessage:  sendChatMessage,
    addGearFromChat,
    resetChat,
    clearError,
    checkServiceHealth,
    activeTrip,
    loading,
    error,
    chatList,
    readOnlyChat,
    loadChatList,
    openChat,
    markChatCompleted,
    submitChatReview,
    duplicateChat,
    cancelChat,
  } = useTrip();

  const { messages, phase, serviceReady } = chat;
  const { user, refreshItems } = useUser();

  // Persist an item from an inline gear-review form, then re-pull the user's kit
  // so the gear page reflects it. addGearFromChat also clears the resolved gap
  // from chat.plan (which un-renders the form) and appends the AI's confirmation.
  const handleGearAdd = async (payload) => {
    const data = await addGearFromChat(payload);
    if (user?.id) { try { await refreshItems(user.id); } catch { /* best-effort */ } }
    return data;
  };
  const location = useLocation();
  const navigate = useNavigate();
  // ── Local UI state ────────────────────────────────────────────────────────
  const [input,          setInput]          = useState("");
  const [sidebarOpen,    setSidebarOpen]    = useState(true);
  const [savedToast,     setSavedToast]     = useState(false);
  // Best-effort browser GPS, used to resolve "near me" chat queries. Populated
  // silently on mount; falls back to the user's saved home_location on send.
  const [userLocation,   setUserLocation]   = useState({ lat: null, lng: null });
  // Mark-as-done / review questionnaire state
  const [marking,          setMarking]          = useState(false);
  const [cancelling,       setCancelling]       = useState(false);
  const [reviewModalOpen,  setReviewModalOpen]  = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [duplicating,      setDuplicating]      = useState(false);
  const [dismissedReviewIds, setDismissedReviewIds] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(DISMISSED_REVIEW_KEY) || "[]")); }
    catch { return new Set(); }
  });
  // Gear suggestion modal state
  const [gearModal,      setGearModal]      = useState(false);
  const [gearSuggestions,setGearSuggestions]= useState([]);
  const [gearAdding,     setGearAdding]     = useState(false);
  const [gearAddedToast, setGearAddedToast] = useState(false);

  const endRef   = useRef(null);
  const inputRef = useRef(null);
  const seededRef = useRef(false);

  // ── On mount: health check + chat history ─────────────────────────────────
  useEffect(() => {
    clearError();          // drop any stale error banner (e.g. a 429 from a prior account)
    checkServiceHealth();
    loadChatList();
  }, [clearError, checkServiceHealth, loadChatList]);

  // ── Trip saved — show toast and gear modal if suggestions exist ───────────
  //
  // TripContext sets activeTrip from the full SaveResponse after a successful
  // POST /api/trip/save.  If TripContext passes gear_suggestions through (add
  // it to whichever setActiveTrip call lives in TripContext), this will
  // auto-open the gear modal when there are items to suggest.
  //
  // If activeTrip doesn't yet include gear_suggestions, the modal simply won't
  // open — no error — until TripContext is updated to forward that field.
  useEffect(() => {
    if (!activeTrip) return;

    setSavedToast(true);
    const toastTimer = setTimeout(() => setSavedToast(false), 3500);

    const suggestions = activeTrip.gear_suggestions ?? [];
    if (suggestions.length > 0) {
      // Slight delay so the save toast reads first before the modal appears
      const modalTimer = setTimeout(() => {
        setGearSuggestions(suggestions);
        setGearModal(true);
      }, 600);
      return () => { clearTimeout(toastTimer); clearTimeout(modalTimer); };
    }

    return () => clearTimeout(toastTimer);
  }, [activeTrip?.trip_id]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ── Send a message ────────────────────────────────────────────────────────
  const sendMessage = async (text) => {
    const content = (text || input).trim();
    if (!content || loading || serviceReady === false) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    const lat = userLocation.lat ?? user?.home_location?.lat ?? null;
    const lng = userLocation.lng ?? user?.home_location?.lon ?? null;
    try {
      await sendChatMessage(content, lat, lng);
    } catch { /* send errors surface via chat context state */ }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  // ── Seeded draft (e.g. "Plan a trip to X" from a hike detail page) ────────
  // Consume a router-state draft once: start a fresh session and PRE-FILL the
  // composer with the message (crafted to hit the name lookup) without sending —
  // the user reviews it and hits send. Clear the state so a refresh / back-nav
  // doesn't re-fill it.
  // Mount-only: reading location.state here (not in deps) is deliberate — the
  // navigate() below clears it, and we must NOT let that re-run this effect
  // (its cleanup would cancel the pending prefill before it lands).
  useEffect(() => {
    const draft = location.state?.draftMessage;
    if (!draft || seededRef.current) return;
    seededRef.current = true;
    resetChat();
    setInput(draft);
    // Clear the router state so a refresh / back-nav doesn't re-fill it.
    navigate(location.pathname, { replace: true, state: {} });
    // Size + focus the composer after the draft has painted.
    const raf = requestAnimationFrame(() => {
      const el = inputRef.current;
      if (el) {
        el.focus();
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 160) + "px";
      }
    });
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Location ──────────────────────────────────────────────────────────────
  // Best-effort, silent: grab the browser's GPS once on mount so "near me"
  // chat queries can be resolved. If denied/unavailable we simply fall back to
  // the user's saved home_location in sendMessage.
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setUserLocation({ lat: coords.latitude, lng: coords.longitude }),
      () => {},
    );
  }, []);

  // ── Gear suggestion handlers ──────────────────────────────────────────────

  const handleGearConfirm = async (selectedCategories) => {
    if (selectedCategories.length === 0) {
      setGearModal(false);
      setGearSuggestions([]);
      return;
    }

    setGearAdding(true);
    try {
      await Promise.all(
        selectedCategories.map((category) => {
          const suggestion = gearSuggestions.find(s => s.category === category);
          if (!suggestion || !user) return Promise.resolve();
          // Add the suggested item to the user's kit (creates + links). The old
          // createItem() made an orphan catalog row that was never tied to the
          // user; createUserGear is the stage-2 category-based add.
          return createUserGear(user.id, {
            name:          suggestion.name || suggestion.display_name || category,
            gear_category: toGearCategory(suggestion.category),
            weight:        suggestion.weight_g ?? 0,
            cost:          suggestion.cost ?? 0,
          });
        })
      );
      setGearAddedToast(true);
      setTimeout(() => setGearAddedToast(false), 3000);
    } catch (err) {
      console.warn("Gear suggestion add failed:", err);
    } finally {
      setGearAdding(false);
      setGearModal(false);
      setGearSuggestions([]);
    }
  };

  const handleGearDismiss = () => {
    if (gearAdding) return;   // prevent dismiss mid-request
    setGearModal(false);
    setGearSuggestions([]);
  };

  // ── Derived ───────────────────────────────────────────────────────────────
  const hasMessages  = messages.length > 0;
  const inputBlocked = loading || serviceReady === false;
  const activeChatId = readOnlyChat?.id ?? (chat.sessionId || null);

  const chatGroups = [
    { key: "planning",  label: "Planning",   items: chatList.filter(c => c.status === "active") },
    { key: "upcoming",  label: "Upcoming",   items: chatList.filter(c => c.status === "saved") },
    { key: "past",      label: "Past hikes", items: chatList.filter(c => c.status === "completed" || c.status === "reviewed") },
  ];

  const needsReviewItems = chatList.filter(
    c => c.status === "completed" && c.needs_review && !dismissedReviewIds.has(c.id)
  );

  const handleOpenChat = (chatId) => {
    openChat(chatId).catch(() => {});
  };

  const handleMarkDone = async () => {
    if (!readOnlyChat) return;
    setMarking(true);
    try {
      await markChatCompleted(readOnlyChat.id);
    } catch {
      // error surfaced via context's `error` state already
    } finally {
      setMarking(false);
    }
  };

  const handleCancel = async () => {
    if (!readOnlyChat || cancelling) return;
    if (!window.confirm(`Remove "${readOnlyChat.title}"? This can't be undone.`)) return;
    setCancelling(true);
    try {
      await cancelChat(readOnlyChat.id);
    } catch {
      // error surfaced via context's `error` state
    } finally {
      setCancelling(false);
    }
  };

  const handleSubmitReview = async (payload) => {
    if (!readOnlyChat) return;
    setReviewSubmitting(true);
    try {
      await submitChatReview(readOnlyChat.id, payload);
      setReviewModalOpen(false);
    } catch {
      // error surfaced via context's `error` state; keep modal open to retry
    } finally {
      setReviewSubmitting(false);
    }
  };

  const dismissReviewNudge = (chatId) => {
    setDismissedReviewIds(prev => {
      const next = new Set(prev);
      next.add(chatId);
      localStorage.setItem(DISMISSED_REVIEW_KEY, JSON.stringify([...next]));
      return next;
    });
  };

  const handleReviewFromBanner = async (item) => {
    await openChat(item.id).catch(() => {});
    setReviewModalOpen(true);
  };

  const handleGoAgain = async () => {
    if (!readOnlyChat) return;
    setDuplicating(true);
    try {
      await duplicateChat(readOnlyChat.id);
    } catch {
      // error surfaced via context's `error` state
    } finally {
      setDuplicating(false);
    }
  };

  return (
    <>
      <GlobalStyles />
      <div style={{
        display: "flex", height: "100vh", width: "100vw",
        background: C.page, fontFamily: sans, overflow: "hidden",
      }}>

        {/* ── Gear suggestion modal ──────────────────────────────────────── */}
        {gearModal && gearSuggestions.length > 0 && (
          <GearSuggestionModal
            suggestions={gearSuggestions}
            onConfirm={handleGearConfirm}
            onDismiss={handleGearDismiss}
            adding={gearAdding}
          />
        )}

        {/* ── Review questionnaire modal ────────────────────────────────── */}
        {reviewModalOpen && readOnlyChat && (
          <ReviewModal
            trip={readOnlyChat}
            onSubmit={handleSubmitReview}
            onClose={() => setReviewModalOpen(false)}
            submitting={reviewSubmitting}
          />
        )}

        {/* ── Sidebar ────────────────────────────────────────────────────── */}
        <aside style={{
          width: sidebarOpen ? 260 : 0, minWidth: sidebarOpen ? 260 : 0,
          background: C.sidebar, borderRight: `1px solid ${C.sidebarBorder}`,
          display: "flex", flexDirection: "column", overflow: "hidden",
          transition: "width 0.25s ease, min-width 0.25s ease",
        }}>
          <div style={{ padding: "16px 14px 12px", display: "flex", alignItems: "center", gap: 10 }}>
            <Logo size={20} />
            <span style={{ fontFamily: serif, fontSize: 15, color: C.heading, letterSpacing: "0.02em" }}>
              TripPlanner
            </span>
          </div>

          <div style={{ padding: "0 10px 16px" }}>
            <button
              onClick={() => resetChat()}
              style={{
                width: "100%", padding: "9px 14px",
                background: "none", border: `1px solid ${C.sidebarBorder}`,
                borderRadius: 10, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 9,
                color: C.label, fontSize: 13, transition: "all 0.15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = C.amberDim; e.currentTarget.style.borderColor = C.amberBorder; }}
              onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.borderColor = C.sidebarBorder; }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>＋</span>
              <span>New trip</span>
            </button>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "0 8px" }}>
            {chatList.length === 0 && (
              <div style={{ padding: "10px 6px", fontFamily: sans, fontSize: 11.5, color: C.muted, fontStyle: "italic" }}>
                No trips yet — start planning one below.
              </div>
            )}
            {chatGroups.map(group => group.items.length > 0 && (
              <div key={group.key} style={{ marginBottom: 14 }}>
                <div style={{ padding: "0 6px 8px" }}>
                  <span style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "1px" }}>
                    {group.label}
                  </span>
                </div>
                {group.items.map(h => {
                  const isActive = activeChatId === h.id;
                  return (
                  <button key={h.id} onClick={() => handleOpenChat(h.id)}
                    style={{
                      width: "100%", padding: "9px 10px",
                      background: isActive ? C.amber : "none",
                      border: `1px solid ${isActive ? C.amber : "transparent"}`,
                      borderRadius: 8, cursor: "pointer", textAlign: "left",
                      marginBottom: 3, transition: "all 0.15s",
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = C.fieldBg; }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "none"; }}
                  >
                    <div style={{ fontSize: 12.5, color: isActive ? C.amberText : C.label, marginBottom: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {h.title}
                    </div>
                    <StatusBadge status={h.status} color={isActive ? C.amberText : undefined} />
                  </button>
                  );
                })}
              </div>
            ))}
          </div>

          <div style={{
            padding: "12px 14px", borderTop: `1px solid ${C.sidebarBorder}`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: C.fieldBg, border: `1px solid ${C.amberBorder}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, color: C.amber, fontWeight: 700,
            }}>W</div>
            <div>
              <div style={{ fontSize: 12, color: C.heading }}>Will</div>
              <div style={{ fontSize: 10.5, color: C.muted }}>3 items · 2.87 kg</div>
            </div>
          </div>
        </aside>

        {/* ── Main column ────────────────────────────────────────────────── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
          <AmbientHue />

          {/* Trip saved toast */}
          <Toast
            message={`✓ Trip saved — "${activeTrip?.title}"`}
            type="success"
            visible={savedToast}
          />

          {/* Gear added toast */}
          <Toast
            message="✓ Gear added to your kit"
            type="success"
            visible={gearAddedToast}
          />

          {/* Top bar */}
          <header style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "12px 20px", borderBottom: `1px solid ${C.sidebarBorder}`,
            background: "transparent", gap: 12, position: "relative", zIndex: 1,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button
                onClick={() => setSidebarOpen(o => !o)}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  padding: "6px 8px", borderRadius: 8,
                  color: C.muted, fontSize: 18, lineHeight: 1, transition: "color 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.color = C.label}
                onMouseLeave={e => e.currentTarget.style.color = C.muted}
                title="Toggle sidebar"
              >☰</button>

              {!sidebarOpen && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Logo size={18} />
                  <span style={{ fontFamily: serif, fontSize: 14, color: C.heading }}>TripPlanner</span>
                </div>
              )}
            </div>

            <div style={{
              flex: 1, maxWidth: 320, display: "flex", alignItems: "center",
              background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
              borderRadius: 20, padding: "5px 14px", gap: 7,
            }}>
              <span style={{ fontSize: 11, color: C.muted }}>🔒</span>
              <span style={{ fontFamily: mono, fontSize: 11.5, color: C.subtext, letterSpacing: "0.02em" }}>
                tripplanner.ai/chat
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                title={serviceReady === null ? "Checking service…" : serviceReady ? "AI service online" : "AI service offline"}
                style={{
                  width: 7, height: 7, borderRadius: "50%",
                  background: serviceReady === null ? C.muted : serviceReady ? "#7a6236" : "#96301f",
                  boxShadow: serviceReady === true ? "0 0 5px #7a6236" : "none",
                  transition: "all 0.4s",
                }}
              />

              <button
                onClick={() => navigate("/profile")}
                style={{
                  background: "none", border: `1px solid ${C.fieldBorder}`, borderRadius: 20,
                  padding: "6px 16px", color: C.label,
                  fontFamily: sans, fontSize: 12.5, cursor: "pointer",
                  fontWeight: 600, letterSpacing: "0.03em", transition: "all 0.15s",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = C.amberBorder; e.currentTarget.style.color = C.amberText; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.fieldBorder; e.currentTarget.style.color = C.label; }}
              >Profile</button>

              <button
                onClick={() => navigate("/map")}
                style={{
                  background: C.amber, border: "none", borderRadius: 20,
                  padding: "6px 16px", color: C.amberText,
                  fontFamily: sans, fontSize: 12.5, cursor: "pointer",
                  fontWeight: 600, letterSpacing: "0.03em", transition: "background 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = C.amberHover}
                onMouseLeave={e => e.currentTarget.style.background = C.amber}
              >View Map</button>
            </div>
          </header>

          <NeedsReviewBanner
            items={needsReviewItems}
            onReview={handleReviewFromBanner}
            onDismiss={dismissReviewNudge}
          />

          {hasMessages && !readOnlyChat && <PhaseBreadcrumb currentPhase={phase} />}

          {error && (
            <div style={{
              padding: "8px 24px", background: C.errorBg,
              borderBottom: `1px solid ${C.errorBorder}`,
              fontFamily: sans, fontSize: 12.5, color: C.errorText,
              position: "relative", zIndex: 1,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span>⚠</span><span>{error}</span>
            </div>
          )}

          {readOnlyChat ? (
            <ReadOnlyTripView
              trip={readOnlyChat}
              onMarkDone={handleMarkDone}
              marking={marking}
              onCancel={handleCancel}
              cancelling={cancelling}
              onOpenReview={() => setReviewModalOpen(true)}
              onGoAgain={handleGoAgain}
              duplicating={duplicating}
            />
          ) : (
          <>
          {/* Messages or welcome */}
          <div style={{
            flex: 1, overflowY: "auto",
            padding: hasMessages ? "32px 0" : 0,
            display: "flex", flexDirection: "column",
            position: "relative", zIndex: 1,
          }}>
            {!hasMessages ? (
              <WelcomeView onSend={sendMessage} serviceReady={serviceReady} />
            ) : (
              <div style={{ maxWidth: 680, width: "100%", margin: "0 auto", padding: "0 24px" }}>
                {messages.map((msg, i) => {
                  // Cards render anchored under the assistant message that
                  // produced them (msg.hikeOptions), not floating at the bottom
                  // of the thread. They stay interactive only while no hike is
                  // selected yet (plan.hike_id null) — once a trail is picked
                  // the phase advances and the earlier sets become a read-only
                  // record of what was offered.
                  const selectable = !loading && !chat.plan?.hike_id;
                  return (
                    <div key={i}>
                      <Message msg={msg} />
                      {msg.hikeOptions?.length > 0 && (
                        <HikeOptionCards
                          options={msg.hikeOptions}
                          // "option N" must come first: PhaseController.extract_hike_selection
                          // regex-matches the FIRST "option|trail|hike|choice|number|#"
                          // + digit it finds left-to-right. If the trail's own name
                          // happened to contain a number 1-5 (e.g. "Trail 2") and it
                          // came before "option N" in the string, that embedded digit
                          // would win instead — leading "option N" guarantees the
                          // intended index always matches first regardless of name.
                          onPick={
                            selectable
                              ? (opt) => sendMessage(`Option ${opt.index}: ${opt.name}`)
                              : undefined
                          }
                        />
                      )}
                    </div>
                  );
                })}

                {/* Proactive gear tray — while reviewing gear, every identified
                    gap gets the same select-your-own UI as the profile gear page,
                    preselected to the minimum this trail needs. Sourced from the
                    live plan, so a form disappears the moment its gap is resolved
                    and the whole tray hides once the kit is set. */}
                {phase === "gear_review" && chat.plan?.gear_gaps?.length > 0 && (
                  <div style={{ marginBottom: 24 }}>
                    <div style={{
                      fontFamily: serifBody, fontStyle: "italic", fontSize: 13, color: C.subtext,
                      margin: "0 0 10px 44px",
                    }}>
                      Jot down what you're carrying:
                    </div>
                    {chat.plan.gear_gaps.map((gap, gi) => (
                      <GearPromptForm key={(gap.category || "") + gi} prompt={gap} onAdd={handleGearAdd} />
                    ))}
                  </div>
                )}

                {loading && (
                  <div style={{ display: "flex", gap: 12, marginBottom: 24, animation: "fadeIn 0.2s ease" }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: "50%",
                      border: `1px solid ${C.amberBorder}`, background: C.fieldBg,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0,
                    }}>
                      <Logo size={16} />
                    </div>
                    <div style={{ padding: "8px 0" }}>
                      <div style={{ fontFamily: sans, fontSize: 11, color: C.amber, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8, fontWeight: 600 }}>
                        Trail AI
                      </div>
                      <TypingDots />
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}
          </div>

          {/* Input bar */}
          <div style={{
            padding: "16px 24px 20px", background: "transparent",
            borderTop: hasMessages ? `1px solid ${C.sidebarBorder}` : "none",
            position: "relative", zIndex: 1,
          }}>
            <div style={{ maxWidth: 680, margin: "0 auto", position: "relative" }}>
              <div style={{
                background: inputBlocked ? "rgba(162,133,90,0.5)" : C.inputBg,
                border: `1px solid ${C.inputBorder}`,
                borderRadius: 18, overflow: "hidden", position: "relative",
                transition: "border-color 0.15s, background 0.15s",
                opacity: inputBlocked && serviceReady === false ? 0.6 : 1,
              }}
                onFocusCapture={e => { if (!inputBlocked) e.currentTarget.style.borderColor = C.amberBorder; }}
                onBlurCapture={e => e.currentTarget.style.borderColor = C.inputBorder}
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKey}
                  disabled={serviceReady === false}
                  placeholder={
                    serviceReady === false
                      ? "AI service unavailable…"
                      : loading
                        ? "Waiting for Trail AI…"
                        : "Ask about trails, gear, or let me plan a trip…"
                  }
                  rows={1}
                  style={{
                    width: "100%", background: "none", border: "none",
                    outline: "none", resize: "none",
                    padding: "16px 60px 16px 18px",
                    fontFamily: serif, fontSize: 14, color: C.heading,
                    lineHeight: 1.6, boxSizing: "border-box",
                    caretColor: C.amber, minHeight: 54, maxHeight: 160,
                    overflowY: "auto",
                    cursor: serviceReady === false ? "not-allowed" : "text",
                  }}
                  onInput={e => {
                    e.target.style.height = "auto";
                    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                  }}
                />

                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || inputBlocked}
                  style={{
                    position: "absolute", right: 12, bottom: 11,
                    background: input.trim() && !inputBlocked ? C.amber : C.fieldBg,
                    border: `1px solid ${input.trim() && !inputBlocked ? C.amber : C.fieldBorder}`,
                    borderRadius: 10, width: 34, height: 34,
                    cursor: input.trim() && !inputBlocked ? "pointer" : "default",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "all 0.15s", flexShrink: 0,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 1L7 13M7 1L2 6M7 1L12 6"
                      stroke={input.trim() && !inputBlocked ? C.amberText : C.muted}
                      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>

              <div style={{ textAlign: "center", marginTop: 8 }}>
                <span style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, letterSpacing: "0.03em" }}>
                  Trail AI can make mistakes. Verify conditions before heading out.
                </span>
              </div>
            </div>
          </div>
          </>
          )}
        </div>
      </div>
    </>
  );
}