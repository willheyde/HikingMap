import { useEffect, useRef } from "react";

/*
 * GoogleSignInButton — renders Google's official "Sign in with Google" button
 * via Google Identity Services (GIS) and returns the resulting ID token
 * (credential) through onCredential.
 *
 * Config: set VITE_GOOGLE_CLIENT_ID (the OAuth client ID from the Google Cloud
 * Console) in the frontend env. Without it the component renders nothing, so the
 * modal degrades gracefully to email/password until Google login is configured.
 *
 * The GIS script is loaded once, and initialize() is called at most once for the
 * whole app (GSI warns and keeps only the last call otherwise). renderButton
 * still runs per mount, into a freshly-cleared container.
 */

const GIS_SRC = "https://accounts.google.com/gsi/client";
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// Module-level promise so the <script> is injected at most once even if several
// buttons mount (or React StrictMode double-invokes effects in dev).
let gisPromise = null;
const loadGis = () => {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (gisPromise) return gisPromise;
  gisPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = () => {
      gisPromise = null; // allow a retry on a later mount
      reject(new Error("Failed to load Google Identity Services"));
    };
    document.head.appendChild(script);
  });
  return gisPromise;
};

// initialize() must run once per page (StrictMode double-mounts and modal
// re-opens would otherwise call it repeatedly, which GSI warns about). We hold
// the current handlers in a module-level ref so a once-only initialize still
// dispatches to whatever the latest mounted button passed in.
let gisInitialized = false;
const handlers = { onCredential: null, onError: null };

const initializeGisOnce = () => {
  if (gisInitialized) return;
  window.google.accounts.id.initialize({
    client_id: CLIENT_ID,
    callback: (response) => {
      // response.credential is the Google ID token (a JWT). Hand it up; the
      // backend verifies it — the client never asserts its own identity.
      if (response?.credential) handlers.onCredential?.(response.credential);
      else handlers.onError?.(new Error("No credential returned from Google"));
    },
  });
  gisInitialized = true;
};

const GoogleSignInButton = ({ onCredential, onError }) => {
  const containerRef = useRef(null);

  // Keep the module-level handlers pointed at this mount's callbacks, so the
  // once-only initialize() above always dispatches to the current button.
  useEffect(() => {
    handlers.onCredential = onCredential;
    handlers.onError = onError;
  }, [onCredential, onError]);

  useEffect(() => {
    if (!CLIENT_ID) return; // not configured — nothing to render
    let cancelled = false;

    loadGis()
      .then(() => {
        // In StrictMode the first mount is torn down before the script resolves,
        // so `cancelled` short-circuits it and only the surviving mount renders
        // a button — avoiding a duplicate button-iframe request.
        if (cancelled || !containerRef.current) return;

        initializeGisOnce();

        containerRef.current.innerHTML = ""; // guard against stacking
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: "outline",        // white/bordered — suits the paper modal
          size: "large",
          type: "standard",
          text: "continue_with",
          shape: "pill",
          logo_alignment: "center",
          width: 316,
        });
      })
      .catch((err) => {
        if (!cancelled) handlers.onError?.(err);
      });

    return () => { cancelled = true; };
  }, []);

  if (!CLIENT_ID) return null;

  // Google renders its (fixed-width) button into this centered container.
  return (
    <div
      ref={containerRef}
      style={{ display: "flex", justifyContent: "center", minHeight: "44px" }}
    />
  );
};

export default GoogleSignInButton;
