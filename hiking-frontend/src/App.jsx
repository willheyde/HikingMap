import { Routes, Route, Navigate } from "react-router-dom";

import MapPage from "./pages/MapPage";
import HikeDetailPage from "./pages/HikeDetailPage";
import AuthModal from "./components/AuthModal"; // Import the modal
import Profile from "./pages/Profile";
import GearManager from "./pages/GearManager";
import GearOnboarding from "./pages/GearOnboarding"; // Assuming this is the correct path
import TripPlanner from "./pages/TripPlanner";

function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      {/* The AuthModal lives here permanently. 
         It handles its own visibility based on UserContext state. 
      */}
      <AuthModal />

      {/* Your existing Navbar could go here */}
      
      <div className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<MapPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/hike/:hikeId" element={<HikeDetailPage />} />
          <Route path="/profile" element={<Profile/>} />
          <Route path="/gear" element={<GearManager />} />
          <Route path="/onboarding" element={<GearOnboarding />} />
          <Route path="/trip-planner" element={<TripPlanner />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;