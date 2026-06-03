import sys
sys.path.append('..')
from PyObjects.Items import WeatherConditions

# NOTE: The "type" field maps exactly to the expected endpoint route strings 
# to ensure populate_items.py seamlessly routes to the correct ItemService models.

GEAR_TAG_TO_ITEM_SPEC = {
    # ==================== SHELTER ====================
    "hyperlite-ultamid-2-tarp": {
        "id": "8b7c7b8c-8f4b-4a5c-9cbe-79f9720d2d3a",
        "type": "shelter",
        "name": "Hyperlite UltaMid 2 Tarp",
        "weight": 0.567, "cost": 600.0,
        "shelter_type": "tarp", "season_rating": "3_season", "capacity_persons": 2
    },
    "nemo-hornet-elite-osmo-2p": {
        "id": "cd40e1b1-2ef3-4d43-bc06-a82f3a61bc5b",
        "type": "shelter",
        "name": "NEMO Hornet Elite OSMO 2P",
        "weight": 0.822, "cost": 600.0,
        "shelter_type": "tent", "season_rating": "3_season", "capacity_persons": 2
    },
    "sol-escape-bivy": {
        "id": "7fb5a497-6c2e-4b72-88f5-373b9e4bc11c",
        "type": "shelter",
        "name": "SOL Escape Bivy",
        "weight": 0.283, "cost": 60.0,
        "shelter_type": "bivy", "season_rating": "summer", "capacity_persons": 1
    },

    # ==================== SLEEPING ====================
    "therm-a-rest-neoair-xlite": {
        "id": "e80c8df4-05d4-42b7-a3d8-e7bf8df726bf",
        "type": "sleeping_pad",
        "name": "Therm-a-Rest NeoAir XLite (R3.2)",
        "weight": 0.354, "cost": 200.0,
        "r_value": 3.2, "pad_type": "inflatable"
    },
    "mountain-hardwear-phantom-0f": {
        "id": "9d863cbb-5bbd-46f9-bd1b-c73e04e4a77f",
        "type": "sleeping_bag",
        "name": "Mountain Hardware Phantom 0°F",
        "weight": 0.794, "cost": 650.0,
        "fill_type": "down", "temp_rating_f": 0
    },

    # ==================== KITCHEN ====================
    "msr-pocketrocket-2": {
        "id": "1bb4542d-20fb-4ebc-8824-738b809a47d2",
        "type": "kitchen",
        "name": "MSR PocketRocket 2",
        "weight": 0.073, "cost": 55.0,
        "stove_type": "canister", "boil_time_min": 3.5, "cookware_included": False
    },
    "msr-titan-kettle": {
        "id": "d54fe6f2-bf89-4e41-9bf5-c045b8fb0e12",
        "type": "kitchen",
        "name": "MSR Titan Titanium Kettle",
        "weight": 0.103, "cost": 90.0,
        "stove_type": None, "boil_time_min": 0, "cookware_included": False
    },

    # ==================== WATER ====================
    "sawyer-squeeze-filter": {
        "id": "fa0ca8b8-4c6e-473d-986c-035df901235a",
        "type": "water",
        "name": "Sawyer Squeeze Filter",
        "weight": 0.085, "cost": 40.0,
        "system_type": "filter", "flow_rate_lpm": 1.7
    },
    "msr-guardian-purifier": {
        "id": "28b3cf68-4f1e-4589-bad4-2a6c0bbf2f07",
        "type": "water",
        "name": "MSR Guardian Purifier",
        "weight": 0.490, "cost": 350.0,
        "system_type": "purifier", "flow_rate_lpm": 2.5
    },

    # ==================== BACKPACKS ====================
    "osprey-atmos-ag-50": {
        "id": "f2096e23-7a91-49fa-948b-3e817bf5b8cf",
        "type": "backpack",
        "name": "Osprey Atmos AG 50",
        "weight": 1.360, "cost": 270.0,
        "frame_type": "internal", "size_class": "weekend", "capacity_liters": 50
    },
    "hyperlite-3400-sw-55": {
        "id": "c73e2189-dce2-4bb3-8b7c-03d32ef39d48",
        "type": "backpack",
        "name": "Hyperlite 3400 SW 55",
        "weight": 0.567, "cost": 425.0,
        "frame_type": "frameless", "size_class": "expedition", "capacity_liters": 55
    },

    # ==================== CLOTHING ====================
    "arcteryx-beta-lt": {
        "id": "694fb4e3-3051-41bb-a5eb-0683a31c55b1",
        "type": "clothing",
        "name": "Arc'teryx Beta LT",
        "weight": 0.340, "cost": 600.0,
        "layer_type": "shell", "min_temp_f": 32, "waterproof": True, "garment_type": "top"
    },
    "patagonia-r1-fleece": {
        "id": "582e0d1c-b873-4560-98b1-3e4e4604fb67",
        "type": "clothing",
        "name": "Patagonia R1 Fleece",
        "weight": 0.318, "cost": 140.0,
        "layer_type": "mid", "min_temp_f": 20, "waterproof": False, "garment_type": "top"
    },
    "smartwool-merino-150-base": {
        "id": "318b3ff1-e129-4171-88f3-85cb9cf46fb8",
        "type": "clothing",
        "name": "Smartwool Merino 150 Base Top",
        "weight": 0.170, "cost": 80.0,
        "layer_type": "base", "min_temp_f": 32, "waterproof": False, "garment_type": "top"
    },

    # ==================== FOOTWEAR ====================
    "salomon-speedcross-6": {
        "id": "4db74c43-df9c-4447-97d8-552be90fa38d",
        "type": "footwear",
        "name": "Salomon Speedcross 6",
        "weight": 0.640, "cost": 140.0,
        "weather_conditions": WeatherConditions.WARM,
        "waterproof": False, "ankle_support": "low", "footwear_type": "trail_runner", "crampon_compatible": False, "crampons": False
    },
    "scarpa-zodiac-plus-gtx": {
        "id": "b5c18a93-b6d3-4613-88df-6435bc2cbda4",
        "type": "footwear",
        "name": "Scarpa Zodiac Plus GTX",
        "weight": 1.340, "cost": 300.0,
        "weather_conditions": WeatherConditions.COLD,
        "waterproof": True, "ankle_support": "high", "footwear_type": "mountaineering_boot", "crampon_compatible": True, "crampons": True
    },
    "merrell-moab-3-mid-wp": {
        "id": "a6b22b10-0931-4874-98c4-df25c0df3ab6",
        "type": "footwear",
        "name": "Merrell Moab 3 Mid WP",
        "weight": 0.960, "cost": 130.0,
        "weather_conditions": WeatherConditions.FINE,
        "waterproof": True, "ankle_support": "mid", "footwear_type": "hiking_boot", "crampon_compatible": False, "crampons": False
    },

    # ==================== NAVIGATION ====================
    "garmin-inreach-mini-2": {
        "id": "18f5d0f6-d8cb-4654-be6c-cb2d6bbfa784",
        "type": "navigation",
        "name": "Garmin inReach Mini 2",
        "weight": 0.100, "cost": 350.0,
        "nav_type": "satellite_communicator"
    },
    "silva-ranger-2-compass": {
        "id": "a8b23c21-f3b1-4b71-9dfc-5c142e97b102",
        "type": "navigation",
        "name": "Silva Ranger 2.0 Compass",
        "weight": 0.055, "cost": 55.0,
        "nav_type": "compass"
    },

    # ==================== SAFETY & LIGHTING ====================
    "rei-backpacker-first-aid": {
        "id": "7823f6e1-5bf3-40fd-bc33-03dbefd40d99",
        "type": "safety",
        "name": "REI Backpacker First Aid Kit",
        "weight": 0.340, "cost": 50.0,
        "safety_type": "first_aid", "avalanche_rated": False
    },
    "bca-tracker-4-beacon": {
        "id": "2a94fb21-ce11-42cb-bdf8-21fbdf8734bc",
        "type": "safety",
        "name": "BCA Tracker 4 Beacon",
        "weight": 0.260, "cost": 420.0,
        "safety_type": "beacon", "avalanche_rated": True
    },
    "petzl-actik-core-600": {
        "id": "bb3efda4-da48-4cb9-95fb-6cc028f3d1b7",
        "type": "lighting",
        "name": "Petzl Actik Core 600",
        "weight": 0.067, "cost": 55.0,
        "lumens": 600, "lighting_type": "headlamp"
    },

    # ==================== TECHNICAL GEAR ====================
    "camp-corsa-nanotech-carbon": {
        "id": "409ab4fd-cf31-419b-abfc-f3cbe8cf41dd",
        "type": "technical",
        "name": "CAMP Corsa Nanotech Carbon",
        "weight": 0.348, "cost": 220.0,
        "material": "carbon", "adjustable": True
    },
    "petzl-summit-evo-ice-axe": {
        "id": "de10cfbd-4df3-40cb-ba12-fef123bc8041",
        "type": "technical",
        "name": "Petzl Summit Evo Ice Axe 60cm",
        "weight": 0.395, "cost": 120.0,
        "technical_type": "ice_axe"
    },
    "black-diamond-oval-carabiner": {
        "id": "f5bc812d-98bc-4672-88df-f290ce48231c",
        "type": "technical",
        "name": "Black Diamond Oval Carabiner",
        "weight": 0.068, "cost": 16.0,
        "technical_type": "carabiner"
    }
}