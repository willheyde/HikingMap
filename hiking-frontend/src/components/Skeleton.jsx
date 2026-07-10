/**
 * Skeleton loading placeholders (Field Journal theme).
 *
 * A shimmer sweeps across paper-toned blocks while real content loads, so a page
 * shows its shape immediately instead of a blank panel or a bare spinner.
 *
 *   <Skeleton />                      — one block, sized via props
 *   <HikeCardSkeleton />              — mirrors HikeSummaryCard's layout
 *   <HikeCardSkeletonList count={6}/> — a stack of card skeletons
 *   <HikeDetailSkeleton />            — full detail-page placeholder
 *
 * The shimmer keyframe (`skeleton-shimmer`) and reduced-motion handling live in
 * styles/global.css.
 */

// Paper tones so placeholders read as aged paper, not grey web boilerplate.
const BASE   = "#dccca5"; // paper-sunk base
const SHEEN  = "#efe6cc"; // lighter sweep band
const CARD   = "#ebe0c2"; // card paper
const BORDER = "rgba(162,133,90,0.5)";

/** One shimmering placeholder block. */
export function Skeleton({
  width = "100%",
  height = 12,
  radius = 6,
  style = {},
}) {
  return (
    <span
      className="skeleton-block"
      aria-hidden="true"
      style={{
        display: "block",
        width,
        height,
        borderRadius: radius,
        // A three-stop gradient wider than the element; animating its position
        // slides the light band across.
        background: `linear-gradient(90deg, ${BASE} 25%, ${SHEEN} 50%, ${BASE} 75%)`,
        backgroundSize: "200% 100%",
        animation: "skeleton-shimmer 1.4s ease-in-out infinite",
        ...style,
      }}
    />
  );
}

/** Placeholder shaped like one HikeSummaryCard (128px row in the list). */
export function HikeCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      style={{
        background: CARD,
        border: `1px solid ${BORDER}`,
        borderRadius: 12,
        height: "100%",
        padding: "14px 16px",
        boxSizing: "border-box",
      }}
    >
      {/* Name + difficulty badge */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
        <Skeleton width="58%" height={14} />
        <Skeleton width={58} height={16} radius={9999} />
      </div>
      {/* Region line */}
      <Skeleton width="42%" height={10} style={{ marginBottom: 14 }} />
      {/* Stats row */}
      <div style={{ display: "flex", gap: 12 }}>
        <Skeleton width={46} height={11} />
        <Skeleton width={62} height={11} />
        <Skeleton width={54} height={11} />
      </div>
    </div>
  );
}

/** A vertical stack of card skeletons, spaced to match the real list rows. */
export function HikeCardSkeletonList({ count = 6, rowHeight = 128 }) {
  return (
    <div aria-busy="true" aria-label="Loading trails">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ height: rowHeight, padding: "4px 12px", boxSizing: "border-box" }}>
          <HikeCardSkeleton />
        </div>
      ))}
    </div>
  );
}

/** Full-page placeholder for the hike detail view. */
export function HikeDetailSkeleton() {
  return (
    <div
      aria-busy="true"
      aria-label="Loading trail details"
      style={{ maxWidth: 720, margin: "0 auto", padding: "32px 24px" }}
    >
      <Skeleton width="60%" height={30} radius={8} style={{ marginBottom: 14 }} />
      <Skeleton width="35%" height={14} style={{ marginBottom: 28 }} />

      {/* Stat tiles */}
      <div style={{ display: "flex", gap: 12, marginBottom: 28 }}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} width="100%" height={64} radius={10} />
        ))}
      </div>

      {/* Body copy lines */}
      {["92%", "97%", "85%", "70%"].map((w, i) => (
        <Skeleton key={i} width={w} height={12} style={{ marginBottom: 12 }} />
      ))}
    </div>
  );
}

export default Skeleton;
