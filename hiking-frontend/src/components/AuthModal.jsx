import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "../context/useUser";
import GoogleSignInButton from "./GoogleSignInButton";

/* ─── Theme tokens ──────────────────────────────────────────────────────── */
const C = {
  backdrop:    "rgba(46, 32, 19, 0.45)", // warm scrim
  card:        "#ebe0c2", // paper
  cardBorder:  "#a2855a", // rule
  fieldBg:     "#ccb98f", // paper-sunk
  fieldBorder: "#a2855a", // rule
  fieldFocus:  "#a83b2c", // ember
  fieldText:   "#3d2817", // ink
  fieldPh:     "#6a4a26", // ink-muted
  heading:     "#3d2817", // ink
  subtext:     "#5c3a21", // ink-soft
  muted:       "#6a4a26", // ink-muted
  label:       "#a83b2c", // ember
  btnBg:       "#a83b2c", // ember
  btnHover:    "#8e3022", // ember-hover
  btnText:     "#ebe0c2", // on-ember
  btnBorder:   "#8e3022",
  link:        "#a83b2c", // ember
  divider:     "#a2855a", // rule
  errorBg:     "#e6c29a", // rust-wash
  errorBorder: "rgba(150,48,31,0.4)",
  errorText:   "#96301f", // rust
};

const serif = "'Fraunces', Georgia, serif";
const body  = "'Spectral', Georgia, serif";
const sans  = "'Work Sans', 'Trebuchet MS', sans-serif";

/* ─── Scenic backdrop ───────────────────────────────────────────────────── */
const SceneryBg = () => (
  <svg
    aria-hidden="true"
    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.22, pointerEvents: "none" }}
    viewBox="0 0 800 600"
    preserveAspectRatio="xMidYMid slice"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M0,380 L80,290 L160,340 L260,220 L370,310 L440,250 L520,300 L620,200 L700,270 L800,240 L800,600 L0,600 Z" fill="#8a7256" />
    <path d="M0,440 L60,360 L130,400 L200,330 L300,390 L380,320 L480,380 L560,340 L650,390 L720,350 L800,380 L800,600 L0,600 Z" fill="#5c3a21" />
    <path d="M-20,520 Q120,500 200,518 Q310,538 420,510 Q530,485 640,512 Q730,530 820,508" fill="none" stroke="#a2855a" strokeWidth="28" opacity="0.7" />
    <path d="M-20,520 Q120,500 200,518 Q310,538 420,510 Q530,485 640,512 Q730,530 820,508" fill="none" stroke="#9ab5b5" strokeWidth="14" opacity="0.5" />
    <path d="M0,560 Q200,540 400,555 Q600,572 800,548 L800,600 L0,600 Z" fill="#4a3a28" />
    <g fill="#6e5a2e">
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
  const { authModalOpen, setAuthModalOpen, login, loginWithGoogle, createUser, loading, error } = useUser();
  const [isLoginView, setIsLoginView] = useState(true);
  const navigate = useNavigate();

  const [email,     setEmail]     = useState("");
  const [password,  setPassword]  = useState("");
  const [name,      setName]      = useState("");
  const [formError, setFormError] = useState("");

  // Google returns an ID token; hand it to the backend via the context. A
  // brand-new account starts onboarding, same as email signup; a returning
  // user just closes the modal and stays where they were. Defined here (before
  // the early return below) so the Hooks are called unconditionally every render.
  const handleGoogleCredential = useCallback(async (credential) => {
    setFormError("");
    try {
      const { isNew } = await loginWithGoogle(credential);
      if (isNew) navigate("/onboarding");
    } catch (err) {
      setFormError(err.message || "Google sign-in failed. Please try again.");
    }
  }, [loginWithGoogle, navigate]);

  const handleGoogleError = useCallback(() => {
    setFormError("Couldn't reach Google sign-in. Check your connection and try again.");
  }, []);

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
        boxShadow: "0 24px 60px rgba(61,40,23,0.20)",
      }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <svg width="56" height="30" viewBox="0 0 56 30" style={{ display: "block", margin: "0 auto 16px" }} xmlns="http://www.w3.org/2000/svg">
            <polygon points="28,2 48,28 8,28" fill="none" stroke="#5c3a21" strokeWidth="1.2" strokeLinejoin="round" />
            <polygon points="14,28 28,8 42,28" fill="#e4cb9e" stroke="#8a7256" strokeWidth="1" strokeLinejoin="round" />
            <polygon points="28,2 33,10 23,10" fill="#ebe0c2" />
            <path d="M0,28 Q14,24 28,27 Q42,30 56,26" fill="none" stroke="#a2855a" strokeWidth="2" strokeLinecap="round" />
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

        {/* Google sign-in — renders only when VITE_GOOGLE_CLIENT_ID is set */}
        <GoogleSignInButton
          onCredential={handleGoogleCredential}
          onError={handleGoogleError}
        />

        {/* "or" separator (only meaningful alongside the Google button, but
            harmless if that renders nothing) */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "18px 0" }}>
          <div style={{ flex: 1, height: "1px", background: C.divider }} />
          <span style={{ fontFamily: sans, fontSize: "10px", color: C.muted, letterSpacing: "1.5px", textTransform: "uppercase" }}>
            or
          </span>
          <div style={{ flex: 1, height: "1px", background: C.divider }} />
        </div>

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
              background: loading ? "#ccb98f" : C.btnBg,
              border: `1px solid ${loading ? "#a2855a" : C.btnBorder}`,
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