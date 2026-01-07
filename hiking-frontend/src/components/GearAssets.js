// GearAssets.js
// This maps your gear IDs to icons (for the menu) and layers (for the avatar)

import { 
  Footprints, Shirt, Mountain, CloudRain, 
  ThermometerSnowflake, Hammer, Navigation, Flashlight, 
  Droplets, Backpack 
} from 'lucide-react';

export const GEAR_DEFINITIONS = [
  { 
    id: "hiking-boots", 
    name: "Heavy Boots", 
    category: "feet", 
    icon: Footprints,
    layerColor: "bg-amber-800", // Replace with: image: '/assets/boots_3d.png'
    zIndex: 10 
  },
  { 
    id: "trail-runners", 
    name: "Trail Runners", 
    category: "feet", 
    icon: Footprints,
    layerColor: "bg-blue-600", 
    zIndex: 10 
  },
  { 
    id: "hiking-pants-convertible", 
    name: "Hiking Pants", 
    category: "legs", 
    icon: Shirt,
    layerColor: "bg-stone-600", 
    zIndex: 20 
  },
  { 
    id: "puffer-jacket", 
    name: "Puffer Jacket", 
    category: "torso", 
    icon: Mountain,
    layerColor: "bg-red-600", 
    zIndex: 30 
  },
  { 
    id: "rain-shell", 
    name: "Rain Shell", 
    category: "torso", 
    icon: CloudRain,
    layerColor: "bg-yellow-400", 
    zIndex: 35 
  },
  { 
    id: "thermal-base-layer", 
    name: "Thermals", 
    category: "torso", 
    icon: ThermometerSnowflake,
    layerColor: "bg-gray-800", 
    zIndex: 25 
  },
  { 
    id: "backpack-day-20l", 
    name: "Day Pack", 
    category: "back", 
    icon: Backpack,
    layerColor: "bg-green-700", 
    zIndex: 5 
  },
  { 
    id: "backpack-multi-50l", 
    name: "50L Ruck", 
    category: "back", 
    icon: Backpack,
    layerColor: "bg-orange-700", 
    zIndex: 4 
  },
  { 
    id: "ice-axe", 
    name: "Ice Axe", 
    category: "hand-r", 
    icon: Hammer,
    layerColor: "bg-gray-400", 
    zIndex: 40 
  },
  { 
    id: "trekking-poles", 
    name: "Poles", 
    category: "hand-r", 
    icon: Navigation,
    layerColor: "bg-black", 
    zIndex: 40 
  }
];