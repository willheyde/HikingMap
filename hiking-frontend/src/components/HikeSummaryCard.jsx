import React from "react";

export default function HikeSummaryCard({ hike, onClick }) {
  // Convert km to miles
  const miles = (hike.length_km * 0.621371).toFixed(1);
  const elevationGainFt = Math.round(hike.elevation_gain_m * 3.28084);

  // Format difficulty
  const difficultyColor = {
    EASY: "text-green-600 bg-green-50",
    MODERATE: "text-yellow-600 bg-yellow-50",
    HARD: "text-red-600 bg-red-50"
  };

  const difficultyLabel = hike.difficulty 
    ? hike.difficulty.charAt(0) + hike.difficulty.slice(1).toLowerCase()
    : "Unknown";

  return (
    <div
      onClick={onClick}
      className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
    >
      {/* Hike Name */}
      <h3 className="font-semibold text-lg text-gray-900 mb-1">
        {hike.name}
      </h3>

      {/* Region/State */}
      <p className="text-sm text-gray-600 mb-3">
        📍 {hike.region}
      </p>

      {/* Stats Row */}
      <div className="flex flex-wrap gap-3 text-sm">
        {/* Distance */}
        <div className="flex items-center gap-1">
          <span className="text-gray-500">📏</span>
          <span className="font-medium text-gray-900">{miles} mi</span>
        </div>

        {/* Elevation Gain */}
        <div className="flex items-center gap-1">
          <span className="text-gray-500">⬆️</span>
          <span className="font-medium text-gray-900">{elevationGainFt} ft</span>
        </div>

        {/* Difficulty Badge */}
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyColor[hike.difficulty] || "text-gray-600 bg-gray-50"}`}>
          {difficultyLabel}
        </span>
      </div>

      {/* Best Season (if available) */}
      {hike.season_start_month && hike.season_end_month && (
        <p className="text-xs text-gray-500 mt-2">
          🗓️ Best: {getMonthName(hike.season_start_month)} - {getMonthName(hike.season_end_month)}
        </p>
      )}
    </div>
  );
}

function getMonthName(monthNum) {
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
  ];
  return months[monthNum - 1] || "";
}