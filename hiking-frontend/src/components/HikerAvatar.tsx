import React from 'react';

// Types for your gear system
type GearType = 
  | 'none'
  | 'base-layer'
  | 'light-backpack'
  | 'heavy-backpack'
  | 'shorts'
  | 'winter-pants'
  | 'boots'
  | 'trail-runners'
  | 'heavy-coat'
  | 'ice-axe'
  | 'crampons';

interface AvatarProps {
  gear: {
    back?: GearType;       
    bottoms: GearType;     
    feet: GearType;        
    torso: GearType;       
    head?: GearType;       
    accessoryRight?: GearType; 
    accessoryLeft?: GearType;
  };
  skinTone?: string;
}

const HikerAvatar: React.FC<AvatarProps> = ({ gear, skinTone = '#e0ac69' }) => {
  
  // RENDERER: instead of fetching URLs, we render CSS shapes
  const renderGearLayer = (type: GearType | undefined, layer: 'front' | 'back' | 'main') => {
    if (!type || type === 'none') return null;

    // --- BACKPACKS ---
    if (type.includes('backpack')) {
      const isHeavy = type === 'heavy-backpack';
      if (layer === 'back') {
        // The Bag behind the person
        return (
          <div className={`absolute bottom-24 w-40 transition-all rounded-xl border-2 border-gray-800
            ${isHeavy ? 'h-64 bg-green-800 -translate-y-4' : 'h-40 bg-orange-600'}`} 
          />
        );
      }
      if (layer === 'front') {
        // The Straps in front of the person
        return (
          <div className="absolute z-40 top-28 w-24 h-32 flex justify-between px-2 opacity-90">
             <div className={`w-3 h-full rounded-full ${isHeavy ? 'bg-green-900' : 'bg-orange-700'}`}></div>
             <div className={`w-3 h-full rounded-full ${isHeavy ? 'bg-green-900' : 'bg-orange-700'}`}></div>
          </div>
        );
      }
    }

    // --- BOTTOMS ---
    if (layer === 'main' && (type === 'shorts' || type === 'winter-pants')) {
        const isShorts = type === 'shorts';
        return (
            <div className="absolute z-20 bottom-28 w-28 flex justify-center gap-1">
                {/* Left Leg Pant */}
                <div className={`w-12 rounded-full ${isShorts ? 'h-24 bg-blue-400' : 'h-40 bg-gray-800'}`}></div>
                {/* Right Leg Pant */}
                <div className={`w-12 rounded-full ${isShorts ? 'h-24 bg-blue-400' : 'h-40 bg-gray-800'}`}></div>
            </div>
        );
    }

    // --- TORSO ---
    if (layer === 'main' && (type === 'base-layer' || type === 'heavy-coat')) {
        const isCoat = type === 'heavy-coat';
        return (
            <div className={`absolute z-30 bottom-44 rounded-2xl flex items-center justify-center
                ${isCoat ? 'w-36 h-48 bg-red-600 shadow-md' : 'w-28 h-44 bg-gray-200'}`}>
                {/* Zipper detail */}
                <div className="w-1 h-full bg-black/10"></div>
            </div>
        );
    }

    // --- FEET ---
    if (layer === 'main' && (type === 'boots' || type === 'trail-runners')) {
        const isBoot = type === 'boots';
        return (
            <div className="absolute z-30 bottom-0 w-40 flex justify-between px-4">
                 <div className={`w-14 rounded-xl ${isBoot ? 'h-16 bg-yellow-700 border-b-4 border-black' : 'h-10 bg-gray-400'}`}></div>
                 <div className={`w-14 rounded-xl ${isBoot ? 'h-16 bg-yellow-700 border-b-4 border-black' : 'h-10 bg-gray-400'}`}></div>
            </div>
        );
    }

    // --- ACCESSORIES ---
    if (layer === 'main' && type === 'ice-axe') {
        return (
            <div className="w-2 h-24 bg-gray-400 relative rotate-12">
                <div className="absolute top-0 -left-4 w-10 h-1 bg-gray-600"></div>
            </div>
        );
    }

    return null;
  };

  return (
    <div className="relative w-64 h-96 flex justify-center items-end bg-sky-100 rounded-xl overflow-hidden border-4 border-gray-300 shadow-xl">
      
      {/* LAYER 1: BEHIND BODY (Backpack Main Body) */}
      <div className="absolute bottom-0 w-full flex justify-center z-0">
        {renderGearLayer(gear.back, 'back')}
      </div>

      {/* LAYER 2: THE BODY (Mannequin) */}
      <div className="absolute z-10 bottom-4 w-32 h-80 flex flex-col items-center">
         {/* Head */}
         <div className="w-16 h-20 rounded-full mb-1 relative z-20" style={{ backgroundColor: skinTone }}></div>
         {/* Torso Base (Skin) */}
         <div className="w-28 h-40 rounded-3xl z-10" style={{ backgroundColor: skinTone }}></div>
         {/* Legs (Skin) */}
         <div className="flex gap-2 mt-[-20px] z-0">
             <div className="w-10 h-40 rounded-full" style={{ backgroundColor: skinTone }}></div>
             <div className="w-10 h-40 rounded-full" style={{ backgroundColor: skinTone }}></div>
         </div>
      </div>

      {/* LAYER 3: BOTTOMS */}
      {renderGearLayer(gear.bottoms, 'main')}

      {/* LAYER 4: FEET */}
      {renderGearLayer(gear.feet, 'main')}

      {/* LAYER 5: TORSO */}
      {renderGearLayer(gear.torso, 'main')}

      {/* LAYER 6: FRONT STRAPS */}
      {renderGearLayer(gear.back, 'front')}

      {/* LAYER 7: HANDHELD ITEMS */}
      {gear.accessoryRight && (
         <div className="absolute z-50 bottom-40 right-10">
            {renderGearLayer(gear.accessoryRight, 'main')}
         </div>
      )}

    </div>
  );
};

export default HikerAvatar;