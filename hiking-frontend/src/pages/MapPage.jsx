import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

// Set your token here
mapboxgl.accessToken = "YOUR_MAPBOX_ACCESS_TOKEN";

import FilterBar from "../components/FilterBar";
import HikeSummaryCard from "../components/HikeSummaryCard";
import MapLegend from "../components/MapLegend";
import { useUserLocation } from "../components/UserLocation";

export default function MapPage() {
  const navigate = useNavigate();
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markers = useRef([]); // To keep track of markers and remove old ones

  const [hikes, setHikes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    maxDistanceMiles: null,
    difficulty: null,
    minLengthMiles: null,
    meetRequirementsOnly: false
  });

  const { location, loading: locationLoading, error: locationError } = useUserLocation();

  /* -----------------------------
     Initialize Map
  ------------------------------*/
  useEffect(() => {
    if (map.current) return; // Initialize map only once
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/outdoors-v12", // Great style for hiking
      center: [-122.4194, 37.7749], // Default center (SF)
      zoom: 9
    });

    map.current.addControl(new mapboxgl.NavigationControl(), "top-right");
  }, []);

  /* -----------------------------
     Fetch Hikes
  ------------------------------*/
  useEffect(() => {
    const fetchHikes = async () => {
      setLoading(true);
      try {
        const response = await fetch("/api/hikes/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filters, userLocation: location })
        });
        const data = await response.json();
        setHikes(data);
      } catch (err) {
        console.error("Failed to load hikes", err);
      } finally {
        setLoading(false);
      }
    };

    if (location || !filters.maxDistanceMiles) {
      fetchHikes();
    }
  }, [filters, location]);

  /* -----------------------------
     Update Map Markers
  ------------------------------*/
  useEffect(() => {
    if (!map.current) return;

    // Clear existing markers
    markers.current.forEach((m) => m.remove());
    markers.current = [];

    // Add new markers
    hikes.forEach((hike) => {
      // Assuming hike.geometry contains [longitude, latitude]
      const coords = hike.geometry?.coordinates || [0, 0];
      
      const marker = new mapboxgl.Marker({ color: "#22c55e" }) // Tailwind green-500
        .setLngLat(coords)
        .setPopup(new mapboxgl.Popup().setHTML(`<h4>${hike.name}</h4>`))
        .addTo(map.current);

      marker.getElement().addEventListener('click', () => {
        navigate(`/hikes/${hike.id}`);
      });

      markers.current.push(marker);
    });

    // Fit map to markers if they exist
    if (hikes.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      hikes.forEach(h => bounds.extend(h.geometry.coordinates));
      map.current.fitBounds(bounds, { padding: 50 });
    }
  }, [hikes, navigate]);

  return (
    <div className="flex h-screen">
      {/* LEFT: Mapbox */}
      <div className="relative flex-1">
        <div ref={mapContainer} className="h-full w-full" />
        <MapLegend />
      </div>

      {/* RIGHT: Controls + Results */}
      <div className="w-96 border-l bg-gray-50 flex flex-col">
        <div className="p-4 border-b">
          <FilterBar filters={filters} onChange={setFilters} />
          {locationLoading && <p className="text-xs text-gray-500 mt-2">Getting your location...</p>}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading && <p className="text-center text-gray-500">Loading hikes...</p>}
          {hikes.map((hike) => (
            <HikeSummaryCard key={hike.id} hike={hike} />
          ))}
        </div>
      </div>
    </div>
  );
}