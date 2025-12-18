import GreenTreeButton from "./GreenTreeButton";

export default function HikeSummaryCard({ hike }) {
  return (
    <div className="border rounded-lg p-4 shadow-sm bg-white flex flex-col gap-2">
      <h3 className="text-lg font-semibold">{hike.name}</h3>

      <div className="text-sm text-gray-600">
        <div>📏 {hike.length_miles} miles</div>
        <div>⬆️ {hike.elevation_gain_ft} ft gain</div>
        <div>⚡ {hike.difficulty}</div>
      </div>

      <div className="mt-2">
        <GreenTreeButton hikeId={hike.id} />
      </div>
    </div>
  );
}
