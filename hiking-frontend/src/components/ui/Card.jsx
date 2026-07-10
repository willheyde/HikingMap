/* ─── Card — Field Journal "specimen card" primitive (hikeStyle.md §6) ───────
   Paper surface, rule hairline, soft warm shadow. `selected` switches to an
   ember-wash fill + ember border. `interactive` adds hover lift for clickables.
   Compose freely; pass style to override.                                     */
import { palette as P } from "../../styles/theme";

export default function Card({
  selected = false,
  interactive = false,
  style = {},
  children,
  ...props
}) {
  const base = {
    background:   selected ? P.emberWash : P.paper,
    border:       `1px solid ${selected ? P.ember : P.rule}`,
    borderRadius: 8,
    boxShadow:    `0 2px 8px ${P.shadow}`,
    transition:   "border-color 0.15s, box-shadow 0.15s, transform 0.1s",
  };

  return (
    <div
      {...props}
      style={{ ...base, ...style }}
      onMouseEnter={(e) => {
        if (interactive && !selected) {
          e.currentTarget.style.borderColor = P.ember;
          e.currentTarget.style.boxShadow   = `0 4px 14px ${P.shadow}`;
        }
        props.onMouseEnter?.(e);
      }}
      onMouseLeave={(e) => {
        if (interactive && !selected) {
          e.currentTarget.style.borderColor = P.rule;
          e.currentTarget.style.boxShadow   = `0 2px 8px ${P.shadow}`;
        }
        props.onMouseLeave?.(e);
      }}
    >
      {children}
    </div>
  );
}
