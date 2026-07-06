/* ─── AmbientHue — animated background glow ──────────────────────────────────
   Self-contained: owns its own keyframes so it can be dropped in anywhere
   without depending on GlobalStyles being present.
   ──────────────────────────────────────────────────────────────────────────── */

const AmbientHueKeyframes = () => (
  <style>{`
    @keyframes huePulse {
      0%   { opacity: 0.55; transform: scale(1);    }
      50%  { opacity: 0.80; transform: scale(1.08); }
      100% { opacity: 0.55; transform: scale(1);    }
    }
    @keyframes hueShift {
      0%   { opacity: 0.30; transform: scale(1)    translateY(0px);   }
      50%  { opacity: 0.50; transform: scale(1.12) translateY(-12px); }
      100% { opacity: 0.30; transform: scale(1)    translateY(0px);   }
    }
    @keyframes hueOrbit {
      0%   { transform: translate(-50%,-50%) rotate(0deg)   scale(1); }
      100% { transform: translate(-50%,-50%) rotate(360deg) scale(1); }
    }
  `}</style>
);

export default function AmbientHue() {
  return (
    <>
      <AmbientHueKeyframes />
      <div style={{
        position: "absolute", inset: 0,
        pointerEvents: "none", overflow: "hidden",
        zIndex: 0,
      }}>
        {/* Core amber orb */}
        <div style={{
          position: "absolute",
          left: "50%", top: "48%",
          transform: "translate(-50%, -50%)",
          width: 520, height: 380,
          borderRadius: "50%",
          background: "radial-gradient(ellipse at center, rgba(193,122,46,0.22) 0%, rgba(193,122,46,0.08) 45%, transparent 72%)",
          animation: "huePulse 6s ease-in-out infinite",
        }} />

        {/* Warm outer bloom */}
        <div style={{
          position: "absolute",
          left: "50%", top: "50%",
          transform: "translate(-50%, -50%)",
          width: 820, height: 560,
          borderRadius: "50%",
          background: "radial-gradient(ellipse at center, rgba(160,80,20,0.10) 0%, rgba(100,40,10,0.05) 50%, transparent 75%)",
          animation: "hueShift 9s ease-in-out infinite",
        }} />

        {/* Cool deep-red counter-bloom for depth */}
        <div style={{
          position: "absolute",
          left: "50%", top: "60%",
          transform: "translate(-50%, -50%)",
          width: 600, height: 300,
          borderRadius: "50%",
          background: "radial-gradient(ellipse at center, rgba(80,20,5,0.18) 0%, transparent 70%)",
          animation: "huePulse 11s ease-in-out 2s infinite",
        }} />

        {/* Subtle top highlight */}
        <div style={{
          position: "absolute",
          left: "50%", top: "28%",
          transform: "translate(-50%, -50%)",
          width: 260, height: 180,
          borderRadius: "50%",
          background: "radial-gradient(ellipse at center, rgba(220,150,60,0.09) 0%, transparent 70%)",
          animation: "hueShift 7s ease-in-out 1s infinite",
        }} />
      </div>
    </>
  );
}