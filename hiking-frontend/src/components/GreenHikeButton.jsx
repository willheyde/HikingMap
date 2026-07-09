import { useNavigate } from "react-router-dom";

export default function GreenTreeButton({ hikeId, label = "View Hike", disabled = false }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (!disabled && hikeId) {
      navigate(`/hikes/${hikeId}`);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={`px-4 py-2 rounded-lg font-semibold transition
        ${disabled
          ? "bg-[#a2855a] text-ink-muted cursor-not-allowed"
          : "bg-sage hover:bg-[#5a6845] text-paper shadow-md"
        }`}
    >
      🌲 {label}
    </button>
  );
}
