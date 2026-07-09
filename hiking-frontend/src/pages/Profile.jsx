import { useMemo, useState, useEffect } from "react";
import { useUser } from "../context/useUser";
import { useNavigate } from "react-router-dom";
import ScrollBar from "../components/ScrollBar";
import { useTrip } from "../context/useTrip";
import { getPastHikesStats } from "../api/tripService";
import { resolveGearCategory, levelLabelFor, categoryMeta } from "../data/gearCategories";

/* ─── Field Journal tokens (hikeStyle.md) ───────────────────────────────── */
const C = {
  page:        "#dccaa0", // canvas
  card:        "#ebe0c2", // paper
  cardBorder:  "#a2855a", // rule
  fieldBg:     "#ccb98f", // paper-sunk
  fieldBorder: "#a2855a", // rule
  heading:     "#3d2817", // ink
  subtext:     "#5c3a21", // ink-soft
  muted:       "#6a4a26", // ink-muted
  label:       "#a83b2c", // ember (accent)
  amber:       "#a83b2c", // ember
  amberDim:    "rgba(168,59,44,0.12)",
  amberBorder: "rgba(168,59,44,0.35)",
  amberText:   "#ebe0c2", // on-ember
  divider:     "#a2855a", // rule
  ownedText:   "#7a6236", // sage
  errorBg:     "#e6c29a", // rust-wash
};
const serif = "'Fraunces', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";
const body  = "'Spectral', Georgia, serif";

/* ─── Mountain avatar (shown when no avatar_url) ────────────────────────── */
const MountainAvatar = ({ size = 96 }) => (
  <div style={{
    width: size, height: size, borderRadius: "50%",
    background: "#ccb98f", border: `2px solid ${C.cardBorder}`,
    display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  }}>
    <svg width={size * 0.72} height={size * 0.55} viewBox="0 0 72 55" fill="none">
      {/* Far peak */}
      <polygon points="54,52 68,20 82,52" fill="none" stroke="#6a4a26" strokeWidth="1.2" strokeLinejoin="round"/>
      {/* Mid peak */}
      <polygon points="20,52 38,14 56,52" fill="#e4cb9e" stroke="#5c3a21" strokeWidth="1.3" strokeLinejoin="round"/>
      {/* Front peak */}
      <polygon points="-2,52 16,26 34,52" fill="none" stroke="#8a7256" strokeWidth="1.2" strokeLinejoin="round"/>
      {/* Snow cap */}
      <polygon points="38,14 42,22 34,22" fill="#a83b2c"/>
      {/* Horizon water line */}
      <path d="M-4,52 Q18,48 36,51 Q54,54 74,50" fill="none" stroke="#a2855a" strokeWidth="1.5" strokeLinecap="round"/>
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
const GearPill = ({ item, categoryKey }) => {
  const level = levelLabelFor(categoryKey, item.attributes?.level);
  const temp  = item.attributes?.temp_rating_f;
  const weight = Number(item.weight) || 0;
  const cost   = Number(item.cost) || 0;
  // Level/temp is the meaningful signal for generalized gear; weight & cost are
  // only shown when actually captured (onboarding doesn't collect them → 0).
  const sub = level
    ? (level !== item.name ? level : null)
    : (temp != null ? `${Math.round(temp)}°F` : null);
  return (
    <div style={{
      padding: "7px 10px", borderRadius: 7,
      background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
      display: "flex", flexDirection: "column", gap: 3,
    }}>
      <span style={{ fontFamily: body, fontSize: 12, color: "#3d2817", lineHeight: 1.3,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {item.name}
      </span>
      <div style={{ display: "flex", gap: 8 }}>
        {sub && (
          <span style={{ fontFamily: sans, fontSize: 10, color: C.label }}>{sub}</span>
        )}
        {weight > 0 && (
          <span style={{ fontFamily: "monospace", fontSize: 10, color: C.muted }}>
            {(weight / 1000).toFixed(2)} kg
          </span>
        )}
        {cost > 0 && (
          <span style={{ fontFamily: "monospace", fontSize: 10, color: "#6a4a26" }}>
            ${cost.toFixed(0)}
          </span>
        )}
      </div>
    </div>
  );
};

/* ─── Divider ────────────────────────────────────────────────────────────── */
const Divider = () => (
  <div style={{
    height: 1, margin: "28px 0",
    background: `linear-gradient(to right, transparent, ${C.divider} 30%, ${C.cardBorder} 50%, ${C.divider} 70%, transparent)`,
  }} />
);

/* ─── Main component ─────────────────────────────────────────────────────── */
const Profile = () => {
  const { user, items, updateLocation, loadingLocation, logout, refreshItems } = useUser();
  const navigate = useNavigate();
  const { chatList, loadChatList, openChat, loading: loadingTrips } = useTrip();
  const [pastStats, setPastStats] = useState({ hike_count: 0, total_miles: 0, favorite_region: null });

  // Depend on user?.id, NOT the whole user object: refreshItems() below calls
  // updateLocalUser({ ...user, items }), which replaces the user reference every
  // run. Keying on the object would make this effect retrigger itself in an
  // infinite loop — loadChatList's shared `loading` flag toggling on each pass
  // is what made the trip cards flash in and vanish.
  useEffect(() => {
    if (!user) return;
    loadChatList();
    getPastHikesStats().then(setPastStats).catch(() => {});
    // Pull fresh gear so items added via the onboarding wizard / gear manager
    // show here without a full re-login (context is otherwise hydrated from a
    // cached blob on mount).
    refreshItems(user.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, loadChatList]);

  // "Saved Trips" (below) means status=saved specifically now — truly
  // upcoming, not-yet-hiked trips — not every trip regardless of lifecycle
  // stage the way the old unfiltered GET /trips/ list showed. Past Hikes
  // (completed + reviewed) gets its own section instead of being mixed in.
  const upcomingTrips = chatList.filter(c => c.status === "saved");
  const pastHikes     = chatList.filter(c => c.status === "completed" || c.status === "reviewed");

  const openTripChat = (chatId) => {
    navigate("/trip-planner");
    openChat(chatId).catch(() => {});
  };

  const itemsByCategory = useMemo(() => {
    if (!items?.length) return {};
    return items.reduce((acc, item) => {
      const key = resolveGearCategory(item);
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
          boxShadow: "0 8px 30px rgba(61,40,23,0.10)",
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
                  background: "#ccb98f", border: `1px solid ${C.fieldBorder}`,
                  color: C.label, fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#e0d0b0"}
                onMouseLeave={e => e.currentTarget.style.background = "#ccb98f"}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
                </svg>
                Map
              </button>
              <button onClick={() => navigate("/trip-planner")}
                style={{
                  padding: "9px 18px", borderRadius: 9, cursor: "pointer",
                  background: "#ccb98f", border: `1px solid ${C.fieldBorder}`,
                  color: C.label, fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#e0d0b0"}
                onMouseLeave={e => e.currentTarget.style.background = "#ccb98f"}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
                </svg>
                Plan a Trip
              </button>
              <button onClick={() => navigate("/gear")}
                style={{
                  padding: "9px 18px", borderRadius: 9, cursor: "pointer",
                  background: C.amber, border: `1px solid ${C.amberBorder}`,
                  color: C.amberText, fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                  boxShadow: "0 4px 16px rgba(168,59,44,0.3)",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#8e3022"}
                onMouseLeave={e => e.currentTarget.style.background = C.amber}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                </svg>
                Manage Gear
              </button>
              <button onClick={logout}
                style={{
                  padding: "9px 18px", borderRadius: 9, cursor: "pointer",
                  background: "rgba(150,48,31,0.10)", border: "1px solid rgba(150,48,31,0.4)",
                  color: "#96301f", fontFamily: sans, fontSize: 12, fontWeight: 600,
                  display: "flex", alignItems: "center", gap: 6,
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "rgba(150,48,31,0.18)";
                  e.currentTarget.style.borderColor = "#96301f";
                  e.currentTarget.style.color = "#8a3626";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "rgba(150,48,31,0.10)";
                  e.currentTarget.style.borderColor = "rgba(150,48,31,0.4)";
                  e.currentTarget.style.color = "#96301f";
                }}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                </svg>
                Logout
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
          <StatCard label="Upcoming Trips" value={upcomingTrips.length}   icon="🗺️" />
        </div>

        {/* ── Upcoming (saved) trips ────────────────────────────────────────── */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: 20, padding: "28px 32px", marginBottom: 20,
        }}>
          <h2 style={{ fontFamily: serif, fontSize: 20, fontWeight: "normal",
            color: C.heading, margin: "0 0 20px", display: "flex", alignItems: "center", gap: 10 }}>
            <span>🗺️</span> Upcoming Trips
          </h2>

          {loadingTrips ? (
            <p style={{ fontFamily: body, color: C.muted, fontStyle: "italic", textAlign: "center", padding: "24px 0" }}>
              Loading trips…
            </p>
          ) : upcomingTrips.length === 0 ? (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <p style={{ fontFamily: body, fontSize: 14, color: C.muted,
                fontStyle: "italic", margin: "0 0 18px" }}>
                No upcoming trips yet — plan your first adventure.
              </p>
              <button onClick={() => navigate("/trip-planner")}
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
              {upcomingTrips.map(trip => (
                <div key={trip.id} onClick={() => openTripChat(trip.id)}
                  style={{
                    background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
                    borderRadius: 12, padding: "16px 18px", cursor: "pointer", transition: "border-color 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = C.amber}
                  onMouseLeave={e => e.currentTarget.style.borderColor = C.fieldBorder}
                >
                  <p style={{ fontFamily: serif, fontSize: 15, color: C.heading, margin: "0 0 4px" }}>
                    {trip.title || "Unnamed Trip"}
                  </p>
                  <p style={{ fontFamily: sans, fontSize: 11, color: C.muted, margin: 0 }}>
                    {new Date(trip.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Past hikes ──────────────────────────────────────────────────── */}
        <div style={{
          background: C.card, border: `1px solid ${C.cardBorder}`,
          borderRadius: 20, padding: "28px 32px", marginBottom: 20,
        }}>
          <h2 style={{ fontFamily: serif, fontSize: 20, fontWeight: "normal",
            color: C.heading, margin: "0 0 20px", display: "flex", alignItems: "center", gap: 10 }}>
            <span>🥾</span> Past Hikes
          </h2>

          {pastHikes.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 12, marginBottom: 22 }}>
              <StatCard label="Hikes Completed" value={pastStats.hike_count}                          icon="🥾" />
              <StatCard label="Total Distance"  value={pastStats.total_miles} sub="mi"                icon="📏" />
              <StatCard label="Favorite Area"   value={pastStats.favorite_region || "—"}               icon="📍" />
            </div>
          )}

          {loadingTrips ? (
            <p style={{ fontFamily: body, color: C.muted, fontStyle: "italic", textAlign: "center", padding: "24px 0" }}>
              Loading…
            </p>
          ) : pastHikes.length === 0 ? (
            <p style={{ fontFamily: body, fontSize: 14, color: C.muted,
              fontStyle: "italic", textAlign: "center", padding: "24px 0", margin: 0 }}>
              Nothing here yet — hikes you mark as done will show up once they're logged.
            </p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
              {pastHikes.map(trip => (
                <div key={trip.id} onClick={() => openTripChat(trip.id)}
                  style={{
                    background: C.fieldBg, border: `1px solid ${C.fieldBorder}`,
                    borderRadius: 12, padding: "16px 18px", cursor: "pointer", transition: "border-color 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = C.amber}
                  onMouseLeave={e => e.currentTarget.style.borderColor = C.fieldBorder}
                >
                  <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
                    <p style={{ fontFamily: serif, fontSize: 15, color: C.heading, margin: "0 0 4px" }}>
                      {trip.title || "Unnamed Trip"}
                    </p>
                    {trip.rating && (
                      <span style={{ color: C.amber, fontSize: 12, flexShrink: 0 }}>
                        {"★".repeat(trip.rating)}
                      </span>
                    )}
                  </div>
                  <p style={{ fontFamily: sans, fontSize: 11, color: C.muted, margin: "0 0 6px" }}>
                    {new Date(trip.updated_at || trip.created_at).toLocaleDateString()}
                  </p>
                  {/* Reviewed pairs its green with an explicit label — not color alone. */}
                  <span style={{
                    fontFamily: sans, fontSize: 10.5, fontWeight: 600,
                    color: trip.status === "reviewed" ? "#7a6236" : C.subtext,
                  }}>
                    {trip.status === "reviewed" ? "✓ Reviewed" : "○ Awaiting review"}
                  </span>
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
                  background: "#ccb98f", border: `1px solid ${C.fieldBorder}`,
                  color: C.label, fontFamily: sans, fontWeight: 600,
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#e0d0b0"}
                onMouseLeave={e => e.currentTarget.style.background = "#ccb98f"}
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
                  boxShadow: "0 4px 16px rgba(168,59,44,0.3)",
                }}>
                Set Up Gear
              </button>
            </div>
          ) : (
            <div>
              {Object.entries(itemsByCategory).map(([type, catItems], idx, arr) => {
                const meta = categoryMeta(type);
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
                      {catItems.map((item, i) => <GearPill key={`${item.id}-${i}`} item={item} categoryKey={type} />)}
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