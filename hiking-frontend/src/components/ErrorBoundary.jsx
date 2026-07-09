import { Component } from "react";

/**
 * Top-level error boundary. Without one, any render/runtime exception in a page
 * unmounts the whole React tree and white-screens the SPA. This catches it and
 * shows a recoverable fallback instead.
 *
 * Class component on purpose — componentDidCatch / getDerivedStateFromError have
 * no hook equivalent; this is the one place React still requires a class.
 */

// Field Journal (Daylight Paper) palette — matches AuthModal's tokens.
const C = {
  pageBg:  "#ded1ad", // paper, sunk
  card:    "#ebe0c2", // paper
  border:  "#a2855a",
  ink:     "#3d2817",
  inkSoft: "#5c3a21",
  muted:   "#6a4a26",
  ember:   "#a83b2c",
  emberText: "#f7efd8",
};

const serif = '"Fraunces", Georgia, serif';
const sans  = '"Work Sans", system-ui, sans-serif';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Surface it in the console for debugging; a real deployment could forward
    // this to an error-reporting service here.
    console.error("Uncaught error in React tree:", error, info);
  }

  handleReload = () => {
    // Full reload is the most reliable recovery — it re-mounts the tree and
    // re-runs data fetches from a clean slate.
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          background: C.pageBg,
          fontFamily: sans,
        }}
      >
        <div
          style={{
            maxWidth: "420px",
            width: "100%",
            textAlign: "center",
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: "10px",
            padding: "36px 28px",
            boxShadow: "0 8px 24px rgba(61, 40, 23, 0.18)",
          }}
        >
          <div style={{ fontSize: "34px", marginBottom: "8px" }}>🧭</div>
          <h1
            style={{
              fontFamily: serif,
              fontSize: "24px",
              color: C.ink,
              margin: "0 0 10px",
            }}
          >
            We lost the trail
          </h1>
          <p
            style={{
              fontFamily: serif,
              fontSize: "15px",
              lineHeight: 1.5,
              color: C.inkSoft,
              margin: "0 0 24px",
            }}
          >
            Something went wrong while loading this page. Reloading usually gets
            you back on track — your saved trips and gear are safe.
          </p>
          <button
            onClick={this.handleReload}
            style={{
              fontFamily: sans,
              fontSize: "13px",
              fontWeight: 600,
              letterSpacing: "1px",
              textTransform: "uppercase",
              color: C.emberText,
              background: C.ember,
              border: `1px solid ${C.ember}`,
              borderRadius: "6px",
              padding: "11px 22px",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
