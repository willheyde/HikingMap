import { useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { useHikes } from "../context/HikeContext";
import { useUser } from "../context/UserContext"; 

import MissingGearList from "../components/MissingGearList";
import CostBreakdownPanel from "../components/CostBreakdownPanel";
import HikerAvatar from "../components/HikerAvatar"; 

/* -----------------------------
   VISUAL MAPPING
   Maps Database 'categories' to Avatar Visual keys.
   Adjust 'dbCategory' keys to match your actual SQL column values.
------------------------------*/
const GEAR_VISUAL_MAP = {
  // DB Category      // Avatar Visual Key
  'boots':            { slot: 'feet', value: 'boots' },
  'trail_runners':    { slot: 'feet', value: 'runners' },
  'jacket':           { slot: 'torso', value: 'heavy-coat' },
  'shell':            { slot: 'torso', value: 'rain-shell' },
  'base_layer':       { slot: 'torso', value: 'base-layer' },
  'backpack_large':   { slot: 'back', value: 'heavy-backpack' },
  'backpack_small':   { slot: 'back', value: 'light-backpack' },
  'poles':            { slot: 'handRight', value: 'poles' },
  'ice_axe':          { slot: 'handRight', value: 'ice-axe' },
  'headlamp':         { slot: 'head', value: 'headlamp' },
};

/* -----------------------------
   Helper Component
------------------------------*/
function Stat({ label, value }) {
  return (
    <div className="border rounded-lg p-3 bg-gray-50 text-center">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

const kmToMiles = (km) => (km * 0.621371).toFixed(1);
const metersToFeet = (m) => Math.round(m * 3.28084);

export default function HikeDetailPage() {
  const { hikeId } = useParams();
  const navigate = useNavigate();

  // Contexts
  const { selectedHike, loadHikeById, loading, error } = useHikes();
  const { items } = useUser(); // 'items' is now your SQL data array

  /* -----------------------------
     1. Load Hike Data
  ------------------------------*/
  useEffect(() => {
    if (!selectedHike || String(selectedHike.id) !== String(hikeId)) {
      loadHikeById(hikeId);
    }
  }, [hikeId, selectedHike, loadHikeById]);

  /* -----------------------------
     2. Calculate Avatar Visual State (Memoized)
     
  ------------------------------*/
  const avatarVisualState = useMemo(() => {
    // Default State
    let visualState = {
      back: 'none',
      bottoms: 'shorts', 
      feet: 'none',
      torso: 'none',
      head: 'none',
      handRight: 'none',
    };

    if (!items || items.length === 0) return visualState;

    // Loop through SQL items and apply visuals based on category/type
    items.forEach(item => {
      // Assuming your SQL Table has a 'category' or 'type' column
      const mapping = GEAR_VISUAL_MAP[item.category] || GEAR_VISUAL_MAP[item.type];
      
      if (mapping) {
        // Apply the visual. 
        // Logic: specific items might override others (e.g. boots override runners)
        // You can add priority logic here if needed.
        visualState[mapping.slot] = mapping.value;
      }
    });

    return visualState;
  }, [items]);

  /* -----------------------------
     3. Evaluation Logic (Memoized)
     No longer using useEffect/useState. Calculated on the fly.
  ------------------------------*/
  const evaluation = useMemo(() => {
    if (!selectedHike) return null;

    const missingGear = [];
    let gearCost = 0;

    const lengthMiles = selectedHike.length_km * 0.621371;
    const elevationFt = selectedHike.elevation_gain_m * 3.28084;
    
    // Helper: Check if user has an item of a specific category/type
    const userHasCategory = (cat) => items?.some(i => i.category === cat || i.type === cat);

    // Rule: Hydration (Example: checks for 'backpack_small' or 'water')
    if (lengthMiles > 8 && !userHasCategory('hydration')) {
      missingGear.push({ id: "rec-hydro", name: "Hydration Pack", estimated_cost: 40 });
      gearCost += 40;
    }

    // Rule: Poles
    if (elevationFt > 2000 && !userHasCategory('poles')) {
      missingGear.push({ id: "rec-poles", name: "Trekking Poles", estimated_cost: 60 });
      gearCost += 60;
    }

    // Rule: First Aid
    const isHard = selectedHike.difficulty === "DIFFICULT" || selectedHike.difficulty === "EXPERT";
    if (isHard && !userHasCategory('first_aid')) {
      missingGear.push({ id: "rec-aid", name: "First Aid Kit", estimated_cost: 25 });
      gearCost += 25;
    }

    // Travel estimate
    const travelCost = selectedHike.distance_from_user_miles
        ? Math.round(selectedHike.distance_from_user_miles * 0.6)
        : 0;

    return {
      missingGear,
      costs: {
        travel: travelCost,
        gear: gearCost,
        fees: selectedHike.park_fee ?? 0
      }
    };
  }, [selectedHike, items]);


  /* -----------------------------
     Render Helpers
  ------------------------------*/
  const formatDifficulty = (diff) => {
    if (!diff) return "Unknown";
    return diff.charAt(0) + diff.slice(1).toLowerCase();
  };

  const formatSeason = () => {
    if (!selectedHike.season_start_month || !selectedHike.season_end_month) return "Unknown";
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[selectedHike.season_start_month - 1]} - ${months[selectedHike.season_end_month - 1]}`;
  };

  if (loading || (!selectedHike && !error)) return <div className="p-8 text-center text-gray-500">Loading hike details...</div>;

  if (error) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <button onClick={() => navigate("/map")} className="text-gray-600 hover:text-gray-900 mb-4">
          &larr; Back to Map
        </button>
        <div className="p-8 text-center text-red-500 border border-red-200 rounded-lg bg-red-50">{error}</div>
      </div>
    );
  }

  if (!selectedHike) return null;

  /* -----------------------------
     MAIN RENDER
  ------------------------------*/
  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">

      <button onClick={() => navigate("/map")} className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Back to Map
      </button>

      {/* HERO SECTION */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* LEFT: Hike Data */}
        <div className="md:col-span-2 space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">{selectedHike.name}</h1>
                <p className="text-lg text-gray-600">{selectedHike.region}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <Stat label="Length" value={`${kmToMiles(selectedHike.length_km)} mi`} />
                <Stat label="Elevation" value={`${metersToFeet(selectedHike.elevation_gain_m)} ft`} />
                <Stat label="Difficulty" value={formatDifficulty(selectedHike.difficulty)} />
                <Stat label="Season" value={formatSeason()} />
            </div>

            {selectedHike.permits_required && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex gap-3">
                    <span className="text-2xl" role="img" aria-label="warning">⚠️</span>
                    <div>
                        <p className="text-yellow-800 font-medium">Permits Required</p>
                        <p className="text-sm text-yellow-700">Check local regulations before you go.</p>
                    </div>
                </div>
            )}
        </div>

        {/* RIGHT: Avatar Visual */}
        <div className="flex flex-col items-center justify-center bg-white rounded-2xl border border-gray-200 p-6 shadow-sm relative">
             <div className="absolute top-4 left-4 text-xs font-bold text-gray-400 uppercase tracking-widest">
                 Your Loadout
             </div>
             
             <div className="transform scale-90 origin-center">
                 <HikerAvatar gear={avatarVisualState} />
             </div>

             <div className="mt-4 text-center">
                 {evaluation && evaluation.missingGear.length > 0 ? (
                     <p className="text-sm text-red-500 font-medium">
                         Missing {evaluation.missingGear.length} recommended items
                     </p>
                 ) : (
                     <p className="text-sm text-green-600 font-medium flex items-center gap-1 justify-center">
                         <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                         Fully Prepared
                     </p>
                 )}
             </div>
        </div>
      </div>

      <hr className="border-gray-100" />

      {/* Evaluation & Costs Panel */}
      {evaluation && (
        <div>
            <h2 className="text-xl font-bold mb-4 text-gray-800">Trip Analysis</h2>
            <div className="grid md:grid-cols-2 gap-6">
                <MissingGearList items={evaluation.missingGear} />
                <CostBreakdownPanel costs={evaluation.costs} />
            </div>
        </div>
      )}

    </div>
  );
}