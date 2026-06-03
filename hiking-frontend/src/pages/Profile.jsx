import { useMemo, useState, useEffect } from "react";
import { useUser } from "../context/UserContext";
import { useNavigate } from "react-router-dom";
import ScrollBar from "../components/ScrollBar";

/* ─── Design tokens ─────────────────────────────────────────────────────── */
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
  amberDim:    "rgba(193,122,46,0.12)",
  amberBorder: "rgba(193,122,46,0.35)",
  amberText:   "#fff8ee",
  divider:     "#3a2510",
  ownedText:   "#9dcc85",
  errorBg:     "#2a100a",
};
const serif = "Georgia, 'Times New Roman', serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";
const body  = "'Palatino Linotype', Palatino, Georgia, serif";

/* ─── Category display names ────────────────────────────────────────────── */
const CATEGORY_LABELS = {
  backpack:       { label: "Backpacks",     icon: "🎒" },
  footwear:       { label: "Footwear",       icon: "👟" },
  shelter:        { label: "Shelter",        icon: "⛺" },
  sleeping_bag:   { label: "Sleeping Bags",  icon: "🛌" },
  sleeping_pad:   { label: "Sleeping Pads",  icon: "🟫" },
  clothing:       { label: "Clothing",       icon: "🧥" },
  water:          { label: "Water",          icon: "💧" },
  kitchen:        { label: "Kitchen",        icon: "🔥" },
  navigation:     { label: "Navigation",     icon: "🗺️" },
  lighting:       { label: "Lighting",       icon: "🔦" },
  safety:         { label: "Safety",         icon: "🚨" },
  trekking_poles: { label: "Trekking Poles", icon: "🥢" },
  technical:      { label: "Technical",      icon: "⛏️" },
};
const getCatMeta = (t) => CATEGORY_LABELS[(t||"").toLowerCase()] ?? { label: t, icon: "📦" };

/* ─── Mountain avatar (shown when no avatar_url) ────────────────────────── */
const MountainAvatar = ({ size = 96 }) => (
  <div style={{
    width: size, height: size, borderRadius: "50%",
    background: "#1a110a", border: `2px solid ${C.cardBorder}`,
    display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  }}>
    <svg width={size * 0.72} height={size * 0.55} viewBox="0 0 72 55" fill="none">
      {/* Far peak */}
      <polygon points="54,52 68,20 82,52" fill="none" stroke="#5a3820" strokeWidth="1.2" strokeLinejoin="round"/>
      {/* Mid peak */}
      <polygon points="20,52 38,14 56,52" fill="#2a1810" stroke="#7a5030" strokeWidth="1.3" strokeLinejoin="round"/>
      {/* Front peak */}
      <polygon points="-2,52 16,26 34,52" fill="none" stroke="#4a2e18" strokeWidth="1.2" strokeLinejoin="round"/>
      {/* Snow cap */}
      <polygon points="38,14 42,22 34,22" fill="#8a6a50"/>
      {/* Horizon water line */}
      <path d="M-4,52 Q18,48 36,51 Q54,54 74,50" fill="none" stroke="#1e3048" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  </div>
);

/* ─── Stat card ─────────────────────────────────────────────────────────── */
const StatCard = ({ label, value, sub, icon }) => (
  <div style={{
    background: C.card, border: `1px solid ${C.cardBorder}`,
    borderRadius: 14, padding: "20px 22px",
  }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
      <span style={{ fontFamily: sans, fontSize: 11, color: C.muted,
        textTransform: "uppercase", letterSpacing: "1.2px" }}>{label}</span>
      <span style={{ fontSize: 18, opacity: 0.7 }}>{icon}</span>
    </div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
      <span style={{ fontFamily: serif, fontSize: 28, color: C.heading, fontWeight: "normal" }}>{value}</span>
      {sub && <span style={{ fontFamily: sans, fontSize: 12, color: C.muted }}>{sub}</span>}
    </div>
  </div>
);

/* ─── Gear item pill ────────────────────────────────────────────────────── */
const GearPill = ({ item }) => (
  <div style={{
    padding: "7px 10px", borderRadius: 7,
    background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
    display: "flex", flexDirection: "column", gap: 3,
  }}>
    <span style={{ fontFamily: body, fontSize: 12, color: "#c8bfb0", lineHeight: 1.3,
      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      {item.name}
    </span>
    <div style={{ display: "flex", gap: 8 }}>
      <span style={{ fontFamily: "monospace", fontSize: 10, color: C.muted }}>
        {(Number(item.weight) / 1000).toFixed(2)} kg
      </span>
      <span style={{ fontFamily: "monospace", fontSize: 10, color: "#7a5a30" }}>
        ${Number(item.cost).toFixed(0)}
      </span>
    </div>
  </div>
);

/* ─── Divider ────────────────────────────────────────────────────────────── */
const Divider = () => (
  <div style={{
    height: 1, margin: "28px 0",
    background: `linear-gradient(to right, transparent, ${C.divider} 30%, ${C.cardBorder} 50%, ${C.divider} 70%, transparent)`,
  }} />
);

/* ─── Main component ─────────────────────────────────────────────────────── */
const Profile = () => {
  const { user, items, updateLocation, loadingLocation } = useUser();
  const navigate = useNavigate();
  const [trips, setTrips]               = useState([]);
  const [loadingTrips, setLoadingTrips] = useState(false);

  useEffect(() => {
    if (!user) return;
    setLoadingTrips(true);
    // placeholder until trips endpoint is wired
    setLoadingTrips(false);
  }, [user]);

  const itemsByCategory = useMemo(() => {
    if (!items?.length) return {};
    return items.reduce((acc, item) => {
      const key = item.item_type || "misc";
      (acc[key] = acc[key] || []).push(item);
      return acc;
    }, {});
  }, [items]);

  const stats = useMemo(() => ({
    count:  items.length,
    weight: items.reduce((s, i) => s + (Number(i.weight) || 0), 0) / 1000,
    cost:   items.reduce((s, i) => s + (Number(i.cost)   || 0), 0),
  }), [items]);

  if (!user) return (
    <div style={{ height: "100vh", background: C.page, display: "flex",
      alignItems: "center", justifyContent: "center" }}>
      <p style={{ fontFamily: body, color: C.muted, fontStyle: "italic" }}>Please log in to view your profile.</p>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: C.page }}>
    <ScrollBar style={{ background: C.page, color: C.heading }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 20px 100px" }}>

        {/* ── Identity card ──────────────────────────────────────────────── */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: 20, padding: "32px", marginBottom: 20,
          boxShadow: "0 8px 40px rgba(0,0,0,0.4)",
        }}>
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start",
            flexWrap: "wrap", justifyContent: "space-between" }}>

            {/* Avatar + info */}
            <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
              {user.avatar_url
                ? <img src={user.avatar_url} alt="Avatar"
                    style={{ width: 96, height: 96, borderRadius: "50%",
                      objectFit: "cover", border: `2px solid ${C.cardBorder}`, flexShrink: 0 }} />
                : <MountainAvatar size={96} />
              }
              <div>
                <h1 style={{ fontFamily: serif, fontSize: 26, fontWeight: "normal",
                  color: C.heading, margin: "0 0 6px" }}>
                  {user.name}
                </h1>
                <p style={{ fontFamily: body, fontSize: 13, color: C.muted,
                  margin: "0 0 10px", fontStyle: "italic" }}>
                  {user.email}
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <svg width="14" height="14" fill="none" stroke={C.muted} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                  </svg>
                  <span style={{ fontFamily: sans, fontSize: 12, color: C.muted }}>
                    {user.home_location?.name || "Location not set"}
                  </span>
                  <button onClick={updateLocation} disabled={loadingLocation}
                    style={{
                      background: "none", border: "none", padding: 0, cursor: loadingLocation ? "not-allowed" : "pointer",
                      fontFamily: sans, fontSize: 11, color: loadingLocation ? C.muted : C.amber,
                      textDecoration: "underline",
                    }}>
                    {loadingLocation ? "Locating…" : "Update"}
                  </button>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
              <button onClick={() => navigate("/map")}
                style={{
                  padding: "9px 18px", borderRadius: 9, cursor: "pointer",
                  background: "rgba(90,58,26,0.3)", border: `1px solid ${C.fieldBorder}`,
                  color: C.label, fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(90,58,26,0.55)"}
                onMouseLeave={e => e.currentTarget.style.background = "rgba(90,58,26,0.3)"}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
                </svg>
                Map
              </button>
              <button onClick={() => navigate("/gear")}
                style={{
                  padding: "9px 18px", borderRadius: 9, cursor: "pointer",
                  background: C.amber, border: "1px solid rgba(255,220,150,0.15)",
                  color: C.amberText, fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                  boxShadow: "0 4px 16px rgba(193,122,46,0.3)",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#d98c38"}
                onMouseLeave={e => e.currentTarget.style.background = C.amber}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                </svg>
                Manage Gear
              </button>
            </div>
          </div>
        </div>

        {/* ── Stats ──────────────────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 14, marginBottom: 20 }}>
          <StatCard label="Items Owned"  value={stats.count}              icon="🎒" />
          <StatCard label="Total Weight" value={stats.weight.toFixed(2)}  sub="kg"  icon="⚖️" />
          <StatCard label="Gear Value"   value={`$${stats.cost.toFixed(0)}`}         icon="💰" />
          <StatCard label="Saved Trips"  value={trips.length}                        icon="🗺️" />
        </div>

        {/* ── Saved trips ─────────────────────────────────────────────────── */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: 20, padding: "28px 32px", marginBottom: 20,
        }}>
          <h2 style={{ fontFamily: serif, fontSize: 20, fontWeight: "normal",
            color: C.heading, margin: "0 0 20px", display: "flex", alignItems: "center", gap: 10 }}>
            <span>🗺️</span> Saved Trips
          </h2>

          {loadingTrips ? (
            <p style={{ fontFamily: body, color: C.muted, fontStyle: "italic", textAlign: "center", padding: "24px 0" }}>
              Loading trips…
            </p>
          ) : trips.length === 0 ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <p style={{ fontFamily: body, fontSize: 14, color: C.muted,
                fontStyle: "italic", margin: "0 0 18px" }}>
                No saved trips yet — plan your first adventure.
              </p>
              <button onClick={() => navigate("/map")}
                style={{
                  padding: "9px 22px", borderRadius: 9, cursor: "pointer",
                  background: C.amberDim, border: `1px solid ${C.amberBorder}`,
                  color: C.label, fontFamily: sans, fontSize: 12, fontWeight: 600,
                }}>
                Plan a Trip
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
              {trips.map(trip => (
                <div key={trip.id} onClick={() => navigate(`/trip/${trip.id}`)}
                  style={{
                    background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
                    borderRadius: 12, padding: "16px 18px", cursor: "pointer", transition: "border-color 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = C.amber}
                  onMouseLeave={e => e.currentTarget.style.borderColor = C.fieldBorder}
                >
                  <p style={{ fontFamily: serif, fontSize: 15, color: C.heading, margin: "0 0 4px" }}>
                    {trip.hike_name || "Unnamed Trip"}
                  </p>
                  <p style={{ fontFamily: sans, fontSize: 11, color: C.muted, margin: 0 }}>
                    {new Date(trip.start_date).toLocaleDateString()} – {new Date(trip.end_date).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Gear inventory ───────────────────────────────────────────────── */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: 20, padding: "28px 32px",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <h2 style={{ fontFamily: serif, fontSize: 20, fontWeight: "normal",
              color: C.heading, margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
              <span>🎒</span> Your Gear
            </h2>
            {items.length > 0 && (
              <button onClick={() => navigate("/gear")}
                style={{
                  padding: "7px 16px", borderRadius: 8, cursor: "pointer", fontSize: 12,
                  background: "rgba(90,58,26,0.3)", border: `1px solid ${C.fieldBorder}`,
                  color: C.label, fontFamily: sans, fontWeight: 600,
                }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(90,58,26,0.55)"}
                onMouseLeave={e => e.currentTarget.style.background = "rgba(90,58,26,0.3)"}
              >
                Edit Gear
              </button>
            )}
          </div>

          {Object.keys(itemsByCategory).length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <p style={{ fontFamily: body, fontSize: 14, color: C.muted,
                fontStyle: "italic", margin: "0 0 6px" }}>Your gear locker is empty.</p>
              <p style={{ fontFamily: sans, fontSize: 12, color: C.muted, margin: "0 0 20px" }}>
                Add your gear so we can calculate pack weight and costs.
              </p>
              <button onClick={() => navigate("/onboarding")}
                style={{
                  padding: "9px 22px", borderRadius: 9, cursor: "pointer",
                  background: C.amber, border: "none", color: C.amberText,
                  fontFamily: sans, fontSize: 12, fontWeight: 600,
                  boxShadow: "0 4px 16px rgba(193,122,46,0.3)",
                }}>
                Set Up Gear
              </button>
            </div>
          ) : (
            <div>
              {Object.entries(itemsByCategory).map(([type, catItems], idx, arr) => {
                const meta = getCatMeta(type);
                const catWeight = catItems.reduce((s, i) => s + (Number(i.weight) || 0), 0) / 1000;
                return (
                  <div key={type}>
                    {/* Category header */}
                    <div style={{ display: "flex", alignItems: "center",
                      justifyContent: "space-between", marginBottom: 10 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 16 }}>{meta.icon}</span>
                        <span style={{ fontFamily: sans, fontSize: 12, fontWeight: 600,
                          color: C.label, textTransform: "uppercase", letterSpacing: "1px" }}>
                          {meta.label}
                        </span>
                        <span style={{ fontFamily: sans, fontSize: 11, color: C.muted }}>
                          · {catItems.length} item{catItems.length !== 1 ? "s" : ""}
                        </span>
                      </div>
                      <span style={{ fontFamily: "monospace", fontSize: 11, color: C.muted }}>
                        {catWeight.toFixed(2)} kg
                      </span>
                    </div>

                    {/* Items */}
                    <div style={{ display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginBottom: 8 }}>
                      {catItems.map((item, i) => <GearPill key={`${item.id}-${i}`} item={item} />)}
                    </div>

                    {idx < arr.length - 1 && <Divider />}
                  </div>
                );
              })}

              {/* Pack total footer */}
              <div style={{
                marginTop: 28, padding: "16px 20px", borderRadius: 12,
                background: C.amberDim, border: `1px solid ${C.amberBorder}`,
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <span style={{ fontFamily: sans, fontSize: 12, color: C.label,
                  textTransform: "uppercase", letterSpacing: "1px" }}>
                  Full Pack Total
                </span>
                <div style={{ display: "flex", gap: 24 }}>
                  <span style={{ fontFamily: "monospace", fontSize: 14, color: C.amber }}>
                    {stats.weight.toFixed(2)} kg
                  </span>
                  <span style={{ fontFamily: "monospace", fontSize: 14, color: C.label }}>
                    ${stats.cost.toFixed(0)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <p style={{ textAlign: "center", fontFamily: sans, fontSize: 11,
          color: C.muted, marginTop: 36, letterSpacing: "0.5px" }}>
          Leave no trace · Stay on the trail
        </p>
      </div>
    </ScrollBar>
    </div>
  );
};

export default Profile;