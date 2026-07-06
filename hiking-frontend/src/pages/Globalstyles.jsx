/* ─── GlobalStyles — app-wide keyframes + scrollbar ──────────────────────────
   Covers all animations used by chat/message components (bounce, fadeIn,
   slideUp). Mount once at the top of TripPlanner.
   Hue animations live in AmbientHue.jsx so that component is portable.
   ──────────────────────────────────────────────────────────────────────────── */

// Matches C.scrollbar in TripPlanner's design tokens
const SCROLLBAR_COLOR = "#3a2510";

export default function GlobalStyles() {
  return (
    <style>{`
      @keyframes bounce {
        0%,60%,100% { transform: translateY(0);    opacity: 0.4; }
        30%          { transform: translateY(-5px); opacity: 1;   }
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(6px);  }
        to   { opacity: 1; transform: translateY(0);    }
      }
      @keyframes slideUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0);    }
      }

      ::-webkit-scrollbar       { width: 4px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: ${SCROLLBAR_COLOR}; border-radius: 2px; }
    `}</style>
  );
}