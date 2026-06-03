import { useState, useEffect, useMemo } from "react";
import { useUser } from "../context/UserContext";
import { listItems } from "../api/itemsService";
import { useNavigate } from "react-router-dom";
import ScrollBar from "../components/ScrollBar";

/* ─── Category config ───────────────────────────────────────────────────── */
const CATEGORY_MAP = {
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
  misc:           { label: "Misc",           icon: "📦" },
};

const getCategoryLabel = (t) => CATEGORY_MAP[(t || "").toLowerCase()]?.label ?? "Other";
const getCategoryIcon  = (t) => CATEGORY_MAP[(t || "").toLowerCase()]?.icon  ?? "📦";

/* ─── Shared modal ──────────────────────────────────────────────────────── */
const Modal = ({ children }) => (
  <div style={{
    position: "fixed", inset: 0, zIndex: 50,
    display: "flex", alignItems: "center", justifyContent: "center",
    background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)", padding: 16,
  }}>
    <div style={{
      background: "#1e160d", border: "1px solid rgba(90,58,26,0.6)",
      borderRadius: 20, padding: "1.75rem", maxWidth: 360, width: "100%",
      boxShadow: "0 32px 80px rgba(0,0,0,0.6)",
    }}>
      {children}
    </div>
  </div>
);

/* ─── Mountain mark ─────────────────────────────────────────────────────── */
const MountainMark = () => (
  <svg width="28" height="22" viewBox="0 0 40 32" fill="none" style={{ flexShrink: 0 }}>
    <polygon points="20,2 38,30 2,30" fill="none" stroke="#c17a2e" strokeWidth="1.5" strokeLinejoin="round"/>
    <polygon points="10,30 20,12 30,30" fill="#2a1810" stroke="#8b5e3c" strokeWidth="1" strokeLinejoin="round"/>
  </svg>
);

/* ─── Main component ─────────────────────────────────────────────────────── */
const QuickGearSetup = () => {
  const { user, items: userItems, addItemsBatch, deleteItem } = useUser();
  const navigate = useNavigate();

  const [catalog, setCatalog]               = useState([]);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [activeCategory, setActiveCategory] = useState("All");
  const [selectedIds, setSelectedIds]       = useState(new Set());
  const [isProcessing, setIsProcessing]     = useState(false);
  const [itemToRemove, setItemToRemove]     = useState(null);
  const [showUnsavedModal, setShowUnsavedModal] = useState(false);

  useEffect(() => {
    listItems()
      .then(setCatalog)
      .catch(err => console.error("Failed to load catalog:", err))
      .finally(() => setLoadingCatalog(false));
  }, []);

  /* ── Derived ──────────────────────────────────────────────────────────── */
  const isOwned    = (id) => (userItems || []).some(u => u.id === id);
  const isSelected = (id) => selectedIds.has(id);

  const totalOwnedWeightKg = useMemo(() =>
    (userItems || []).reduce((sum, i) => sum + (Number(i.weight) || 0), 0) / 1000,
  [userItems]);

  const categories = useMemo(() => {
    const seen = new Set(catalog.map(i => getCategoryLabel(i.item_type)));
    return ["All", ...Array.from(seen).sort()];
  }, [catalog]);

  /* Filter by tab, then sort: owned items first, then unowned alphabetically */
  const visibleItems = useMemo(() => {
    const filtered = activeCategory === "All"
      ? catalog
      : catalog.filter(i => getCategoryLabel(i.item_type) === activeCategory);

    return [...filtered].sort((a, b) => {
      const aOwned = isOwned(a.id);
      const bOwned = isOwned(b.id);
      if (aOwned && !bOwned) return -1;
      if (!aOwned && bOwned) return  1;
      return a.name.localeCompare(b.name);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCategory, catalog, userItems]);

  const ownedCount = useMemo(
    () => visibleItems.filter(i => isOwned(i.id)).length,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [visibleItems, userItems]);

  /* ── Handlers ─────────────────────────────────────────────────────────── */
  const handleItemClick = (item) => {
    if (isProcessing) return;
    if (isOwned(item.id)) { setItemToRemove(item); return; }
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(item.id) ? next.delete(item.id) : next.add(item.id);
      return next;
    });
  };

  const handleBulkAdd = async () => {
    if (!user || selectedIds.size === 0) return;
    setIsProcessing(true);
    try {
      await addItemsBatch(user.id, Array.from(selectedIds));
      setSelectedIds(new Set());
      if (showUnsavedModal) navigate("/map");
    } catch (err) {
      console.error("Failed to add items:", err);
    } finally {
      setIsProcessing(false);
      setShowUnsavedModal(false);
    }
  };

  const confirmRemove = async () => {
    if (!itemToRemove || !user) return;
    setIsProcessing(true);
    try {
      await deleteItem(user.id, itemToRemove.id);
      setItemToRemove(null);
    } catch (err) {
      console.error("Failed to remove:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNavigation = () =>
    selectedIds.size > 0 ? setShowUnsavedModal(true) : navigate("/map");

  /* ── Loading ──────────────────────────────────────────────────────────── */
  if (loadingCatalog) {
    return (
      <div style={{ height: "100vh", background: "#0d0a07", display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
        <MountainMark />
        <p style={{ fontFamily: "'Trebuchet MS', sans-serif", fontSize: 12,
          color: "#6b4f35", letterSpacing: "2px", textTransform: "uppercase" }}>
          Loading your gear…
        </p>
      </div>
    );
  }

  /* ── Render ───────────────────────────────────────────────────────────── */
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column",
      background: "#0d0a07", color: "#e8dcc8", overflow: "hidden", position: "relative" }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0, zIndex: 20,
        background: "rgba(20,13,7,0.94)", backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(90,58,26,0.5)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
      }}>
        <div style={{ padding: "14px 20px", display: "flex", alignItems: "center",
          justifyContent: "space-between", gap: 12 }}>

          {/* Left */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MountainMark />
            <div>
              <h1 style={{ fontFamily: "Georgia, serif", fontSize: 18, fontWeight: "normal",
                color: "#f0e6d0", margin: 0, letterSpacing: "0.3px" }}>
                Gear Locker
              </h1>
              <p style={{ fontFamily: "Palatino, Georgia, serif", fontSize: 12,
                color: "#6b4f35", margin: "2px 0 0", fontStyle: "italic" }}>
                Green items are in your pack
              </p>
            </div>
          </div>

          {/* Right */}
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ display: "none", flexDirection: "column", alignItems: "flex-end" }}
              className="md-show">
              <span style={{ fontFamily: "'Trebuchet MS', sans-serif", fontSize: 10,
                color: "#5a3a1a", textTransform: "uppercase", letterSpacing: "1.5px" }}>
                Pack Weight
              </span>
              <span style={{ fontFamily: "monospace", fontSize: 15, color: "#c17a2e" }}>
                {totalOwnedWeightKg.toFixed(2)} kg
              </span>
            </div>
            <button
              onClick={handleNavigation}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 16px", borderRadius: 8, fontSize: 13,
                fontFamily: "'Trebuchet MS', sans-serif", fontWeight: 600,
                background: "rgba(90,58,26,0.35)", color: "#c8a97a",
                border: "1px solid rgba(193,122,46,0.3)", cursor: "pointer",
                transition: "background 0.2s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(90,58,26,0.6)"}
              onMouseLeave={e => e.currentTarget.style.background = "rgba(90,58,26,0.35)"}
            >
              Go to Map
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Category tabs */}
        <ScrollBar className="px-5 pb-0 !h-auto overflow-x-auto !overflow-y-hidden flex gap-1">
          {categories.map(cat => (
            <button key={cat} onClick={() => setActiveCategory(cat)}
              style={{
                whiteSpace: "nowrap", padding: "8px 12px 10px",
                borderBottom: `2px solid ${activeCategory === cat ? "#c17a2e" : "transparent"}`,
                color: activeCategory === cat ? "#c8a97a" : "#5a3a1a",
                fontFamily: "'Trebuchet MS', sans-serif", fontSize: 13,
                fontWeight: activeCategory === cat ? 600 : 400,
                background: "none", border: "none",
                borderBottom: `2px solid ${activeCategory === cat ? "#c17a2e" : "transparent"}`,
                cursor: "pointer", transition: "color 0.15s",
              }}
              onMouseEnter={e => { if (activeCategory !== cat) e.currentTarget.style.color = "#a07850"; }}
              onMouseLeave={e => { if (activeCategory !== cat) e.currentTarget.style.color = "#5a3a1a"; }}
            >
              {cat}
            </button>
          ))}
        </ScrollBar>
      </div>

      {/* ── Owned section label ──────────────────────────────────────────── */}
      {ownedCount > 0 && (
        <div style={{
          padding: "10px 20px 0",
          fontFamily: "'Trebuchet MS', sans-serif", fontSize: 11,
          color: "#5a8a40", textTransform: "uppercase", letterSpacing: "1.5px",
          background: "#0d0a07", flexShrink: 0,
        }}>
          ✓ In your pack — {ownedCount} item{ownedCount !== 1 ? "s" : ""}
        </div>
      )}

      {/* ── Grid ────────────────────────────────────────────────────────── */}
      <ScrollBar className="!h-auto flex-1 p-5 relative" style={{ background: "#0d0a07" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", paddingBottom: 100 }}>

          {/* Divider between owned / unowned */}
          {ownedCount > 0 && ownedCount < visibleItems.length && (() => {
            // We'll inject the divider inline in the grid via a wrapper approach
            const owned   = visibleItems.filter(i => isOwned(i.id));
            const unowned = visibleItems.filter(i => !isOwned(i.id));
            return (
              <>
                {/* Owned grid */}
                <div style={{
                  display: "grid", gap: 12,
                  gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
                  marginBottom: 0,
                }}>
                  {owned.map(item => <ItemCard key={item.id} item={item}
                    owned selected={false} onClick={() => handleItemClick(item)} />)}
                </div>

                {/* Section break */}
                <div style={{
                  display: "flex", alignItems: "center", gap: 12,
                  margin: "20px 0 16px",
                }}>
                  <div style={{ flex: 1, height: 1, background: "rgba(90,58,26,0.3)" }} />
                  <span style={{ fontFamily: "'Trebuchet MS', sans-serif", fontSize: 11,
                    color: "#5a3a1a", textTransform: "uppercase", letterSpacing: "1.5px",
                    whiteSpace: "nowrap" }}>
                    Not in pack
                  </span>
                  <div style={{ flex: 1, height: 1, background: "rgba(90,58,26,0.3)" }} />
                </div>

                {/* Unowned grid */}
                <div style={{
                  display: "grid", gap: 12,
                  gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
                }}>
                  {unowned.map(item => <ItemCard key={item.id} item={item}
                    owned={false} selected={isSelected(item.id)}
                    onClick={() => handleItemClick(item)} />)}
                </div>
              </>
            );
          })()}

          {/* All same status — no divider needed */}
          {(ownedCount === 0 || ownedCount === visibleItems.length) && (
            <div style={{
              display: "grid", gap: 12,
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
            }}>
              {visibleItems.map(item => (
                <ItemCard key={item.id} item={item}
                  owned={isOwned(item.id)} selected={isSelected(item.id)}
                  onClick={() => handleItemClick(item)} />
              ))}
            </div>
          )}
        </div>
      </ScrollBar>

      {/* ── Floating Add button ──────────────────────────────────────────── */}
      {selectedIds.size > 0 && (
        <div style={{ position: "absolute", bottom: 28, left: 0, right: 0,
          display: "flex", justifyContent: "center", zIndex: 30, pointerEvents: "none" }}>
          <button
            onClick={handleBulkAdd} disabled={isProcessing}
            style={{
              pointerEvents: "auto", display: "flex", alignItems: "center", gap: 10,
              padding: "12px 32px", borderRadius: 9999, fontWeight: 600, fontSize: 14,
              fontFamily: "'Trebuchet MS', sans-serif", cursor: isProcessing ? "not-allowed" : "pointer",
              background: isProcessing ? "#7a4a1e" : "#c17a2e", color: "#fff8ee",
              border: "1px solid rgba(255,220,150,0.15)",
              boxShadow: "0 8px 32px rgba(193,122,46,0.4)",
              transition: "background 0.2s, transform 0.15s",
            }}
            onMouseEnter={e => { if (!isProcessing) { e.currentTarget.style.background = "#d98c38"; e.currentTarget.style.transform = "translateY(-2px)"; }}}
            onMouseLeave={e => { if (!isProcessing) { e.currentTarget.style.background = "#c17a2e"; e.currentTarget.style.transform = "translateY(0)"; }}}
          >
            {isProcessing ? "Saving…" : (
              <>
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"/>
                </svg>
                Add {selectedIds.size} Item{selectedIds.size !== 1 ? "s" : ""} to Pack
              </>
            )}
          </button>
        </div>
      )}

      {/* ── Remove modal ─────────────────────────────────────────────────── */}
      {itemToRemove && (
        <Modal>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <MountainMark />
          </div>
          <h3 style={{ fontFamily: "Georgia, serif", fontSize: 18, fontWeight: "normal",
            color: "#f0e6d0", textAlign: "center", margin: "0 0 8px" }}>
            Remove from pack?
          </h3>
          <p style={{ fontFamily: "Palatino, Georgia, serif", fontSize: 13,
            color: "#8b6a4a", textAlign: "center", margin: "0 0 24px" }}>
            <span style={{ color: "#9dcc85" }}>{itemToRemove.name}</span> will be removed from your inventory.
          </p>
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={() => setItemToRemove(null)} style={{
              flex: 1, padding: "10px 0", borderRadius: 10, cursor: "pointer",
              background: "rgba(90,58,26,0.3)", border: "1px solid rgba(90,58,26,0.5)",
              color: "#c8bfb0", fontFamily: "'Trebuchet MS', sans-serif", fontSize: 13,
            }}>Cancel</button>
            <button onClick={confirmRemove} disabled={isProcessing} style={{
              flex: 1, padding: "10px 0", borderRadius: 10, cursor: isProcessing ? "not-allowed" : "pointer",
              background: "#7a2e1e", border: "1px solid rgba(200,80,60,0.4)",
              color: "#f8c8b8", fontFamily: "'Trebuchet MS', sans-serif", fontSize: 13, fontWeight: 600,
            }}>
              {isProcessing ? "…" : "Remove"}
            </button>
          </div>
        </Modal>
      )}

      {/* ── Unsaved modal ────────────────────────────────────────────────── */}
      {showUnsavedModal && (
        <Modal>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <MountainMark />
          </div>
          <h3 style={{ fontFamily: "Georgia, serif", fontSize: 18, fontWeight: "normal",
            color: "#f0e6d0", textAlign: "center", margin: "0 0 8px" }}>
            Gear not saved yet
          </h3>
          <p style={{ fontFamily: "Palatino, Georgia, serif", fontSize: 13,
            color: "#8b6a4a", textAlign: "center", margin: "0 0 24px" }}>
            You have <span style={{ color: "#c8a97a" }}>{selectedIds.size} item{selectedIds.size !== 1 ? "s" : ""}</span> selected but not added to your pack.
          </p>
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={() => navigate("/map")} style={{
              flex: 1, padding: "10px 0", borderRadius: 10, cursor: "pointer",
              background: "rgba(90,58,26,0.3)", border: "1px solid rgba(90,58,26,0.5)",
              color: "#a07850", fontFamily: "'Trebuchet MS', sans-serif", fontSize: 13,
            }}>Leave anyway</button>
            <button onClick={handleBulkAdd} disabled={isProcessing} style={{
              flex: 1, padding: "10px 0", borderRadius: 10,
              cursor: isProcessing ? "not-allowed" : "pointer",
              background: "#c17a2e", color: "#fff8ee",
              border: "none", fontFamily: "'Trebuchet MS', sans-serif",
              fontSize: 13, fontWeight: 600,
            }}>
              {isProcessing ? "Saving…" : "Add & Leave"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
};

/* ─── Item card ─────────────────────────────────────────────────────────── */
const ItemCard = ({ item, owned, selected, onClick }) => {
  const bg     = owned   ? "rgba(28,42,18,0.7)"
               : selected ? "rgba(30,20,10,0.85)"
               : "#1a110a";
  const border = owned   ? "rgba(90,160,60,0.55)"
               : selected ? "#c17a2e"
               : "rgba(90,58,26,0.3)";
  const shadow = owned   ? "0 0 14px rgba(80,140,60,0.1)"
               : selected ? "0 0 18px rgba(193,122,46,0.22)"
               : "none";

  return (
    <div onClick={onClick} style={{
      position: "relative", cursor: "pointer", borderRadius: 12,
      overflow: "hidden", display: "flex", flexDirection: "column",
      background: bg, border: `1.5px solid ${border}`, boxShadow: shadow,
      transform: selected && !owned ? "scale(1.02)" : "scale(1)",
      transition: "all 0.15s ease",
    }}>
      {/* Badge */}
      {owned && (
        <div style={{
          position: "absolute", top: 8, right: 8, zIndex: 2,
          background: "rgba(50,110,30,0.88)", color: "#b8e8a0",
          fontFamily: "'Trebuchet MS', sans-serif", fontSize: 10,
          fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px",
          padding: "2px 8px", borderRadius: 9999,
        }}>✓ Owned</div>
      )}
      {selected && !owned && (
        <div style={{
          position: "absolute", top: 8, right: 8, zIndex: 2,
          background: "rgba(193,122,46,0.92)", color: "#fff8ee",
          fontFamily: "'Trebuchet MS', sans-serif", fontSize: 10,
          fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px",
          padding: "2px 8px", borderRadius: 9999,
        }}>Selected</div>
      )}

      {/* Image */}
      <div style={{
        height: 112, background: "#130e08",
        display: "flex", alignItems: "center", justifyContent: "center",
        opacity: owned ? 0.6 : 1, overflow: "hidden",
      }}>
        {item.image_url
          ? <img src={item.image_url} alt={item.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <span style={{ fontSize: 30, userSelect: "none" }}>{getCategoryIcon(item.item_type)}</span>
        }
      </div>

      {/* Info */}
      <div style={{ padding: "10px 12px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        <p style={{
          fontFamily: "Palatino, Georgia, serif", fontSize: 13, lineHeight: 1.35,
          color: owned ? "#9dcc85" : selected ? "#c8a97a" : "#c8bfb0",
          margin: "0 0 8px", fontWeight: owned || selected ? 600 : 400,
        }}>
          {item.name}
        </p>
        <div style={{ display: "flex", justifyContent: "space-between",
          fontFamily: "monospace", fontSize: 11, color: "#5a3a1a" }}>
          <span>{(Number(item.weight) / 1000).toFixed(2)} kg</span>
          <span style={{ color: "#7a5a30" }}>${Number(item.cost).toFixed(0)}</span>
        </div>
      </div>
    </div>
  );
};

export default QuickGearSetup;