import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "../context/UserContext";

/* ─── Theme tokens ──────────────────────────────────────────────────────── */
const C = {
  backdrop:    "rgba(14, 10, 6, 0.82)",
  card:        "#1c1510",
  cardBorder:  "#4a3520",
  fieldBg:     "#241a10",
  fieldBorder: "#5a3e22",
  fieldFocus:  "#c8854a",
  fieldText:   "#e8d5b8",
  fieldPh:     "#7a5c3a",
  heading:     "#f0e6d0",
  subtext:     "#a08060",
  muted:       "#6a4e30",
  label:       "#b8906a",
  btnBg:       "#8b3a0f",
  btnHover:    "#a8471a",
  btnText:     "#fde8d0",
  btnBorder:   "#c05a2a",
  link:        "#d4874a",
  divider:     "#3a2510",
  errorBg:     "#2a100a",
  errorBorder: "#8b3020",
  errorText:   "#f0a090",
};

const serif = "Georgia, 'Times New Roman', serif";
const body  = "'Palatino Linotype', Palatino, Georgia, serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";

/* ─── Scenic backdrop ───────────────────────────────────────────────────── */
const SceneryBg = () => (
  <svg
    aria-hidden="true"
    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.18, pointerEvents: "none" }}
    viewBox="0 0 800 600"
    preserveAspectRatio="xMidYMid slice"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M0,380 L80,290 L160,340 L260,220 L370,310 L440,250 L520,300 L620,200 L700,270 L800,240 L800,600 L0,600 Z" fill="#2a1a08" />
    <path d="M0,440 L60,360 L130,400 L200,330 L300,390 L380,320 L480,380 L560,340 L650,390 L720,350 L800,380 L800,600 L0,600 Z" fill="#361e0a" />
    <path d="M-20,520 Q120,500 200,518 Q310,538 420,510 Q530,485 640,512 Q730,530 820,508" fill="none" stroke="#1a2e40" strokeWidth="28" opacity="0.7" />
    <path d="M-20,520 Q120,500 200,518 Q310,538 420,510 Q530,485 640,512 Q730,530 820,508" fill="none" stroke="#243a50" strokeWidth="14" opacity="0.5" />
    <path d="M0,560 Q200,540 400,555 Q600,572 800,548 L800,600 L0,600 Z" fill="#1a0e06" />
    <g fill="#1a2810">
      <polygon points="50,480 62,520 38,520" />
      <polygon points="50,460 65,480 35,480" />
      <polygon points="50,440 67,463 33,463" />
      <polygon points="720,470 732,510 708,510" />
      <polygon points="720,450 735,470 705,470" />
      <polygon points="720,430 737,453 703,453" />
      <polygon points="680,490 690,522 670,522" />
      <polygon points="680,473 692,492 668,492" />
    </g>
  </svg>
);

/* ─── Field ─────────────────────────────────────────────────────────────── */
const Field = ({ label, type = "text", value, onChange, placeholder, minLength }) => {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ marginBottom: "18px" }}>
      <label style={{
        display: "block", fontFamily: sans, fontSize: "11px", fontWeight: "600",
        color: focused ? C.label : C.muted, letterSpacing: "1.5px",
        textTransform: "uppercase", marginBottom: "7px", transition: "color 0.2s",
      }}>
        {label}
      </label>
      <input
        type={type} value={value} onChange={onChange}
        placeholder={placeholder} minLength={minLength} required
        style={{
          display: "block", width: "100%", boxSizing: "border-box",
          background: C.fieldBg,
          border: `1px solid ${focused ? C.fieldFocus : C.fieldBorder}`,
          borderRadius: "10px", padding: "12px 16px",
          color: C.fieldText, fontFamily: body, fontSize: "15px",
          outline: "none", transition: "border-color 0.2s",
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
    </div>
  );
};

/* ─── AuthModal ─────────────────────────────────────────────────────────── */
const AuthModal = () => {
  const { authModalOpen, setAuthModalOpen, login, createUser, loading, error, items: userItems } = useUser();
  const [isLoginView, setIsLoginView] = useState(true);
  const navigate = useNavigate();

  const [email,     setEmail]     = useState("");
  const [password,  setPassword]  = useState("");
  const [name,      setName]      = useState("");
  const [formError, setFormError] = useState("");

  if (!authModalOpen) return null;

  const validateEmail = (v) => {
    const re = /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/;
    if (!v) return "Email is required.";
    if (!re.test(v)) return "Enter a valid email address.";
    return null;
  };
  const validatePassword = (v) => {
    if (!v) return "Password is required.";
    if (v.length < 6) return "Password must be at least 6 characters.";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError("");
    const emailError = validateEmail(email);
    if (emailError) { setFormError(emailError); return; }

    try {
      if (isLoginView) {
        await login(email, password);
        // No navigation — closing the modal below leaves the user on
        // whatever page they were already on.
      } else {
        const pwError = validatePassword(password);
        if (pwError) { setFormError(pwError); return; }
        await createUser({ email, password, name, avatar_url: null, home_location: null, timezone: "UTC" });
        // Brand-new account always starts with onboarding.
        navigate("/onboarding");
      }

      if (setAuthModalOpen) setAuthModalOpen(false);
      setEmail(""); setPassword(""); setName("");
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 409) {
        setFormError("An account with this email already exists. Redirecting to login…");
        setTimeout(() => { setFormError(""); setIsLoginView(true); }, 2000);
        return;
      }
      if (Array.isArray(detail))           setFormError(detail[0].msg.split(": ")[1] || detail[0].msg);
      else if (typeof detail === "string") setFormError(detail);
      else                                 setFormError("Something went wrong. Please try again.");
    }
  };

  const handleToggleView = () => {
    setIsLoginView(!isLoginView);
    setEmail(""); setPassword(""); setName(""); setFormError("");
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: C.backdrop,
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 50, padding: "24px", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", inset: 0 }}>
        <SceneryBg />
      </div>

      <div style={{
        background: C.card, border: `1px solid ${C.cardBorder}`,
        borderRadius: "20px", padding: "2.25rem 2rem 1.75rem",
        width: "100%", maxWidth: "380px",
        position: "relative", zIndex: 2,
        boxShadow: "0 32px 80px rgba(0,0,0,0.6)",
      }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <svg width="56" height="30" viewBox="0 0 56 30" style={{ display: "block", margin: "0 auto 16px" }} xmlns="http://www.w3.org/2000/svg">
            <polygon points="28,2 48,28 8,28" fill="none" stroke="#7a5030" strokeWidth="1.2" strokeLinejoin="round" />
            <polygon points="14,28 28,8 42,28" fill="#2a1810" stroke="#5a3820" strokeWidth="1" strokeLinejoin="round" />
            <polygon points="28,2 33,10 23,10" fill="#8a6a50" />
            <path d="M0,28 Q14,24 28,27 Q42,30 56,26" fill="none" stroke="#1e3048" strokeWidth="2" strokeLinecap="round" />
          </svg>

          <h2 style={{ fontFamily: serif, fontSize: "28px", fontWeight: "normal", color: C.heading, margin: "0 0 6px", letterSpacing: "0.3px" }}>
            {isLoginView ? "Welcome back" : "Join the trail"}
          </h2>
          <p style={{ fontFamily: body, fontSize: "13px", color: C.subtext, margin: 0, fontStyle: "italic" }}>
            {isLoginView ? "The mountains are calling." : "Your next adventure starts here."}
          </p>
        </div>

        {/* Divider */}
        <div style={{
          height: "1px",
          background: `linear-gradient(to right, transparent, ${C.divider} 30%, ${C.cardBorder} 50%, ${C.divider} 70%, transparent)`,
          marginBottom: "1.75rem",
        }} />

        {/* Error */}
        {(formError || error) && (
          <div style={{
            background: C.errorBg, border: `1px solid ${C.errorBorder}`,
            color: C.errorText, borderRadius: "10px",
            padding: "11px 14px", marginBottom: "16px",
            fontFamily: sans, fontSize: "12px", lineHeight: "1.5",
          }}>
            {formError || error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {!isLoginView && (
            <Field label="Name" value={name} onChange={e => setName(e.target.value)} placeholder="Your name" />
          )}
          <Field label="Email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
          <div>
            <Field label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" minLength={6} />
            {!isLoginView && (
              <p style={{ marginTop: "-10px", marginBottom: "18px", fontFamily: sans, fontSize: "11px", color: C.muted }}>
                Minimum 6 characters
              </p>
            )}
          </div>

          <button
            type="submit" disabled={loading}
            style={{
              width: "100%",
              background: loading ? "#4a2810" : C.btnBg,
              border: `1px solid ${loading ? "#3a1e0a" : C.btnBorder}`,
              borderRadius: "10px", padding: "13px 16px",
              color: loading ? C.muted : C.btnText,
              fontFamily: sans, fontSize: "13px", fontWeight: "600",
              letterSpacing: "1px", cursor: loading ? "not-allowed" : "pointer",
              marginBottom: "18px", transition: "background 0.2s",
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.background = C.btnHover; }}
            onMouseLeave={e => { if (!loading) e.currentTarget.style.background = C.btnBg; }}
          >
            {loading ? "One moment…" : (isLoginView ? "Continue" : "Create account")}
          </button>
        </form>

        <div style={{ textAlign: "center", fontFamily: body, fontSize: "13px", color: C.subtext }}>
          {isLoginView ? "New here? " : "Already have an account? "}
          <button
            type="button" onClick={handleToggleView} disabled={loading}
            style={{
              background: "none", border: "none", padding: 0,
              color: C.link, fontFamily: body, fontSize: "13px",
              fontStyle: "italic", textDecoration: "underline",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {isLoginView ? "Create an account" : "Log in"}
          </button>
        </div>

        <p style={{ textAlign: "center", fontFamily: sans, fontSize: "11px", color: C.muted, margin: "20px 0 0", letterSpacing: "0.5px" }}>
          Leave no trace · Stay on the trail
        </p>
      </div>
    </div>
  );
};

export default AuthModal;