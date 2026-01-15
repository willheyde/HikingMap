import { useMemo, useState, useEffect } from "react";
import { useUser } from "../context/UserContext";
import { useNavigate } from "react-router-dom";
import ScrollBar from "../components/ScrollBar";

const Profile = () => {
  // Pull updateLocation and loadingLocation from context
  const { user, items, updateLocation, loadingLocation } = useUser();
  const navigate = useNavigate();
  const [trips, setTrips] = useState([]);
  const [loadingTrips, setLoadingTrips] = useState(false);

  // --- DEBUGGING WRAPPER ---
  const handleUpdateLocation = () => {
    console.log("--- DEBUG: Manual Location Update Triggered ---");
    console.log("Current User Object:", user);
    console.log("User ID (for URL):", user?.id);
    console.log("Current Home Location:", user?.home_location);
    
    // Check if the ID in the log matches the UUID in your error: 4294501a...
    if (!user || !user.id) {
        console.error("CRITICAL: User ID is missing!");
    }

    updateLocation();
  };
  // -------------------------

  // Fetch user's saved trips
  useEffect(() => {
    const fetchTrips = async () => {
      if (!user) return;
      setLoadingTrips(true);
      try {
        setTrips([]); 
      } catch (err) {
        console.error("Failed to load trips:", err);
      } finally {
        setLoadingTrips(false);
      }
    };
    fetchTrips();
  }, [user]);

  // Group items by category
  const itemsByCategory = useMemo(() => {
    if (!items || items.length === 0) return {};
    
    return items.reduce((acc, item) => {
      const category = item.item_type || "Uncategorized";
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(item);
      return acc;
    }, {});
  }, [items]);

  // Calculate stats
  const stats = useMemo(() => {
    const totalWeight = items.reduce((sum, item) => sum + (Number(item.weight) || 0), 0);
    const totalCost = items.reduce((sum, item) => sum + (Number(item.cost) || 0), 0);
    const itemCount = items.length;
    
    return { totalWeight, totalCost, itemCount };
  }, [items]);

  if (!user) {
    return (
      <ScrollBar className="bg-slate-900 flex items-center justify-center">
        <p className="text-slate-400">Please log in to view your profile.</p>
      </ScrollBar>
    );
  }

  return (
    <ScrollBar className="bg-slate-900 text-white">
      <div className="max-w-6xl mx-auto p-6 md:p-8 pb-20">
        
        {/* Header Section */}
        <div className="bg-slate-800 rounded-2xl p-8 mb-8 border border-slate-700">
          <div className="flex flex-col md:flex-row items-start justify-between gap-4">
            <div className="flex items-center gap-6">
              <img 
                src={user.avatar_url || "https://via.placeholder.com/120"} 
                className="w-24 h-24 rounded-full border-4 border-blue-500 shadow-lg object-cover" 
                alt="User Avatar" 
              />
              <div>
                <h1 className="text-3xl font-bold text-white mb-2">{user.name}</h1>
                
                {/* Location Display & Update Button */}
                <div className="flex items-center gap-3">
                  <p className="text-slate-400 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                    {user.home_location?.name || "Location not set"}
                  </p>
                  
                  {/* Manual Update Button - UPDATED TO USE DEBUG WRAPPER */}
                  <button 
                    onClick={handleUpdateLocation}
                    disabled={loadingLocation}
                    className="text-xs text-blue-400 hover:text-blue-300 underline disabled:text-slate-600 disabled:no-underline"
                  >
                    {loadingLocation ? "Locating..." : "Update Location"}
                  </button>
                </div>

                <p className="text-slate-500 text-sm mt-1">{user.email}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/map")}
                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 shadow-sm whitespace-nowrap"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10l1.5-1.5L9 12l4-4 7.5 7.5L21 21"/>
                </svg>
                Back to Map
              </button>

              <button 
                onClick={() => navigate("/onboarding")}
                className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-semibold transition-all flex items-center gap-2 shadow-lg whitespace-nowrap"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                Update Gear
              </button>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400 text-sm font-medium">Total Items</span>
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
              </svg>
            </div>
            <p className="text-3xl font-bold text-white">{stats.itemCount}</p>
          </div>

          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400 text-sm font-medium">Total Weight</span>
              <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/>
              </svg>
            </div>
            <p className="text-3xl font-bold text-white">{stats.totalWeight.toFixed(2)} <span className="text-lg text-slate-400">kg</span></p>
          </div>

          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400 text-sm font-medium">Total Cost</span>
              <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <p className="text-3xl font-bold text-white">${stats.totalCost.toFixed(2)}</p>
          </div>

          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400 text-sm font-medium">Saved Trips</span>
              <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
              </svg>
            </div>
            <p className="text-3xl font-bold text-white">{trips.length}</p>
          </div>
        </div>

        {/* Saved Trips Section */}
        <div className="bg-slate-800 rounded-2xl p-8 border border-slate-700 mb-8">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
            <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
            </svg>
            Saved Trips
          </h2>

          {loadingTrips ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400 mx-auto"></div>
              <p className="text-slate-400 mt-4">Loading trips...</p>
            </div>
          ) : trips.length === 0 ? (
            <div className="text-center py-12">
              <svg className="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
              </svg>
              <p className="text-slate-400 text-lg mb-4">No saved trips yet</p>
              <p className="text-slate-500 text-sm mb-4">Plan your first adventure and save it for later!</p>
              <button 
                onClick={() => navigate("/map")}
                className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-semibold transition-all inline-flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"/>
                </svg>
                Plan a Trip
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {trips.map((trip) => (
                <div 
                  key={trip.id}
                  className="bg-slate-900/50 rounded-lg p-5 border border-slate-700 hover:border-purple-500 transition-all cursor-pointer"
                  onClick={() => navigate(`/trip/${trip.id}`)}
                >
                  {/* Trip Card Content */}
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-white mb-1">{trip.hike_name || "Unnamed Trip"}</h3>
                      <p className="text-slate-400 text-sm">
                        {new Date(trip.start_date).toLocaleDateString()} - {new Date(trip.end_date).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="px-2 py-1 bg-purple-600/20 text-purple-400 text-xs rounded-full border border-purple-500/30">
                      {trip.travel_mode}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Gear Inventory Section */}
        <div className="bg-slate-800 rounded-2xl p-8 border border-slate-700">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
            <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
            </svg>
            Your Gear
          </h2>

          {Object.keys(itemsByCategory).length === 0 ? (
            <div className="text-center py-12">
               <p className="text-slate-400 mb-4">Your gear locker is empty</p>
               <p className="text-slate-500 text-sm mb-6">Select the gear you use so we can calculate pack weight and costs.</p>
               <div className="flex justify-center">
                 <button
                   onClick={() => navigate("/onboarding")}
                   className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-lg font-semibold transition-all inline-flex items-center gap-2"
                 >
                   <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                     <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"/>
                   </svg>
                   Select Gear
                 </button>
               </div>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(itemsByCategory).map(([category, categoryItems]) => (
                <div key={category} className="border-l-4 border-blue-500 pl-4">
                  <h3 className="text-lg font-semibold text-blue-400 mb-3 capitalize">
                    {category.replace('_', ' ')}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {categoryItems.map((item, index) => (
                      <div 
                        key={`${item.id}-${index}`}
                        className="bg-slate-900/50 rounded-lg p-4 border border-slate-700"
                      >
                          <h4 className="font-medium text-white text-sm">{item.name}</h4>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </ScrollBar>
  );
};

export default Profile;