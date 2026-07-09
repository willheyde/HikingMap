/* ─── Button — Field Journal primitive (hikeStyle.md §6) ─────────────────────
   Variants:
     primary   — ember fill, paper text; reads like an inked stamp
     secondary — paper fill, ink text, rule border
     ghost     — inkSoft text, no border; ember on hover
   Sizes: sm | md | lg. Forwards any style/props overrides.                    */
import { palette as P, fonts } from "../../styles/theme";

const SIZES = {
  sm: { padding: "6px 12px",  fontSize: 12.5 },
  md: { padding: "9px 16px",  fontSize: 14   },
  lg: { padding: "12px 22px", fontSize: 15.5 },
};

const VARIANTS = {
  primary: {
    base:  { background: P.ember,  color: P.onEmber, border: `1px solid ${P.ember}` },
    hover: { background: P.emberHover, borderColor: P.emberHover },
  },
  secondary: {
    base:  { background: P.paper,  color: P.ink, border: `1px solid ${P.rule}` },
    hover: { background: P.paperSunk, borderColor: P.ember },
  },
  ghost: {
    base:  { background: "transparent", color: P.inkSoft, border: "1px solid transparent" },
    hover: { color: P.ember },
  },
};

export default function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  style = {},
  children,
  ...props
}) {
  const v = VARIANTS[variant] ?? VARIANTS.primary;
  const s = SIZES[size] ?? SIZES.md;

  return (
    <button
      disabled={disabled}
      {...props}
      style={{
        fontFamily:   fonts.sans,
        fontWeight:   500,
        fontSize:     s.fontSize,
        padding:      s.padding,
        borderRadius: 7,
        cursor:       disabled ? "not-allowed" : "pointer",
        opacity:      disabled ? 0.5 : 1,
        letterSpacing:"0.2px",
        transition:   "background 0.15s, border-color 0.15s, color 0.15s, transform 0.05s",
        ...v.base,
        ...style,
      }}
      onMouseEnter={(e) => {
        if (disabled) return;
        Object.assign(e.currentTarget.style, v.hover);
        props.onMouseEnter?.(e);
      }}
      onMouseLeave={(e) => {
        if (disabled) return;
        Object.assign(e.currentTarget.style, v.base, style);
        props.onMouseLeave?.(e);
      }}
      onMouseDown={(e) => {
        if (!disabled) e.currentTarget.style.transform = "translateY(1px)";
        props.onMouseDown?.(e);
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        props.onMouseUp?.(e);
      }}
    >
      {children}
    </button>
  );
}
