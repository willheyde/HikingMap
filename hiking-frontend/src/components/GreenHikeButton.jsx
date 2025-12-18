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
          ? "bg-gray-400 cursor-not-allowed" 
          : "bg-green-600 hover:bg-green-700 text-white shadow-md"
        }`}
    >
      🌲 {label}
    </button>
  );
}
