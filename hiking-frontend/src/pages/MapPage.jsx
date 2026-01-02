import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import FilterBar from "../components/FilterBar";
import HikeSummaryCard from "../components/HikeSummaryCard";
import MapLegend from "../components/MapLegend";
import { useUserLocation } from "../components/UserLocation";
import { useHikes } from "../context/HikeContext";

// Mapbox token
mapboxgl.accessToken = "pk.eyJ1Ijoid3doZXlkZSIsImEiOiJjbWpjNHQ1enYwb3I1M2ZvbzMycTA2NGliIn0.vUtDLKMdB88W62j3JDcBUA";

export default function MapPage() {
  const navigate = useNavigate();
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markers = useRef([]);

  const {
    hikes,
    loading,
    searchHikes,
    selectHike
  } = useHikes();

  const [filters, setFilters] = useState({
    minLengthKm: null,
    minElevationGainM: null,
    difficulty: null,
    region: null,
    month: null
  });


  const {
    location,
    loading: locationLoading,
    error: locationError
  } = useUserLocation();

  /* -----------------------------
     Initialize Map
  ------------------------------*/
  useEffect(() => {
    if (map.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/outdoors-v12",
      center: [-98.5795, 39.8283], // Continental US
      zoom: 4
    });

    map.current.addControl(
      new mapboxgl.NavigationControl(),
      "top-right"
    );
  }, []);

  /* -----------------------------
     Search Hikes (via context)
  ------------------------------*/
  useEffect(() => {
  const searchParams = {};

  if (filters.minLengthKm !== null) {
    searchParams.min_length_km = filters.minLengthKm;
  }

  if (filters.minElevationGainM !== null) {
    searchParams.min_elevation_gain_m = filters.minElevationGainM;
  }

  if (filters.difficulty) {
    searchParams.difficulty = filters.difficulty;
  }

  if (filters.region) {
    searchParams.region = filters.region;
  }

  if (filters.month) {
    searchParams.month = filters.month;
  }

  if (location) {
    searchParams.farthest_hike_latitude_m = location.lat;
    searchParams.farthest_hike_longitude_m = location.lng;
  }

  searchHikes(searchParams);
}, [filters, location]);


  /* -----------------------------
   Update Map Markers
-------------------------------*/
useEffect(() => {
  if (!map.current) return;

  // Remove old markers
  markers.current.forEach((m) => m.remove());
  markers.current = [];

  hikes.forEach((hike) => {
    if (!hike.geometry?.coordinates) return;

    // Handle different geometry types
    let markerPosition;
    
    if (hike.geometry.type === 'LineString') {
      // For trails, use the first coordinate (start of trail)
      markerPosition = hike.geometry.coordinates[0];
      
      // Add trail line to map
      const trailId = `trail-${hike.id}`;
      
      if (!map.current.getSource(trailId)) {
        map.current.addSource(trailId, {
          type: 'geojson',
          data: {
            type: 'Feature',
            geometry: hike.geometry
          }
        });

        map.current.addLayer({
          id: trailId,
          type: 'line',
          source: trailId,
          layout: {
            'line-join': 'round',
            'line-cap': 'round'
          },
          paint: {
            'line-color': '#22c55e',
            'line-width': 3,
            'line-opacity': 0.8
          }
        });
      }
    } else if (hike.geometry.type === 'Point') {
      // For points, use the coordinate directly
      markerPosition = hike.geometry.coordinates;
    } else {
      console.warn(`Unsupported geometry type: ${hike.geometry.type}`);
      return;
    }

    const marker = new mapboxgl.Marker({
      color: "#22c55e"
    })
      .setLngLat(markerPosition)
      .setPopup(
        new mapboxgl.Popup().setHTML(
          `<strong>${hike.name}</strong>`
        )
      )
      .addTo(map.current);

    marker.getElement().addEventListener("click", () => {
      selectHike(hike);
      navigate(`/hikes/${hike.id}`);
    });

    markers.current.push(marker);
  });

  // Fit map to results
  if (hikes.length > 0) {
    const bounds = new mapboxgl.LngLatBounds();
    
    hikes.forEach((h) => {
      if (!h.geometry?.coordinates) return;
      
      if (h.geometry.type === 'LineString') {
        // For LineString, extend bounds with all coordinates
        h.geometry.coordinates.forEach(coord => {
          bounds.extend(coord);
        });
      } else if (h.geometry.type === 'Point') {
        bounds.extend(h.geometry.coordinates);
      }
    });
    
    map.current.fitBounds(bounds, { padding: 60 });
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
        <MapLegend />
      </div>

      {/* RIGHT: Filters + Results */}
      <div className="w-96 border-l bg-gray-50 flex flex-col">

        {/* Filters */}
        <div className="p-4 border-b">
          <FilterBar
            filters={filters}
            onChange={setFilters}
          />

          {locationLoading && (
            <p className="text-xs text-gray-500 mt-2">
              Getting your location…
            </p>
          )}

          {locationError && (
            <p className="text-xs text-red-500 mt-2">
              {locationError}
            </p>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading && (
            <p className="text-center text-gray-500">
              Loading hikes…
            </p>
          )}

          {!loading && hikes.length === 0 && (
            <p className="text-center text-gray-500">
              No hikes match your filters
            </p>
          )}

          {hikes.map((hike) => (
            <HikeSummaryCard
              key={hike.id}
              hike={hike}
            />
          ))}
        </div>

      </div>
    </div>
  );
}
