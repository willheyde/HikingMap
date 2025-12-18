export default function HikeMarker({ hike, onSelect }) {
  if (!hike?.location) return null;

  return (
    <div
      onClick={() => onSelect(hike.id)}
      className="cursor-pointer transform hover:scale-110 transition"
      title={hike.name}
    >
      📍
    </div>
  );
}
