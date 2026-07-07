// src/data/gearCategories.js
//
// Mirrors the backend gear vocabulary (pythonBackend/gear_levels.py). Kept as a
// small static constant — the set is small and changes rarely.
// `key` is the functional gear_category the POST /users/:id/gear endpoint expects;
// `levels[].value` must match the level scales in gear_levels.py exactly.

export const GEAR_SECTIONS = [
  {
    key: "footwear", label: "Footwear", icon: "👟",
    prompt: "What footwear do you own? Add each type you'd hike in.",
    levels: [
      { value: "sandal",              label: "Sandals" },
      { value: "trail_runner",        label: "Trail runners" },
      { value: "hiking_boot",         label: "Hiking boots" },
      { value: "mountaineering_boot", label: "Mountaineering boots" },
    ],
  },
  {
    key: "insulation", label: "Insulation", icon: "🧥",
    prompt: "Insulating layers — warmth for cold or exposed trails.",
    levels: [
      { value: "fleece",     label: "Fleece" },
      { value: "puffy",      label: "Puffy / down" },
      { value: "expedition", label: "Expedition-weight" },
    ],
  },
  {
    key: "shell", label: "Rain shell", icon: "🌧️",
    prompt: "Wind / rain shells you own.",
    levels: [
      { value: "water_resistant", label: "Water-resistant" },
      { value: "hardshell",       label: "Hardshell (waterproof)" },
    ],
  },
  {
    key: "shelter", label: "Shelter", icon: "⛺",
    prompt: "Tents or shelters — add each you'd take.",
    levels: [
      { value: "3_season", label: "3-season" },
      { value: "4_season", label: "4-season" },
    ],
  },
  {
    key: "navigation", label: "Navigation", icon: "🧭",
    prompt: "How do you navigate?",
    levels: [
      { value: "map",       label: "Map & compass" },
      { value: "gps",       label: "GPS / phone app" },
      { value: "satellite", label: "Satellite messenger" },
    ],
  },
  {
    key: "traction", label: "Traction", icon: "🥾",
    prompt: "Traction for snow or ice — skip if you have none.",
    levels: [
      { value: "microspikes", label: "Microspikes" },
      { value: "crampons",    label: "Crampons" },
    ],
  },
  {
    key: "sleep", label: "Sleep system", icon: "🛌",
    prompt: "Sleeping bag or quilt — enter its temp rating if you know it.",
    sleepTemp: true,
  },
  {
    key: "hydration", label: "Water", icon: "💧",
    prompt: "Water carry or treatment (bottle, bladder, filter).",
    presence: true,
  },
  {
    key: "illumination", label: "Headlamp", icon: "🔦",
    prompt: "A headlamp or flashlight?",
    presence: true,
  },
  {
    key: "first_aid", label: "First aid", icon: "🩹",
    prompt: "A first-aid kit?",
    presence: true,
  },
];

/* Fast lookups keyed by functional gear_category. */
export const GEAR_SECTION_BY_KEY = Object.fromEntries(
  GEAR_SECTIONS.map(s => [s.key, s])
);

// Legacy item_type → functional category, mirroring
// gear_levels.resolve_gear_category() on the backend. Clothing is ambiguous and
// split by the waterproof flag (shell vs insulation).
const ITEM_TYPE_TO_SECTION = {
  footwear: "footwear", technical: "traction", navigation: "navigation",
  lighting: "illumination", safety: "first_aid", water: "hydration",
  shelter: "shelter", sleeping_bag: "sleep",
};

/** The functional gear_category for an item (new attributes.gear_category first,
 *  else derived from the legacy item_type). Returns "misc" when unmappable. */
export const resolveGearCategory = (item) => {
  const attrs = item?.attributes || {};
  if (attrs.gear_category) return attrs.gear_category;
  if (item?.item_type === "clothing") return attrs.waterproof ? "shell" : "insulation";
  return ITEM_TYPE_TO_SECTION[item?.item_type] || "misc";
};

/** Human label for a level value within a category (or null). */
export const levelLabelFor = (categoryKey, value) => {
  const section = GEAR_SECTION_BY_KEY[categoryKey];
  if (!value || !Array.isArray(section?.levels)) return null;
  return section.levels.find(l => l.value === value)?.label || value;
};

/** Display metadata (label + icon) for a functional category. */
export const categoryMeta = (categoryKey) => {
  const section = GEAR_SECTION_BY_KEY[categoryKey];
  if (section) return { label: section.label, icon: section.icon };
  return { label: "Other gear", icon: "📦" };
};

// Ordinal rank of a level within a category's scale (-1 if not level-bearing or
// unknown), matching gear_levels.level_index() on the backend.
const levelIndex = (categoryKey, value) => {
  const section = GEAR_SECTION_BY_KEY[categoryKey];
  if (!value || !Array.isArray(section?.levels)) return -1;
  return section.levels.findIndex(l => l.value === value);
};

/**
 * Per-trail gear readiness for the detail page — a mirror of
 * GearGapAnalyzer.readiness_for_hike (backend). Walks the hike's
 * gear_requirements and, for each category, reports whether the user's gear
 * satisfies it. Returns one row per required category:
 *   { category, label, icon, importance, required, status, note }
 *   status: "ok" (✓) | "missing" (✗ required & absent) | "flag" (⚠ recommended-
 *           absent, or owned-but-under-spec)
 * Adequacy fails open when an owned item has no captured level (matches backend).
 */
export const readinessForHike = (gearRequirements, userItems) => {
  const reqs = gearRequirements || {};
  const items = userItems || [];

  const rows = Object.entries(reqs).map(([cat, spec]) => {
    const s = spec || {};
    const importance = s.importance || "required";
    const required = importance === "required";
    const meta = categoryMeta(cat);
    const inCat = items.filter(i => resolveGearCategory(i) === cat);
    const owns = inCat.length > 0;

    const requiredDisplay =
      s.min_level != null ? levelLabelFor(cat, s.min_level)
      : s.min_temp_f != null ? `${Math.round(s.min_temp_f)}°F bag`
      : null;

    let status = "ok";
    let note = null;

    if (!owns) {
      status = required ? "missing" : "flag";
      note = required
        ? `No ${meta.label.toLowerCase()} on record (required for this trail).`
        : `No ${meta.label.toLowerCase()} on record (recommended for this trail).`;
    } else if (cat === "sleep") {
      const temps = inCat.map(i => i.attributes?.temp_rating_f).filter(t => t != null).map(Number);
      const have = temps.length ? Math.min(...temps) : null;
      const need = s.min_temp_f;
      if (need != null) {
        if (have == null) {
          status = "flag";
          note = "Sleep system found but no temperature rating stored — confirm it's warm enough.";
        } else if (have > need) {
          status = "flag";
          note = `Your warmest bag is rated ${Math.round(have)}°F, but this trip calls for about ${Math.round(need)}°F.`;
        }
      }
    } else if (s.min_level != null && Array.isArray(GEAR_SECTION_BY_KEY[cat]?.levels)) {
      const needIdx = levelIndex(cat, s.min_level);
      const haveIdx = Math.max(-1, ...inCat.map(i => levelIndex(cat, i.attributes?.level)));
      // Only flag when we actually know the user's level and it's below spec —
      // an owned item with an unknown level counts as present (fails open).
      if (needIdx >= 0 && haveIdx >= 0 && haveIdx < needIdx) {
        status = "flag";
        note = `You have ${levelLabelFor(cat, GEAR_SECTION_BY_KEY[cat].levels[haveIdx].value)}, but this trail calls for ${levelLabelFor(cat, s.min_level)}.`;
      }
    }

    return { category: cat, label: meta.label, icon: meta.icon, importance, required: requiredDisplay, status, note };
  });

  // Required first, then recommended; missing/flag surface above ok within each.
  const statusRank = { missing: 0, flag: 1, ok: 2 };
  return rows.sort((a, b) =>
    (a.importance === "required" ? 0 : 1) - (b.importance === "required" ? 0 : 1)
    || statusRank[a.status] - statusRank[b.status]
    || a.label.localeCompare(b.label)
  );
};
