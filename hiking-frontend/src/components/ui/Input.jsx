/* ─── Input — Field Journal "writing on a line" primitive (hikeStyle.md §6) ──
   Ruled-line input: a single rule underline that thickens to ember on focus,
   echoing writing on a notebook line. Set `boxed` for a bordered field
   (better for multiline). `multiline` renders a <textarea>. Optional `label`
   in Work Sans sits above.                                                    */
import { useState, useId } from "react";
import { palette as P, fonts } from "../../styles/theme";

export default function Input({
  label,
  boxed = false,
  multiline = false,
  rows = 3,
  style = {},
  id,
  ...props
}) {
  const [focused, setFocused] = useState(false);
  const autoId = useId();
  const inputId = id ?? autoId;
  const Tag = multiline ? "textarea" : "input";

  const fieldStyle = boxed
    ? {
        background:   P.paperSunk,
        border:       `1px solid ${focused ? P.ember : P.rule}`,
        borderRadius: 6,
        padding:      "9px 12px",
      }
    : {
        background:    "transparent",
        border:        "none",
        borderBottom:  `${focused ? 2 : 1}px solid ${focused ? P.ember : P.rule}`,
        borderRadius:  0,
        padding:       "6px 2px",
        // keep text from shifting when the border grows on focus
        marginBottom:  focused ? 0 : 1,
      };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            fontFamily: fonts.sans, fontSize: 12, fontWeight: 500,
            color: P.inkSoft, letterSpacing: "0.3px",
          }}
        >
          {label}
        </label>
      )}
      <Tag
        id={inputId}
        rows={multiline ? rows : undefined}
        {...props}
        onFocus={(e) => { setFocused(true);  props.onFocus?.(e); }}
        onBlur={(e)  => { setFocused(false); props.onBlur?.(e);  }}
        style={{
          fontFamily: fonts.sans,
          fontSize:   14,
          color:      P.ink,
          outline:    "none",
          width:      "100%",
          boxSizing:  "border-box",
          resize:     multiline ? "vertical" : undefined,
          ...fieldStyle,
          ...style,
        }}
      />
    </div>
  );
}
