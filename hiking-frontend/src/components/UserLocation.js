// components/UserLocation.jsx
import { useState, useEffect } from "react";

export function useUserLocation() {
  // Geolocation support is a stable browser capability — decide it at render so
  // the effect never has to setState synchronously for the unsupported case
  // (react-hooks/set-state-in-effect). When unsupported we start already-settled:
  // not loading, with the error message; the effect below then does nothing.
  const geoSupported = typeof navigator !== "undefined" && "geolocation" in navigator;
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(geoSupported);
  const [error, setError] = useState(
    geoSupported ? null : "Geolocation not supported by your browser."
  );

  useEffect(() => {
    if (!geoSupported) return;

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const newLat = position.coords.latitude;
        const newLng = position.coords.longitude;

        setLocation((prev) => {
          // If coords haven't moved more than ~100m, return the same
          // reference so React skips the re-render entirely
          if (
            prev &&
            Math.abs(newLat - prev.lat) < 0.001 &&
            Math.abs(newLng - prev.lng) < 0.001
          ) {
            return prev;
          }
          return { lat: newLat, lng: newLng };
        });

        setLoading(false);
      },
      (err) => {
        setError(err.message);
        setLoading(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000,
      }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [geoSupported]);

  return { location, loading, error };
}