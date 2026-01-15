import React from "react";

export default function FilterBar({ filters, onChange }) {
  const update = (key, value) => {
    onChange({
      ...filters,
      [key]: value
    });
  };

  const inputClass = "w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-green-500";
  const labelClass = "block text-xs font-semibold text-gray-600 mb-0.5";

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center mb-2">
        <h2 className="text-sm font-bold text-gray-800">Filters</h2>
        <button
          onClick={() => onChange({
            maxDistanceMiles: null, difficulty: null, minLengthMiles: null,
            maxLengthMiles: null, meetRequirementsOnly: false, state: null,
            region: null, month: null
          })}
          className="text-xs text-green-600 hover:text-green-800 underline"
        >
          Reset
        </button>
      </div>

      {/* Row 1: State & Difficulty */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={labelClass}>State</label>
          <select
            value={filters.state ?? ""}
            onChange={(e) => update("state", e.target.value || null)}
            className={inputClass}
          >
            {/* FIXED: Changed values to abbreviations to match standard API expectations */}
            <option value="">All</option>
            <option value="CA">CA</option>
            <option value="CO">CO</option>
            <option value="WA">WA</option>
            <option value="OR">OR</option>
            <option value="MT">MT</option>
            <option value="WY">WY</option>
            <option value="UT">UT</option>
            <option value="AZ">AZ</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>Difficulty</label>
          <select
            value={filters.difficulty ?? ""}
            onChange={(e) => update("difficulty", e.target.value || null)}
            className={inputClass}
          >
            <option value="">Any</option>
            <option value="EASY">Easy</option>
            <option value="MODERATE">Moderate</option>
            <option value="HARD">Hard</option>
          </select>
        </div>
      </div>

      {/* Row 2: Trail Length */}
      <div>
        <label className={labelClass}>Trail Length (mi)</label>
        <div className="flex gap-2">
          <input
            type="number"
            min="0"
            step="0.1"
            placeholder="Min"
            value={filters.minLengthMiles ?? ""}
            onChange={(e) => update("minLengthMiles", e.target.value === "" ? null : Number(e.target.value))}
            className={inputClass}
          />
          <input
            type="number"
            min="0"
            step="0.1"
            placeholder="Max"
            value={filters.maxLengthMiles ?? ""}
            onChange={(e) => update("maxLengthMiles", e.target.value === "" ? null : Number(e.target.value))}
            className={inputClass}
          />
        </div>
      </div>

      {/* Row 3: Max Dist & Month */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={labelClass}>Max Radius (mi)</label>
          <input
            type="number"
            min="0"
            step="1"
            placeholder="From center"
            value={filters.maxDistanceMiles ?? ""}
            onChange={(e) => update("maxDistanceMiles", e.target.value === "" ? null : Number(e.target.value))}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Best Month</label>
          <select
            value={filters.month ?? ""}
            onChange={(e) => update("month", e.target.value === "" ? null : Number(e.target.value))}
            className={inputClass}
          >
            <option value="">Any</option>
            <option value="1">Jan</option>
            <option value="2">Feb</option>
            <option value="3">Mar</option>
            <option value="4">Apr</option>
            <option value="5">May</option>
            <option value="6">Jun</option>
            <option value="7">Jul</option>
            <option value="8">Aug</option>
            <option value="9">Sep</option>
            <option value="10">Oct</option>
            <option value="11">Nov</option>
            <option value="12">Dec</option>
          </select>
        </div>
      </div>

      {/* Row 4: Gear Requirement */}
      <div className="flex items-center pt-1">
        <input
          id="meet-requirements"
          type="checkbox"
          checked={!!filters.meetRequirementsOnly}
          onChange={(e) => update("meetRequirementsOnly", e.target.checked)}
          className="h-3.5 w-3.5 text-green-600 rounded border-gray-300 focus:ring-green-500"
        />
        <label htmlFor="meet-requirements" className="ml-2 text-xs text-gray-700 select-none">
          My gear only
        </label>
      </div>
    </div>
  );
}