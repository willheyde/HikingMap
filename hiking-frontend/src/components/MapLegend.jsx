export default function MapLegend() {
  return (
    <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg p-4 text-sm w-48">
      <h4 className="font-semibold mb-3 text-gray-800">
        Map Legend
      </h4>

      <ul className="space-y-2">
        <LegendItem
          icon="📍"
          label="Hike Location"
        />

        <LegendItem
          icon="⭐"
          label="Recommended Hike"
        />

        <LegendItem
          icon="⚠️"
          label="Missing Required Gear"
        />
      </ul>
    </div>
  );
}

/* -----------------------------
   Internal helper
------------------------------*/
function LegendItem({ icon, label }) {
  return (
    <li className="flex items-center gap-2">
      <span className="text-lg">{icon}</span>
      <span className="text-gray-700">{label}</span>
    </li>
  );
}
