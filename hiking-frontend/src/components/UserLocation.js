// components/UserLocation.jsx
import { useState, useEffect } from "react";

export function useUserLocation() {
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setError("Geolocation not supported by your browser.");
      setLoading(false);
      return;
    }

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
  }, []);

  return { location, loading, error };
}