import { Routes, Route, Navigate } from "react-router-dom";

import MapPage from "./pages/MapPage";
import HikeDetailPage from "./pages/HikeDetailPage";

export default function App() {
  return (
    <Routes>
      {/* Default route */}
      <Route path="/" element={<Navigate to="/map" replace />} />

      {/* Core pages */}
      <Route path="/map" element={<MapPage />} />
      <Route path="/hikes/:hikeId" element={<HikeDetailPage />} />

      {/* Fallback */}
      <Route
        path="*"
        element={
          <div className="p-8 text-center text-gray-500">
            Page not found
          </div>
        }
      />
    </Routes>
  );
}
