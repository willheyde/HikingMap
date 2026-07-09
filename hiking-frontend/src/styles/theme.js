/* ─── HikeBuilder design tokens ───────────────────────────────────────────────
   Theme: Field Journal (Daylight Paper). Single source of truth for color +
   type across the app. Spec: hiking-frontend/hikeStyle.md.

   Components currently style inline, so the palette is exported as a JS object
   (`palette`) for those files. The same values are mirrored in the `@theme`
   block in styles/global.css (which drives both Tailwind v4 utilities and the
   --color-* CSS variables) — keep the two in sync when editing.
   ──────────────────────────────────────────────────────────────────────────── */

export const palette = {
  // Surfaces — warm aged paper, never pure white
  canvas:    "#dccaa0", // app background
  paper:     "#ebe0c2", // raised surfaces: cards, panels, sheets
  paperSunk: "#ccb98f", // recessed: inputs, wells, map chrome
  rule:      "#a2855a", // hairline borders, ruled lines, dividers

  // Ink — text, never pure black
  ink:       "#3d2817", // primary text (dark walnut)
  inkSoft:   "#5c3a21", // secondary text, subheads
  inkMuted:  "#6a4a26", // captions, placeholders, disabled

  // Ember — primary accent / ink-highlight (kept from prior app)
  ember:      "#a83b2c",
  emberHover: "#8e3022",
  emberWash:  "#e4cb9e", // tint fill behind selected/active
  emberBorder:"rgba(168,59,44,0.45)",
  onEmber:    "#ebe0c2", // text/icons on an ember fill

  // Sage — secondary accent: nature, eco, success
  sage:     "#7a6236",
  sageWash: "#d8c48e",

  // Rust — alerts, destructive, warnings
  rust:     "#96301f",
  rustWash: "#e6c29a",

  // Water (map + accents) — faded old-map teal
  water:    "#cdb483",

  // Feedback (composed)
  successText:   "#7a6236",
  successBg:     "#d8c48e",
  successBorder: "rgba(122,98,54,0.4)",
  errorText:     "#96301f",
  errorBg:       "#e6c29a",
  errorBorder:   "rgba(150,48,31,0.4)",

  // Warm shadow base
  shadow: "rgba(61,40,23,0.12)",
};

/* Font stacks. Families are loaded in index.html (Google Fonts) and declared in
   the global.css @theme block. Fallbacks keep things sane before fonts load. */
export const fonts = {
  display: "'Fraunces', Georgia, 'Times New Roman', serif", // headings, cover voice
  serif:   "'Spectral', Georgia, serif",                    // long-form reading
  sans:    "'Work Sans', 'Trebuchet MS', system-ui, sans-serif", // UI / data
  hand:    "'Caveat', 'Comic Sans MS', cursive",            // marginalia ONLY
  mono:    "'Courier New', Courier, monospace",
};

export default palette;
