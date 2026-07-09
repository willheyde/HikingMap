# hikeStyle — HikeBuilder Visual Language

**Theme:** *Field Journal (Daylight Paper)*
**One-line brief:** A naturalist's field notebook, open on a sunlit table. Warm paper, ink-brown text, botanical accents, and the ember-amber highlight you already own. Every trail feels *collected and annotated*, not just listed.

This document is the single source of truth for how the frontend should look and feel. When a component decision isn't covered here, ask: *"What would this look like inked into a well-made field journal?"*

---

## 1. Design principles

1. **Paper first.** The canvas is warm paper, never pure white and never dark. Light, tactile, calm.
2. **Ration the charm.** Handwriting, texture, and illustration are *seasoning*, not the meal. They appear at the edges — headings, labels, marginalia — never in dense content. Get this wrong and the app reads "cutesy" and slow.
3. **Legibility is non-negotiable.** Trail descriptions, gear lists, costs, and itineraries are always set in clean, high-contrast type. Decoration never costs a user a squint.
4. **The map is part of the journal.** It is styled as an aged map *page*, not a bright modern web map. This is the whole reason the theme fits — lean into it.
5. **Evolve, don't restart.** The current TripPlanner palette (cream, ember-amber, brown ink) is already field-journal DNA. It moves from "campfire at night" to "notebook in daylight." Amber becomes the ink-highlight.
6. **Daylight only.** No dark mode in this edition. If a "lantern-lit" dark variant is ever added, it's a separate, later spec.

---

## 2. Color

Warm, aged, low-saturation. Think coffee-stained cartography, not a bright green outdoors brand.

### Core tokens

| Token | Hex | Role |
|---|---|---|
| `canvas` | `#f2e8d5` | App background — aged paper |
| `paper` | `#faf3e6` | Raised surfaces: cards, panels, sheets |
| `paperSunk` | `#ece0c8` | Recessed areas: inputs, wells, map chrome |
| `rule` | `#d8c4a0` | Hairline borders, ruled lines, dividers |
| `ink` | `#2e2013` | Primary text — dark walnut |
| `inkSoft` | `#6b5844` | Secondary text, subheads |
| `inkMuted` | `#a08a6e` | Captions, placeholders, disabled |

### Accents

| Token | Hex | Role |
|---|---|---|
| `ember` | `#c17a2e` | Primary accent / ink-highlight — links, active state, primary buttons *(kept from current app)* |
| `emberHover` | `#a8641f` | Hover/pressed for ember |
| `emberWash` | `#efd9b8` | Tint fill behind selected/active items |
| `sage` | `#6b7a52` | Secondary accent — nature, "green"/eco hikes, success |
| `sageWash` | `#dfe3cf` | Tint fill for sage states |
| `rust` | `#a4432f` | Alerts, destructive actions, warnings |
| `rustWash` | `#f0d9cf` | Tint fill for rust states |

### Feedback

- **Success:** `sage` text on `sageWash`.
- **Error / destructive:** `rust` text on `rustWash`.
- **Info / highlight:** `ember` text on `emberWash`.

### Rules
- Never use pure `#000` or `#fff`. Black is `ink`; white is `paper`.
- Saturation stays low — everything reads slightly faded, as if printed a while ago.
- Exactly one accent leads any given screen. `ember` is the default lead; `sage` supports; `rust` interrupts.

---

## 3. Typography

Four faces, each with a strict job. All are on Google Fonts and self-hostable.

| Face | Use | Notes |
|---|---|---|
| **Fraunces** | Display & page/section headings — the "cover" voice | Variable; use higher optical size, soft settings. Warm and literary. |
| **Spectral** | Long-form reading: trail descriptions, AI chat prose | A comfortable serif for actual reading. |
| **Work Sans** | UI, labels, buttons, data, tables, gear lists, costs | Keeps dense information crisp and modern. This carries most pixels. |
| **Caveat** | Marginalia & annotations **only** | Handwritten. Strictly rationed — see below. |

### The Caveat rule
Handwriting is the theme's signature *and* its biggest failure mode. It is allowed **only** for:
- Short marginal notes ("your guide's note", tips, empty-state asides)
- Decorative labels / section flourishes of ≤ 4 words
- The occasional callout pull-quote

It is **never** used for: body text, buttons, form fields, lists, numbers, or anything a user must read to make a decision.

### Scale (suggested, rem @ 16px base)
| Level | Face | Size / weight |
|---|---|---|
| Display | Fraunces | 2.5–3rem / 500 |
| H1 | Fraunces | 2rem / 500 |
| H2 | Fraunces | 1.5rem / 500 |
| H3 | Work Sans | 1.125rem / 600, tracked +0.02em, small-caps feel |
| Body | Spectral | 1rem / 400, line-height 1.6 |
| UI / label | Work Sans | 0.875rem / 500 |
| Caption | Work Sans | 0.75rem / 500, `inkMuted` |
| Marginalia | Caveat | 1.05–1.25rem / 400, `inkSoft` |

---

## 4. Texture & material

The paper feeling comes from *restraint*, applied in three thin layers:

1. **Paper grain** — a single tiling SVG/PNG noise texture over `canvas`, opacity ≈ 3–5%. Barely perceptible. Never on top of text.
2. **Ruled lines** — optional faint horizontal `rule`-colored lines behind journal-like sections (e.g. the itinerary, notes). Think notebook feint ruling, very low contrast.
3. **Edges** — reserve deckled/torn or taped-corner edges for *hero* moments only (landing hero, a saved-trip "keepsake" card). Regular cards get clean, softly-rounded corners (radius 6–8px) and a 1px `rule` border, no heavy shadows. Shadows are soft, warm, and low (`0 2px 8px rgba(46,32,19,0.08)`).

If in doubt, use less texture.

---

## 5. The map (Mapbox)

This is the make-or-break surface. It must read as an **aged map page**, not a default web map.

- **Base style:** custom muted/vintage style — buff landmass (`canvas`/`paperSunk` family), faded muted water (`#a9c4c4`), minimal faded labels in `inkSoft`.
- **Contours / terrain:** faint brown contour lines where available — this is the cartographer's texture that sells the theme.
- **Trails:** ink-line strokes (`ink`) — consider a subtle dashed treatment for a hand-drawn feel. Selected/active trail switches to `ember`, slightly thicker.
- **User location dot:** re-skin the current Google-blue dot (`#4285F4` in `global.css`) to `ember` with a cream ring and a soft `ember` pulse — it currently breaks theme.
- **Map controls & popups:** styled as paper chrome (`paper` bg, `rule` border, `ink` text) — not default Mapbox white boxes.

---

## 6. Components

- **Buttons**
  - *Primary:* `ember` fill, `paper` text, subtle press-down. Reads like an inked stamp.
  - *Secondary:* `paper` fill, `ink` text, `rule` border.
  - *Ghost/tertiary:* `inkSoft` text, no border, ember on hover.
- **Cards / trail options** — "specimen cards": `paper` surface, `rule` hairline, Fraunces title, Work Sans metadata, optional Caveat one-line note. Selected state uses `emberWash` fill + `ember` border.
- **Inputs** — favor underline/ruled-line inputs (`rule` line, `ink` text) over heavy boxed fields, echoing writing on a line. Focus state: line thickens to `ember`.
- **Tabs / phase stepper** — the existing destination→gear→itinerary→finalize stepper stays, restyled with `ember` for active/done and `inkMuted` for pending. Consider a tab/divider treatment like journal section markers.
- **Chat (AI planner)** — the guide's field notes. AI prose in Spectral; user messages in a `paperSunk` bubble; occasional Caveat marginalia for tips. Keep the existing typing-dots animation.
- **Logo/mark** — the current mountain-triangle SVG stays conceptually but is redrawn to feel *hand-inked* (slightly irregular stroke) in `ink` with an `ember` peak.

---

## 7. Iconography & illustration

- **Icons:** thin, single-weight ink line icons (≈1.5px), lightly imperfect where possible. `ink`/`inkSoft` default, `ember` when active.
- **Illustration accents (sparingly):** botanical sprigs (fern, pine), a compass rose, contour swirls, a route dash-line motif. Used at section headers, empty states, and dividers — never behind content.
- **Trail blazes** as a recurring motif for waypoints/steps.

---

## 8. Motion

Quiet and organic — nothing bouncy or springy.
- Content **inks in**: fade + small upward drift (your existing `fadeIn` / `slideUp` keyframes are exactly right — keep them, ~200–300ms, ease-out).
- Hover states: gentle, ≤150ms.
- The only lively motion is the chat typing dots. Everything else settles calmly.

---

## 9. Voice & microcopy

Write like a knowledgeable trail guide jotting notes — warm, concise, a little wry. Empty states, tips, and confirmations are opportunities for a Caveat-styled aside ("Pack layers — the ridge gets breezy after 3pm."). Never corporate, never a wall of instructions.

---

## 10. Implementation notes

- **Extract tokens.** The palette currently lives inline as the `C` object inside `TripPlanner.jsx`. Promote these tokens to CSS custom properties in `src/styles/global.css` (`:root { --canvas: #f2e8d5; ... }`) and/or a shared `theme.js`, then consume them app-wide. Right now only the planner is themed; the map, profile, and gear pages are stock Tailwind and are what make the app look generic.
- **Fonts:** self-host Fraunces, Spectral, Work Sans, Caveat (subset for weight). Set them as Tailwind font families (`font-display`, `font-serif`, `font-sans`, `font-hand`).
- **Tailwind:** extend `tailwind.config.js` `theme.extend.colors` with the tokens above so utilities (`bg-canvas`, `text-ink`, `border-rule`, `text-ember`) work everywhere — this is how you kill the generic gray/green.
- **Rollout order:** (1) tokens + fonts + `global.css`, (2) map style — highest visual payoff, (3) shared Button/Card/Input primitives, (4) sweep the map/profile/gear pages off stock Tailwind, (5) illustration + texture polish.

---

## Do / Don't

**Do**
- Keep paper warm and text high-contrast.
- Let the map carry the vintage-cartography load.
- Use one lead accent per screen.

**Don't**
- Use pure black or white.
- Let Caveat near anything a user must read to act.
- Pile on texture, shadows, or torn edges.
- Leave any page on default Tailwind grays/greens — that's the look we're escaping.
