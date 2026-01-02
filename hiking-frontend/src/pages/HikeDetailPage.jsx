import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { useHikes } from "../context/HikeContext";
import MissingGearList from "../components/MissingGearList";
import CostBreakdownPanel from "../components/CostBreakdownPanel";

export default function HikeDetailPage() {
  const { hikeId } = useParams();

  const {
    selectedHike,
    loadHikeById,
    loading,
    error
  } = useHikes();

  /* -----------------------------
     Local evaluation state
  ------------------------------*/
  const [evaluation, setEvaluation] = useState(null);

  /* -----------------------------
     Load hike if needed
  ------------------------------*/
  useEffect(() => {
    if (!selectedHike || selectedHike.id !== hikeId) {
      loadHikeById(hikeId);
    }
  }, [hikeId]);

  /* -----------------------------
     MVP Evaluation Logic
     (frontend placeholder)
  ------------------------------*/
  useEffect(() => {
    if (!selectedHike) return;

    /**
     * This simulates what your backend
     * /hikes/{id}/evaluate endpoint will do.
     *
     * DO NOT OVER-OPTIMIZE THIS —
     * it proves the decision loop.
     */

    const missingGear = [];
    let gearCost = 0;

    // Simple rule-based logic
    if (selectedHike.length_miles > 8) {
      missingGear.push({
        id: "hydration-pack",
        name: "Hydration Pack",
        estimated_cost: 40
      });
      gearCost += 40;
    }

    if (selectedHike.elevation_gain_ft > 2000) {
      missingGear.push({
        id: "trekking-poles",
        name: "Trekking Poles",
        estimated_cost: 60
      });
      gearCost += 60;
    }

    if (selectedHike.difficulty === "hard") {
      missingGear.push({
        id: "first-aid-kit",
        name: "First Aid Kit",
        estimated_cost: 25
      });
      gearCost += 25;
    }

    // Very rough travel estimate
    const travelCost =
      selectedHike.distance_from_user_miles
        ? Math.round(selectedHike.distance_from_user_miles * 0.6)
        : 0;

    setEvaluation({
      missingGear,
      costs: {
        travel: travelCost,
        gear: gearCost,
        fees: selectedHike.park_fee ?? 0
      }
    });
  }, [selectedHike]);

  /* -----------------------------
     Render states
  ------------------------------*/
  if (loading || !selectedHike) {
    return (
      <div className="p-8 text-center text-gray-500">
        Loading hike details…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-red-500">
        {error}
      </div>
    );
  }

  /* -----------------------------
     Main Render
  ------------------------------*/
  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">
          {selectedHike.name}
        </h1>
        <p className="text-gray-600">
          {selectedHike.location_name}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Length" value={`${selectedHike.length_miles} mi`} />
        <Stat label="Elevation Gain" value={`${selectedHike.elevation_gain_ft} ft`} />
        <Stat label="Difficulty" value={selectedHike.difficulty} />
        <Stat label="Season" value={selectedHike.season ?? "Unknown"} />
      </div>

      {/* Description */}
      {selectedHike.description && (
        <div>
          <h3 className="text-lg font-semibold mb-2">About This Hike</h3>
          <p className="text-gray-700">
            {selectedHike.description}
          </p>
        </div>
      )}

      {/* Evaluation */}
      {evaluation && (
        <div className="grid md:grid-cols-2 gap-6">

          <MissingGearList items={evaluation.missingGear} />

          <CostBreakdownPanel costs={evaluation.costs} />

        </div>
      )}

    </div>
  );
}

/* -----------------------------
   Small helper component
------------------------------*/
function Stat({ label, value }) {
  return (
    <div className="border rounded-lg p-3 bg-gray-50 text-center">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
