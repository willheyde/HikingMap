# AllGear.py
import sys
sys.path.append('..')
from PyObjects.Items import WeatherConditions

# NOTE: The "type" field maps to how the ItemService creates objects.
# In the current logic:
# - "backpack": Used for actual packs AND generic gear (stoves, water bottles, etc.)
# - "shoes": Footwear
# - "clothing": Wearables

GEAR_TAG_TO_ITEM_SPEC = {
    # ==================== HYDRATION ====================
    "water-bottle-500ml": {
        "type": "backpack",
        "name": "500ml Handheld Bottle",
        "weight": 0.5, "cost": 15.0, "capacity_liters": 0.5
    },
    "water-bottle-1l": {
        "type": "backpack",
        "name": "1L Tritan Bottle",
        "weight": 0.2, "cost": 15.0, "capacity_liters": 1.0
    },
    "hydration-bladder-2l": {
        "type": "backpack",
        "name": "2L Hydration Reservoir",
        "weight": 0.3, "cost": 35.0, "capacity_liters": 2.0
    },
    "hydration-bladder-3l": {
        "type": "backpack",
        "name": "3L Expedition Reservoir",
        "weight": 0.4, "cost": 45.0, "capacity_liters": 3.0
    },
    "water-filter-squeeze": {
        "type": "backpack",
        "name": "Squeeze Water Filter",
        "weight": 0.1, "cost": 40.0, "capacity_liters": 0.0
    },
    "purification-tablets": {
        "type": "backpack",
        "name": "Water Purification Tabs",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
     "collapsible-bottle-1l": {
        "type": "backpack",
        "name": "1L Collapsible Bottle",
        "weight": 0.05, "cost": 12.0, "capacity_liters": 1.0
    },
    "insulated-bottle-1l": {
        "type": "backpack",
        "name": "Insulated Vacuum Bottle 1L",
        "weight": 0.35, "cost": 25.0, "capacity_liters": 1.0
    },
    "water-container-5l": {
        "type": "backpack",
        "name": "5L Camp Water Container",
        "weight": 0.6, "cost": 18.0, "capacity_liters": 5.0
    },


    # ==================== FOOTWEAR ====================
    "trail-sandals": {
        "type": "shoes",
        "name": "Hiking Sandals",
        "weight": 0.5, "cost": 90.0,
        "weather_conditions": WeatherConditions.WARM,
        "crampons": False
    },
    "trail-runners": {
        "type": "shoes",
        "name": "Trail Running Shoes",
        "weight": 0.6, "cost": 130.0,
        "weather_conditions": WeatherConditions.WARM,
        "crampons": False
    },
    "hiking-shoes": {
        "type": "shoes",
        "name": "Mid-Cut Hiking Shoes",
        "weight": 0.9, "cost": 140.0,
        "weather_conditions": WeatherConditions.FINE,
        "crampons": False
    },
    "hiking-boots": {
        "type": "shoes",
        "name": "Leather Hiking Boots",
        "weight": 1.2, "cost": 220.0,
        "weather_conditions": WeatherConditions.COLD,
        "crampons": False
    },
    "mountaineering-boots": {
        "type": "shoes",
        "name": "Insulated Mountaineering Boots",
        "weight": 2.0, "cost": 450.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": True
    },
     "camp-slippers": {
        "type": "shoes",
        "name": "Camp Slip-On Sandals",
        "weight": 0.2, "cost": 25.0,
        "weather_conditions": WeatherConditions.FINE,
        "crampons": False
    },
    "snowshoes": {
        "type": "shoes",
        "name": "Snowshoes (pair)",
        "weight": 2.0, "cost": 180.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": False
    },

    # ==================== CLOTHING (TOPS/SHELLS) ====================
    "softshell-jacket": {
        "type": "clothing",
        "name": "Softshell Jacket",
        "weight": 0.4, "cost": 120.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "down-vest": {
        "type": "clothing",
        "name": "Down Vest",
        "weight": 0.25, "cost": 120.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "neck-gaiter-buff": {
        "type": "clothing",
        "name": "Neck Gaiter / Buff",
        "weight": 0.02, "cost": 15.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "hiking-shorts": {
        "type": "clothing",
        "name": "Lightweight Hiking Shorts",
        "weight": 0.18, "cost": 45.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "synthetic-underwear": {
        "type": "clothing",
        "name": "Quick-Dry Underwear",
        "weight": 0.05, "cost": 20.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "rain-hood-extra": {
        "type": "clothing",
        "name": "Packable Emergency Rain Hood",
        "weight": 0.06, "cost": 12.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "tshirt-synthetic": {
        "type": "clothing",
        "name": "Synthetic Tech Tee",
        "weight": 0.15, "cost": 30.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "sun-hoodie": {
        "type": "clothing",
        "name": "UPF Sun Hoodie",
        "weight": 0.2, "cost": 60.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "fleece-midlayer": {
        "type": "clothing",
        "name": "Grid Fleece Midlayer",
        "weight": 0.35, "cost": 90.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "puffer-jacket": {
        "type": "clothing",
        "name": "Down Puffer Jacket",
        "weight": 0.4, "cost": 250.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "rain-shell": {
        "type": "clothing",
        "name": "Waterproof Rain Shell",
        "weight": 0.3, "cost": 150.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "hard-shell-alpine": {
        "type": "clothing",
        "name": "Gore-Tex Alpine Shell",
        "weight": 0.5, "cost": 400.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "thermal-base-layer": {
        "type": "clothing",
        "name": "Merino Wool Base Layer",
        "weight": 0.2, "cost": 80.0,
        "weather_conditions": WeatherConditions.FREEZING
    },

    # ==================== CLOTHING (BOTTOMS/ACCESSORIES) ====================
    "hiking-pants-convertible": {
        "type": "clothing",
        "name": "Convertible Hiking Pants",
        "weight": 0.3, "cost": 70.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "rain-pants": {
        "type": "clothing",
        "name": "Waterproof Rain Pants",
        "weight": 0.25, "cost": 90.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "gaiters-low": {
        "type": "clothing",
        "name": "Trail Gaiters (Low)",
        "weight": 0.1, "cost": 25.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "gaiters-tall": {
        "type": "clothing",
        "name": "Alpine Gaiters (Tall)",
        "weight": 0.3, "cost": 60.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "gloves-liner": {
        "type": "clothing",
        "name": "Liner Gloves",
        "weight": 0.05, "cost": 25.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "gloves-insulated": {
        "type": "clothing",
        "name": "Waterproof Insulated Gloves",
        "weight": 0.2, "cost": 80.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "sun-hat": {
        "type": "clothing",
        "name": "Wide Brim Sun Hat",
        "weight": 0.1, "cost": 30.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "beanie-wool": {
        "type": "clothing",
        "name": "Merino Wool Beanie",
        "weight": 0.1, "cost": 35.0,
        "weather_conditions": WeatherConditions.COLD
    },

    # ==================== PACKS ====================
    "backpack-day-20l": {
        "type": "backpack",
        "name": "20L Daypack",
        "weight": 0.7, "cost": 90.0, "capacity_liters": 20.0
    },
    "backpack-multi-50l": {
        "type": "backpack",
        "name": "50L Backpacking Pack",
        "weight": 1.5, "cost": 200.0, "capacity_liters": 50.0
    },
    "backpack-expedition-75l": {
        "type": "backpack",
        "name": "75L Expedition Pack",
        "weight": 2.2, "cost": 350.0, "capacity_liters": 75.0
    },
     "stuff-sack-10l": {
        "type": "backpack",
        "name": "10L Compression Stuff Sack",
        "weight": 0.05, "cost": 12.0, "capacity_liters": 10.0
    },
    "bear-canister": {
        "type": "backpack",
        "name": "Bear-Resistant Food Canister",
        "weight": 1.5, "cost": 120.0, "capacity_liters": 8.0
    },
    "dry-bag-20l": {
        "type": "backpack",
        "name": "20L Dry Bag",
        "weight": 0.18, "cost": 25.0, "capacity_liters": 20.0
    },
    # ==================== SLEEP SYSTEM (Multi-Day) ====================
    "tent-1p-ultralight": {
        "type": "backpack",
        "name": "1P Ultralight Tent",
        "weight": 0.9, "cost": 350.0, "capacity_liters": 0.0
    },
    "tent-2p-3season": {
        "type": "backpack",
        "name": "2P 3-Season Tent",
        "weight": 2.0, "cost": 250.0, "capacity_liters": 0.0
    },
    "tent-4season": {
        "type": "backpack",
        "name": "4-Season Mountaineering Tent",
        "weight": 3.5, "cost": 600.0, "capacity_liters": 0.0
    },
    "sleeping-bag-30f": {
        "type": "backpack",
        "name": "30°F Down Sleeping Bag",
        "weight": 0.8, "cost": 200.0, "capacity_liters": 0.0
    },
    "sleeping-bag-0f": {
        "type": "backpack",
        "name": "0°F Winter Sleeping Bag",
        "weight": 1.4, "cost": 400.0, "capacity_liters": 0.0
    },
    "sleeping-pad-foam": {
        "type": "backpack",
        "name": "Closed Cell Foam Pad",
        "weight": 0.4, "cost": 45.0, "capacity_liters": 0.0
    },
    "sleeping-pad-inflatable": {
        "type": "backpack",
        "name": "Insulated Air Pad",
        "weight": 0.5, "cost": 150.0, "capacity_liters": 0.0
    },
    "hammock-1p": {
        "type": "backpack",
        "name": "1P Camping Hammock",
        "weight": 0.4, "cost": 80.0, "capacity_liters": 0.0
    },
    "tarp-3x3": {
        "type": "backpack",
        "name": "3x3 Lightweight Tarp",
        "weight": 0.5, "cost": 60.0, "capacity_liters": 0.0
    },
    "sleeping-bag-liner": {
        "type": "backpack",
        "name": "Silk / Lightweight Sleeping Bag Liner",
        "weight": 0.12, "cost": 40.0, "capacity_liters": 0.0
    },

    # ==================== KITCHEN ====================
    "stove-canister": {
        "type": "backpack",
        "name": "Ultralight Canister Stove",
        "weight": 0.1, "cost": 50.0, "capacity_liters": 0.0
    },
    "fuel-canister": {
        "type": "backpack",
        "name": "Isobutane Fuel (100g)",
        "weight": 0.2, "cost": 8.0, "capacity_liters": 0.0
    },
    "cook-pot-titanium": {
        "type": "backpack",
        "name": "Titanium Pot 750ml",
        "weight": 0.1, "cost": 45.0, "capacity_liters": 0.75
    },
    "food-meal": {
        "type": "backpack",
        "name": "Freeze-Dried Meal",
        "weight": 0.15, "cost": 12.0, "capacity_liters": 0.0
    },
    "food-snacks": {
        "type": "backpack",
        "name": "Energy Bar/Snacks",
        "weight": 0.1, "cost": 3.0, "capacity_liters": 0.0
    },
     "spork": {
        "type": "backpack",
        "name": "Ultralight Spork",
        "weight": 0.02, "cost": 4.0, "capacity_liters": 0.0
    },
    "lighter": {
        "type": "backpack",
        "name": "Refillable Lighter",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "matches-waterproof": {
        "type": "backpack",
        "name": "Waterproof Matches (box)",
        "weight": 0.01, "cost": 3.0, "capacity_liters": 0.0
    },
    "pot-lid-press": {
        "type": "backpack",
        "name": "Universal Pot Lid / Press",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
    "repair-kit": {
        "type": "backpack",
        "name": "Field Repair Kit (duct tape, patches, cord)",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },

    # ==================== TECHNICAL / SNOW ====================
    "trekking-poles": {
        "type": "backpack",
        "name": "Carbon Trekking Poles",
        "weight": 0.4, "cost": 120.0, "capacity_liters": 0.0
    },
    "crampons": {
        "type": "shoes",
        "name": "12-Point Crampons",
        "weight": 0.9, "cost": 160.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": True
    },
    "microspikes": {
        "type": "shoes",
        "name": "Traction Microspikes",
        "weight": 0.4, "cost": 70.0,
        "weather_conditions": WeatherConditions.COLD,
        "crampons": False
    },
    "ice-axe": {
        "type": "backpack",
        "name": "General Mountaineering Axe",
        "weight": 0.5, "cost": 100.0, "capacity_liters": 0.0
    },
    "helmet-climbing": {
        "type": "backpack",
        "name": "Climbing Helmet",
        "weight": 0.3, "cost": 80.0, "capacity_liters": 0.0
    },
    "harness": {
        "type": "backpack",
        "name": "Alpine Harness",
        "weight": 0.3, "cost": 60.0, "capacity_liters": 0.0
    },
    "rope-60m": {
        "type": "backpack",
        "name": "9.5mm Dry Rope (60m)",
        "weight": 3.5, "cost": 200.0, "capacity_liters": 0.0
    },
     "carabiner-locking": {
        "type": "backpack",
        "name": "Locking Carabiner (qty 1)",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
    "carabiner-wire": {
        "type": "backpack",
        "name": "Wiregate Carabiner (qty 1)",
        "weight": 0.04, "cost": 8.0, "capacity_liters": 0.0
    },
    "avalanche-beacon": {
        "type": "backpack",
        "name": "Avalanche Transceiver",
        "weight": 0.15, "cost": 300.0, "capacity_liters": 0.0
    },
    "avalanche-probe": {
        "type": "backpack",
        "name": "Avalanche Probe",
        "weight": 0.4, "cost": 130.0, "capacity_liters": 0.0
    },
    "avalanche-shovel": {
        "type": "backpack",
        "name": "Avalanche Shovel",
        "weight": 0.9, "cost": 120.0, "capacity_liters": 0.0
    },

    # ==================== ELECTRONICS ====================
    "headlamp": {
        "type": "backpack",
        "name": "Rechargeable Headlamp",
        "weight": 0.1, "cost": 45.0, "capacity_liters": 0.0
    },
    "power-bank": {
        "type": "backpack",
        "name": "10000mAh Power Bank",
        "weight": 0.2, "cost": 40.0, "capacity_liters": 0.0
    },
    "satellite-messenger": {
        "type": "backpack",
        "name": "Satellite Communicator",
        "weight": 0.2, "cost": 350.0, "capacity_liters": 0.0
    },
     "gps-handheld": {
        "type": "backpack",
        "name": "Handheld GPS Unit",
        "weight": 0.2, "cost": 200.0, "capacity_liters": 0.0
    },
    "altimeter-watch": {
        "type": "backpack",
        "name": "Altimeter / Barometer Watch",
        "weight": 0.1, "cost": 80.0, "capacity_liters": 0.0
    },
    "solar-panel-10w": {
        "type": "backpack",
        "name": "10W Solar Charger Panel",
        "weight": 0.45, "cost": 120.0, "capacity_liters": 0.0
    },
    "extra-batteries-headlamp": {
        "type": "backpack",
        "name": "Spare Batteries for Headlamp",
        "weight": 0.05, "cost": 5.0, "capacity_liters": 0.0
    },

    # ==================== SAFETY / ESSENTIALS ====================
    "first-aid-kit-basic": {
        "type": "backpack",
        "name": "Day Hiker First Aid Kit",
        "weight": 0.3, "cost": 30.0, "capacity_liters": 0.0
    },
    "first-aid-kit-mountain": {
        "type": "backpack",
        "name": "Mountain Medical Kit",
        "weight": 0.8, "cost": 90.0, "capacity_liters": 0.0
    },
    "navigation-map-compass": {
        "type": "backpack",
        "name": "Topo Map & Compass",
        "weight": 0.1, "cost": 25.0, "capacity_liters": 0.0
    },
    "bug-spray": {
        "type": "backpack",
        "name": "DEET Insect Repellent",
        "weight": 0.1, "cost": 8.0, "capacity_liters": 0.0
    },
    "bear-spray": {
        "type": "backpack",
        "name": "Bear Defense Spray",
        "weight": 0.3, "cost": 50.0, "capacity_liters": 0.0
    },
    "emergency-bivy": {
        "type": "backpack",
        "name": "Emergency Mylar Bivy",
        "weight": 0.1, "cost": 20.0, "capacity_liters": 0.0
    },
    "whistle": {
        "type": "backpack",
        "name": "Emergency Whistle",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "multi-tool": {
        "type": "backpack",
        "name": "Multi-tool (plier-style)",
        "weight": 0.25, "cost": 50.0, "capacity_liters": 0.0
    },
    "sewing-kit": {
        "type": "backpack",
        "name": "Mini Sewing / Patch Kit",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "trowel": {
        "type": "backpack",
        "name": "Folding Trowel (for cat-holes)",
        "weight": 0.08, "cost": 15.0, "capacity_liters": 0.0
    },
    "signal-mirror": {
        "type": "backpack",
        "name": "Signal Mirror",
        "weight": 0.02, "cost": 8.0, "capacity_liters": 0.0
    },
    "personal-locator-beacon": {
        "type": "backpack",
        "name": "PLB (Personal Locator Beacon)",
        "weight": 0.18, "cost": 250.0, "capacity_liters": 0.0
    }
    
}