export default function FilterBar({ filters, onChange }) {
  /**
   * filters shape:
   * {
   *   maxDistanceMiles: number | null,
   *   difficulty: "easy" | "moderate" | "hard" | null,
   *   minLengthMiles: number | null,
   *   meetRequirementsOnly: boolean
   * }
   */

  const update = (key, value) => {
    onChange({
      ...filters,
      [key]: value
    });
  };

  return (
    <div className="bg-white shadow rounded-lg p-4 flex flex-wrap gap-4 items-end">
      
      {/* Distance from User */}
      <div className="flex flex-col">
        <label className="text-sm font-medium">
          Max Distance (mi)
        </label>
        <input
          type="number"
          min="0"
          value={filters.maxDistanceMiles ?? ""}
          onChange={(e) =>
            update(
              "maxDistanceMiles",
              e.target.value === "" ? null : Number(e.target.value)
            )
          }
          className="border rounded px-2 py-1 w-28"
        />
      </div>

      {/* Difficulty */}
      <div className="flex flex-col">
        <label className="text-sm font-medium">
          Difficulty
        </label>
        <select
          value={filters.difficulty ?? ""}
          onChange={(e) =>
            update(
              "difficulty",
              e.target.value === "" ? null : e.target.value
            )
          }
          className="border rounded px-2 py-1"
        >
          <option value="">Any</option>
          <option value="easy">Easy</option>
          <option value="moderate">Moderate</option>
          <option value="hard">Hard</option>
        </select>
      </div>

      {/* Minimum Length */}
      <div className="flex flex-col">
        <label className="text-sm font-medium">
          Min Length (mi)
        </label>
        <input
          type="number"
          min="0"
          value={filters.minLengthMiles ?? ""}
          onChange={(e) =>
            update(
              "minLengthMiles",
              e.target.value === "" ? null : Number(e.target.value)
            )
          }
          className="border rounded px-2 py-1 w-28"
        />
      </div>

      {/* Requirements / Gear Match */}
      <div className="flex items-center gap-2 mt-6">
        <input
          type="checkbox"
          checked={filters.meetRequirementsOnly}
          onChange={(e) =>
            update("meetRequirementsOnly", e.target.checked)
          }
        />
        <label className="text-sm font-medium">
          Meet My Gear
        </label>
      </div>

    </div>
  );
}
