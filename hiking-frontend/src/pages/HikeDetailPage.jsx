import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { useHikes } from "../context/HikeContext";
import { useUser } from "../context/UserContext"; 
import * as itemsService from "../api/itemsService";

import ScrollBar from "../components/ScrollBar";
import CostBreakdownPanel from "../components/CostBreakdownPanel"; 

/* -----------------------------
   Helper Functions
------------------------------*/
const kmToMiles = (km) => (km * 0.621371).toFixed(1);
const metersToFeet = (m) => Math.round(m * 3.28084);

function StatCard({ label, value, icon }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col items-center justify-center text-center shadow-sm hover:border-slate-600 transition-colors">
      <div className="text-slate-400 mb-2">{icon}</div>
      <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-1">{label}</div>
      <div className="text-lg font-bold text-white">{value}</div>
    </div>
  );
}

export default function HikeDetailPage() {
  const { hikeId } = useParams();
  const navigate = useNavigate();

  // Contexts
  const { selectedHike, loadHikeById, loading, error } = useHikes();
  const { items } = useUser(); 

  // State
  const [gearDetails, setGearDetails] = useState([]); // Stores the fully resolved gear items
  const [loadingGear, setLoadingGear] = useState(false);
  const [calculatedCosts, setCalculatedCosts] = useState({ travel: 0, gear: 0, fees: 0 });

  /* -----------------------------
      1. Load Hike Data
   ------------------------------*/
  useEffect(() => {
    // Only load if we don't have it or if the ID doesn't match
    if (!selectedHike || String(selectedHike.id) !== String(hikeId)) {
      loadHikeById(hikeId);
    }
  }, [hikeId, selectedHike, loadHikeById]);

  /* -----------------------------
      2. Fetch Gear Details (Dynamic via ID)
   ------------------------------*/
  useEffect(() => {
    const fetchDynamicGear = async () => {
      // Wait for hike to load and verify it has tags
      if (!selectedHike || !selectedHike.required_gear_tags) return;
      
      setLoadingGear(true);
      
      try {
        // Iterate over the IDs provided by the DB
        const promises = selectedHike.required_gear_tags.map(async (itemId) => {
          try {
            // 1. Fetch full details using ID
            const itemDetails = await itemsService.getItemById(itemId);
            
            // 2. Determine ownership
            // Check if user has an item with matching category, type, or specific name
            // This allows generic matching (e.g., if Hike needs "Generic Boots", but you own "Pro Boots", it counts)
            const isOwned = items?.some(
              (userItem) => 
                userItem.id === itemDetails.id || // Exact Match
                (userItem.category && userItem.category === itemDetails.category) || // Category Match
                (userItem.item_type && userItem.item_type === itemDetails.item_type) // Type Match
            );

            return {
              id: itemDetails.id, 
              name: itemDetails.name,
              category: itemDetails.category,
              reason: "Required for this route", 
              fullDetails: itemDetails,
              owned: isOwned,
              est_cost: itemDetails.cost || 40 // Fallback cost
            };
          } catch (err) {
            console.warn(`Could not find item detail for ID: ${itemId}`);
            // Return a placeholder if lookup fails so the UI doesn't crash
            return {
              id: itemId,
              name: "Unknown Item", // Since we only have UUID, we can't guess the name on fail
              owned: false,
              reason: "Required",
              est_cost: 0,
              fullDetails: null
            };
          }
        });

        const resolvedGear = await Promise.all(promises);
        setGearDetails(resolvedGear);

      } catch (err) {
        console.error("Error processing gear tags:", err);
      } finally {
        setLoadingGear(false);
      }
    };

    fetchDynamicGear();
  }, [selectedHike, items]);

  /* -----------------------------
      3. Calculate Costs
   ------------------------------*/
  useEffect(() => {
    if (!selectedHike) return;

    // Travel Cost
    const travelCost = selectedHike.distance_from_user_miles
      ? Math.round(selectedHike.distance_from_user_miles * 0.6)
      : 0;

    // Gear Cost (Sum of unowned items)
    const missingGearCost = gearDetails
      .filter(g => !g.owned)
      .reduce((acc, curr) => acc + (curr.est_cost || 0), 0);

    setCalculatedCosts({
      travel: travelCost,
      gear: missingGearCost,
      fees: selectedHike.park_fee ?? 0
    });

  }, [selectedHike, gearDetails]);


  /* -----------------------------
      Render Helpers
   ------------------------------*/
  const formatDifficulty = (diff) => {
    if (!diff) return "Unknown";
    return diff.charAt(0) + diff.slice(1).toLowerCase();
  };

  const formatSeason = () => {
    if (!selectedHike?.season_start_month || !selectedHike?.season_end_month) return "Year-round";
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[selectedHike.season_start_month - 1]} - ${months[selectedHike.season_end_month - 1]}`;
  };

  /* -----------------------------
      Loading / Error States
   ------------------------------*/
  if (loading || (!selectedHike && !error)) {
    return (
      <ScrollBar className="bg-slate-900 flex items-center justify-center">
         <div className="text-slate-500 animate-pulse">Loading hike details...</div>
      </ScrollBar>
    );
  }

  if (error) {
    return (
      <ScrollBar className="bg-slate-900">
        <div className="max-w-5xl mx-auto p-6">
          <button onClick={() => navigate("/map")} className="text-slate-400 hover:text-white mb-4 transition-colors">
            &larr; Back to Map
          </button>
          <div className="p-8 text-center text-red-400 border border-red-900/50 rounded-lg bg-red-900/20">
            {error}
          </div>
        </div>
      </ScrollBar>
    );
  }

  if (!selectedHike) return null;

  /* -----------------------------
      MAIN RENDER
   ------------------------------*/
  return (
    <ScrollBar className="bg-slate-900 text-white">
      <div className="max-w-6xl mx-auto p-6 md:p-8 pb-24">

        {/* Navigation */}
        <button 
          onClick={() => navigate("/map")} 
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6 group"
        >
          <svg className="w-5 h-5 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
          </svg>
          Back to Map
        </button>

        {/* Hike Image - Full Width */}
        {selectedHike.image_url && (
          <div className="w-full h-64 md:h-96 rounded-2xl overflow-hidden mb-8 shadow-2xl">
            <img 
              src={selectedHike.image_url} 
              alt={selectedHike.name}
              className="w-full h-full object-cover"
            />
          </div>
        )}

        {/* Hero Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
          
          {/* Left: Info */}
          <div className="lg:col-span-2 space-y-6">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">{selectedHike.name}</h1>
              <div className="flex items-center gap-2 text-slate-400">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
                <span className="text-lg">{selectedHike.region}</span>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard 
                label="Length" 
                value={`${kmToMiles(selectedHike.length_km)} mi`} 
                icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>}
              />
              <StatCard 
                label="Elevation" 
                value={`${metersToFeet(selectedHike.elevation_gain_m)} ft`} 
                icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>}
              />
              <StatCard 
                label="Difficulty" 
                value={formatDifficulty(selectedHike.difficulty)} 
                icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>}
              />
              <StatCard 
                label="Season" 
                value={formatSeason()} 
                icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>}
              />
            </div>

            {selectedHike.permits_required && (
              <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4 flex gap-4 items-start">
                <span className="text-2xl">⚠️</span>
                <div>
                  <h3 className="text-yellow-500 font-bold">Permits Required</h3>
                  <p className="text-yellow-600/80 text-sm mt-1">Check local regulations and obtain necessary passes before heading out.</p>
                </div>
              </div>
            )}
          </div>

          {/* Right: Cost / Quick Summary */}
          <div className="bg-slate-800 rounded-2xl p-6 border border-slate-700 h-fit">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                Est. Trip Cost
              </h2>
              <CostBreakdownPanel costs={calculatedCosts} theme="dark" />
          </div>
        </div>

        <div className="border-t border-slate-700 my-10"></div>

        {/* Gear Showcase Section */}
        <div className="space-y-6">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white mb-2">Required Gear</h2>
              <p className="text-slate-400">Items tagged specifically for this hike.</p>
            </div>
            
            <div className={`px-4 py-2 rounded-full border text-sm font-semibold flex items-center gap-2 ${
                gearDetails.length > 0 && gearDetails.every(g => g.owned) 
                ? "bg-green-900/30 border-green-500/50 text-green-400" 
                : "bg-yellow-900/30 border-yellow-500/50 text-yellow-500"
            }`}>
                {gearDetails.length > 0 && gearDetails.every(g => g.owned) ? (
                    <>
                        <span className="w-2 h-2 rounded-full bg-green-500"></span>
                        Fully Equipped
                    </>
                ) : (
                    <>
                        <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                        Missing Items
                    </>
                )}
            </div>
          </div>

          {loadingGear ? (
            <div className="text-center text-slate-500 py-8">
              <div className="animate-pulse">Loading gear details from database...</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {gearDetails.map((gear, index) => (
                <div 
                  key={`${gear.id}-${index}`}
                  className={`relative rounded-xl border transition-all duration-300 overflow-hidden ${
                    gear.owned 
                      ? "bg-green-900/10 border-green-500/50 shadow-[0_0_15px_rgba(34,197,94,0.1)]" 
                      : "bg-slate-800 border-slate-700 opacity-80"
                  }`}
                >
                  {/* Item Image */}
                  {gear.fullDetails?.image_url ? (
                    <div className="w-full h-32 bg-slate-700 overflow-hidden">
                      <img 
                        src={gear.fullDetails.image_url} 
                        alt={gear.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ) : (
                    <div className="w-full h-32 bg-slate-700 flex items-center justify-center">
                      <svg className="w-12 h-12 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                      </svg>
                    </div>
                  )}

                  <div className="p-5">
                    <div className="flex justify-between items-start mb-2">
                        <span className={`text-xs font-bold uppercase tracking-wider ${
                            gear.owned ? "text-green-500" : "text-slate-500"
                        }`}>
                            {gear.owned ? "Owned" : "Needed"}
                        </span>
                        {gear.owned && (
                            <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                        )}
                    </div>

                    <h3 className={`font-bold text-lg mb-1 ${
                        gear.owned ? "text-green-100" : "text-slate-300"
                    }`}>
                        {gear.name}
                    </h3>
                    
                    <p className={`text-sm mb-2 ${
                        gear.owned ? "text-green-400/70" : "text-slate-500"
                    }`}>
                        {gear.reason}
                    </p>

                    {/* Show additional details if available */}
                    {gear.fullDetails && (
                      <div className={`text-xs space-y-1 ${
                        gear.owned ? "text-green-400/60" : "text-slate-500"
                      }`}>
                        {gear.fullDetails.cost && (
                          <div className="flex items-center gap-1">
                            <span>Cost: ${gear.fullDetails.cost}</span>
                          </div>
                        )}
                        {gear.fullDetails.weight && (
                          <div className="flex items-center gap-1">
                            <span>Weight: {gear.fullDetails.weight}oz</span>
                          </div>
                        )}
                      </div>
                    )}

                    {!gear.owned && (
                        <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center gap-2 text-xs text-slate-400">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
                            Available in Shop
                        </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </ScrollBar>
  );
}