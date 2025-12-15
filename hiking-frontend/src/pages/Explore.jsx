import { useEffect } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import { useHikes } from "../context/HikeContext";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

const Explore = () => {
  const {
    hikes,
    fetchHikes,
    setSelectedHike,
    loading,
    error
  } = useHikes();

  useEffect(() => {
    fetchHikes();
  }, []);

  useEffect(() => {
    if (!hikes || hikes.length === 0) return;

    const map = new mapboxgl.Map({
      container: "map",
      style: "mapbox://styles/mapbox/outdoors-v12",
      center: [-98.5795, 39.8283], // center of US
      zoom: 3
    });

    hikes.forEach((hike) => {
      if (!hike.longitude || !hike.latitude) return;

      const marker = new mapboxgl.Marker()
        .setLngLat([hike.longitude, hike.latitude])
        .addTo(map);

      marker.getElement().addEventListener("click", () => {
        setSelectedHike(hike);
      });
    });

    return () => map.remove();
  }, [hikes]);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Map */}
      <div
        id="map"
        style={{ flex: 3 }}
      />

      {/* Side Panel */}
      <div style={{ flex: 1, padding: "1rem", overflowY: "auto" }}>
        <h2>Explore Hikes</h2>

        {loading && <p>Loading hikes...</p>}
        {error && <p>Error loading hikes</p>}

        {hikes.map((hike) => (
          <div
            key={hike.id}
            style={{
              border: "1px solid #ccc",
              padding: "0.75rem",
              marginBottom: "0.75rem",
              cursor: "pointer"
            }}
            onClick={() => setSelectedHike(hike)}
          >
            <h4>{hike.name}</h4>
            <p>{hike.distance} miles</p>
            <p>{hike.elevation_gain} ft gain</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Explore;
