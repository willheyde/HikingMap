// src/data/gearOptions.js

// This maps the specific Python ID to the visual shape your HikerAvatar expects
// Visual options: 'boots', 'runners', 'heavy-coat', 'rain-shell', 'base-layer', 
// 'heavy-backpack', 'light-backpack', 'ice-axe', 'poles', 'headlamp', 'crampons'

export const GEAR_OPTIONS = [
  // --- FOOTWEAR ---
  { id: "hiking-boots", name: "Leather Hiking Boots", category: "Footwear", visual: "boots", cost: 220, weight: 1.2 },
  { id: "trail-runners", name: "Trail Runners", category: "Footwear", visual: "trail-runners", cost: 130, weight: 0.6 },
  { id: "mountaineering-boots", name: "Mountaineering Boots", category: "Footwear", visual: "boots", cost: 450, weight: 2.0 },
  
  // --- CLOTHING ---
  { id: "puffer-jacket", name: "Down Puffer Jacket", category: "Torso", visual: "heavy-coat", cost: 250, weight: 0.4 },
  { id: "rain-shell", name: "Rain Shell", category: "Torso", visual: "rain-shell", cost: 150, weight: 0.3 },
  { id: "thermal-base-layer", name: "Merino Base Layer", category: "Torso", visual: "base-layer", cost: 80, weight: 0.2 },
  
  // --- PACKS ---
  { id: "backpack-multi-50l", name: "50L Backpack", category: "Back", visual: "heavy-backpack", cost: 200, weight: 1.5 },
  { id: "backpack-day-20l", name: "20L Daypack", category: "Back", visual: "light-backpack", cost: 90, weight: 0.7 },
  
  // --- TECHNICAL ---
  { id: "ice-axe", name: "Ice Axe", category: "Hand", visual: "ice-axe", cost: 100, weight: 0.5 },
  { id: "trekking-poles", name: "Trekking Poles", category: "Hand", visual: "poles", cost: 120, weight: 0.4 },
  { id: "crampons", name: "Crampons", category: "Feet", visual: "crampons", cost: 160, weight: 0.9 },
  
  // --- ESSENTIALS (Non-visual items, but need to be selectable) ---
  { id: "headlamp", name: "Headlamp", category: "Head", visual: "headlamp", cost: 45, weight: 0.1 },
  { id: "stove-canister", name: "Canister Stove", category: "Kitchen", visual: null, cost: 50, weight: 0.1 },
  { id: "tent-2p-3season", name: "2P Tent", category: "Shelter", visual: null, cost: 250, weight: 2.0 },
];