import { useEffect, useState, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import FilterBar from "../components/FilterBar";
import HikeSummaryCard from "../components/HikeSummaryCard";
import MapLegend from "../components/MapLegend";
import { useUserLocation } from "../components/UserLocation";
import { useHikes } from "../context/HikeContext";
import { useUser } from "../context/UserContext";
import AuthModal from "../components/AuthModal";
// Mapbox token
mapboxgl.accessToken = MapAccess;

export default function MapPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markers = useRef([]);
  const trailLayers = useRef(new Set());
  
  // 1. Destructure 'user' here so we have access to the ID
  const { user, setGlobalUserLocation } = useUser();
  
  const userMarkerRef = useRef(null);
  const { hikes, loading, searchHikes, selectHike } = useHikes();
  const { authModalOpen } = AuthModal.authModalOpen ? AuthModal : { authModalOpen: false };
  const [filters, setFilters] = useState({
    maxDistanceMiles: null,
    difficulty: null,
    minLengthMiles: null,
    maxLengthMiles: null,
    meetRequirementsOnly: false,
    state: null,
    region: null,
    month: null
  });

  const {
    location: userLocation,
    loading: locationLoading,
    error: locationError
  } = useUserLocation();

  const searchHikesRef = useRef(searchHikes);
  useEffect(() => {
    searchHikesRef.current = searchHikes;
  }, [searchHikes]);

  /* -----------------------------
      Initialize Map
  ------------------------------*/
  useEffect(() => {
    if (map.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/outdoors-v12",
      center: [-98.5795, 39.8283],
      zoom: 4
    });

    map.current.addControl(
      new mapboxgl.NavigationControl(),
      "top-right"
    );
  }, []);
  useEffect(() => {
    // Sync local hook data to Global Context
    if (!authModalOpen && userLocation) {
      setGlobalUserLocation(userLocation);
    }

    // If map isn't ready or no location, do nothing
    if (!map.current || !userLocation) return;

    // Create the DOM element for the marker
    const el = document.createElement('div');
    el.className = 'user-location-dot';

    // If marker already exists, just update position
    if (userMarkerRef.current) {
      userMarkerRef.current.setLngLat([userLocation.lng, userLocation.lat]);
    } else {
      // Create new marker
      userMarkerRef.current = new mapboxgl.Marker(el)
        .setLngLat([userLocation.lng, userLocation.lat])
        .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML("<strong>You are here</strong>"))
        .addTo(map.current);
    }

  }, [userLocation, setGlobalUserLocation]);
  /* -----------------------------
      Search Hikes
  ------------------------------*/
  useEffect(() => {
    let active = true;
    let timer = null;

    const runSearch = () => {
      if (!active) return;

      const searchParams = {};

      // 1. Trail Length (Miles -> KM)
      if (filters.minLengthMiles && Number(filters.minLengthMiles) > 0) {
        searchParams.min_length_km = Number((filters.minLengthMiles * 1.60934).toFixed(3));
      }
      
      if (filters.maxLengthMiles && Number(filters.maxLengthMiles) > 0) {
        searchParams.max_length_km = Number((filters.maxLengthMiles * 1.60934).toFixed(3));
      }

      // 2. Difficulty & Region
      if (filters.difficulty) searchParams.difficulty = filters.difficulty;
      if (filters.region) searchParams.region = filters.region;
      if (filters.state) searchParams.state = filters.state;
      if (filters.month) searchParams.month = filters.month;

      // 3. Requirements
      if (filters.meetRequirementsOnly) {
        searchParams.meet_requirements_only = true;
      }

      // 4. Max Distance Radius (Miles -> KM)
      // UPDATED: Changed param name to 'max_dist' to match Python Controller
      if (filters.maxDistanceMiles) {
        searchParams.max_dist = Number((filters.maxDistanceMiles * 1.60934).toFixed(3));
      }

      // 5. User Location
      // UPDATED: Changed param names to 'user_lat' / 'user_lon' to match Python Controller
      if (userLocation) {
        searchParams.user_lat = userLocation.lat; 
        searchParams.user_lon = userLocation.lng;
      }

      searchHikesRef.current(searchParams);
    };

    const DEBOUNCE_MS = 300;
    timer = setTimeout(runSearch, DEBOUNCE_MS);

    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [filters, userLocation]);

  /* -----------------------------
      Re-trigger search on navigation
      This ensures fresh data when returning to map
  ------------------------------*/
  useEffect(() => {
    // Only run when we're on /map route
    if (location.pathname === "/map") {
      const searchParams = {};

      if (filters.minLengthMiles && Number(filters.minLengthMiles) > 0) {
        searchParams.min_length_km = Number((filters.minLengthMiles * 1.60934).toFixed(3));
      }
      
      if (filters.maxLengthMiles && Number(filters.maxLengthMiles) > 0) {
        searchParams.max_length_km = Number((filters.maxLengthMiles * 1.60934).toFixed(3));
      }

      if (filters.difficulty) searchParams.difficulty = filters.difficulty;
      if (filters.region) searchParams.region = filters.region;
      if (filters.state) searchParams.state = filters.state;
      if (filters.month) searchParams.month = filters.month;

      if (filters.meetRequirementsOnly) {
        searchParams.meet_requirements_only = true;
      }

      if (filters.maxDistanceMiles) {
        searchParams.farthest_hike_distance_m = Math.round(filters.maxDistanceMiles * 1609.34);
      }

      if (userLocation) {
        searchParams.user_latitude = userLocation.lat; 
        searchParams.user_longitude = userLocation.lng;
      }

      searchHikesRef.current(searchParams);
    }
  }, [location.pathname, filters, userLocation]);

  /* -----------------------------
       Update Map Markers
  -------------------------------*/
  useEffect(() => {
    if (!map.current) return;

    // Function to clean up and add markers
    const updateMarkers = () => {
      // Clean up existing markers
      markers.current.forEach((m) => m.remove());
      markers.current = [];

      // Clean up existing trail layers using our tracked set
      trailLayers.current.forEach((layerId) => {
        try {
          if (map.current.getLayer(layerId)) {
            map.current.removeLayer(layerId);
          }
          if (map.current.getSource(layerId)) {
            map.current.removeSource(layerId);
          }
        } catch (e) {
          console.warn(`Failed to remove layer ${layerId}:`, e);
        }
      });
      trailLayers.current.clear();

      // Add new markers and layers
      hikes.forEach((hike) => {
        if (!hike.geometry?.coordinates) return;
        let markerPosition;

        if (hike.geometry.type === "LineString") {
          markerPosition = hike.geometry.coordinates[0];
          const trailId = `trail-${hike.id}`;

          try {
            map.current.addSource(trailId, {
              type: "geojson",
              data: { type: "Feature", geometry: hike.geometry }
            });
            map.current.addLayer({
              id: trailId,
              type: "line",
              source: trailId,
              layout: { "line-join": "round", "line-cap": "round" },
              paint: {
                "line-color": "#22c55e",
                "line-width": 3,
                "line-opacity": 0.8
              }
            });
            trailLayers.current.add(trailId);
          } catch (e) {
            console.warn(`Failed to add trail layer ${trailId}:`, e);
          }
        } else if (hike.geometry.type === "Point") {
          markerPosition = hike.geometry.coordinates;
        } else {
          return;
        }

        const marker = new mapboxgl.Marker({ color: "#22c55e" })
          .setLngLat(markerPosition)
          .setPopup(new mapboxgl.Popup().setHTML(`<strong>${hike.name}</strong>`))
          .addTo(map.current);

        marker.getElement().addEventListener("click", () => {
          selectHike(hike);
          navigate(`/hike/${hike.id}`);
        });
        markers.current.push(marker);
      });

      // Fit bounds if we have hikes
      if (hikes.length > 0) {
        const bounds = new mapboxgl.LngLatBounds();
        hikes.forEach((h) => {
          if (h.geometry?.type === "LineString") {
            h.geometry.coordinates.forEach((c) => bounds.extend(c));
          } else if (h.geometry?.type === "Point") {
            bounds.extend(h.geometry.coordinates);
          }
        });
        map.current.fitBounds(bounds, { padding: 60 });
      }
    };

    // Check if map is loaded
    if (map.current.loaded()) {
      updateMarkers();
    } else {
      map.current.once('load', updateMarkers);
    }
  }, [hikes, navigate, selectHike]);

  /* -----------------------------
       Render
  ------------------------------*/
  return (
    <div className="flex h-screen">
      {/* LEFT: Map */}
      <div className="relative flex-1">
        <div ref={mapContainer} className="h-full w-full" />
        
        {/* --- ADDED: Profile Button --- */}
        <button
          onClick={() => navigate("/profile")}
          className="absolute top-4 right-14 z-10 bg-white p-2 rounded-md shadow-md hover:bg-gray-50 border border-gray-200 transition-colors"
          title="Go to Profile"
        >
          {/* Simple User SVG Icon */}
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            width="20" 
            height="20" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            className="text-gray-700"
          >
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
        </button>
        {/* ----------------------------- */}

        <MapLegend />
      </div>

      {/* RIGHT: Filters + Results */}
      <div className="w-80 border-l bg-gray-50 flex flex-col shadow-xl z-10">
        
        {/* Filters Area */}
        <div className="p-3 border-b bg-white">
          <FilterBar filters={filters} onChange={setFilters} />

          {/* Location Status */}
          <div className="flex justify-between items-center mt-2">
            {locationLoading && <p className="text-[10px] text-gray-500">Locating...</p>}
            {locationError && <p className="text-[10px] text-red-500">{locationError}</p>}
          </div>
        </div>
        
        {/* Results Area */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {loading && hikes.length === 0 && (
            <p className="text-center text-sm text-gray-500 mt-4">Loading hikes...</p>
          )}
          {loading && hikes.length > 0 && (
             <p className="text-[10px] text-right text-gray-400">Updating...</p>
          )}
          {!loading && hikes.length === 0 && (
            <p className="text-center text-sm text-gray-500 mt-4">No hikes found.</p>
          )}
          
          {hikes.map((hike) => (
            <div 
              key={hike.id}
              onClick={() => {
                selectHike(hike);
                navigate(`/hike/${hike.id}`);
              }}
              className="cursor-pointer hover:bg-white hover:shadow-md transition-all duration-200 rounded-lg border border-transparent hover:border-gray-200"
            >
              <HikeSummaryCard hike={hike} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}