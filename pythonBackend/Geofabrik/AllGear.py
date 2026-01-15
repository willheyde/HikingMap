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
        "id": "c13e03ed-669f-40b9-b1f2-87dee7747e4a",
        "type": "backpack",
        "name": "500ml Handheld Bottle",
        "weight": 0.5, "cost": 15.0, "capacity_liters": 0.5
    },
    "water-bottle-1l": {
        "id": "79276ad8-0a2b-4062-a48c-347fbee042b1",
        "type": "backpack",
        "name": "1L Tritan Bottle",
        "weight": 0.2, "cost": 15.0, "capacity_liters": 1.0
    },
    "hydration-bladder-2l": {
        "id": "72a80d74-87cf-42e1-9feb-838bc75ee23f",
        "type": "backpack",
        "name": "2L Hydration Reservoir",
        "weight": 0.3, "cost": 35.0, "capacity_liters": 2.0
    },
    "hydration-bladder-3l": {
        "id": "b7ba42ae-b5f8-42b1-ae82-dc016c8bdc14",
        "type": "backpack",
        "name": "3L Expedition Reservoir",
        "weight": 0.4, "cost": 45.0, "capacity_liters": 3.0
    },
    "water-filter-squeeze": {
        "id": "557ca84e-2361-4c89-ae60-d6f61c33135e",
        "type": "backpack",
        "name": "Squeeze Water Filter",
        "weight": 0.1, "cost": 40.0, "capacity_liters": 0.0
    },
    "purification-tablets": {
        "id": "76cd5481-e996-4d94-8a74-2ff6085c731b",
        "type": "backpack",
        "name": "Water Purification Tabs",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
     "collapsible-bottle-1l": {
        "id": "ace084c9-0996-4b7c-b118-e5b07f81695c",
        "type": "backpack",
        "name": "1L Collapsible Bottle",
        "weight": 0.05, "cost": 12.0, "capacity_liters": 1.0
    },
    "insulated-bottle-1l": {
        "id": "ccb13558-bff7-4650-97d5-f7988607d6df",
        "type": "backpack",
        "name": "Insulated Vacuum Bottle 1L",
        "weight": 0.35, "cost": 25.0, "capacity_liters": 1.0
    },
    "water-container-5l": {
        "id": "90f0420b-a803-4381-9778-88e0da68bba4",
        "type": "backpack",
        "name": "5L Camp Water Container",
        "weight": 0.6, "cost": 18.0, "capacity_liters": 5.0
    },


    # ==================== FOOTWEAR ====================
    "trail-sandals": {
        "id": "ed251b70-2c3e-42fa-80a9-accce2eedb25",
        "type": "shoes",
        "name": "Hiking Sandals",
        "weight": 0.5, "cost": 90.0,
        "weather_conditions": WeatherConditions.WARM,
        "crampons": False
    },
    "trail-runners": {
        "id": "a415270e-6ed0-49dc-a04b-ba37cb14b837",
        "type": "shoes",
        "name": "Trail Running Shoes",
        "weight": 0.6, "cost": 130.0,
        "weather_conditions": WeatherConditions.WARM,
        "crampons": False
    },
    "hiking-shoes": {
        "id": "b7989807-4d1e-48b4-99e1-09ca6cc05971",
        "type": "shoes",
        "name": "Mid-Cut Hiking Shoes",
        "weight": 0.9, "cost": 140.0,
        "weather_conditions": WeatherConditions.FINE,
        "crampons": False
    },
    "hiking-boots": {
        "id": "27622021-e99d-4455-9573-db5e107ac5e4",
        "type": "shoes",
        "name": "Leather Hiking Boots",
        "weight": 1.2, "cost": 220.0,
        "weather_conditions": WeatherConditions.COLD,
        "crampons": False
    },
    "mountaineering-boots": {
        "id": "a679fdc4-6b74-407d-a649-fab4163d7350",
        "type": "shoes",
        "name": "Insulated Mountaineering Boots",
        "weight": 2.0, "cost": 450.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": True
    },
     "camp-slippers": {
        "id": "26e77986-60ef-4c24-b430-d75341b9bea8",
        "type": "shoes",
        "name": "Camp Slip-On Sandals",
        "weight": 0.2, "cost": 25.0,
        "weather_conditions": WeatherConditions.FINE,
        "crampons": False
    },
    "snowshoes": {
        "id": "488ebdb6-bf28-4d32-b3e6-9ce08bf677c8",
        "type": "shoes",
        "name": "Snowshoes (pair)",
        "weight": 2.0, "cost": 180.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": False
    },

    # ==================== CLOTHING (TOPS/SHELLS) ====================
    "softshell-jacket": {
        "id": "89316839-a54a-40f5-b74f-39c52547b07a",
        "type": "clothing",
        "name": "Softshell Jacket",
        "weight": 0.4, "cost": 120.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "down-vest": {
        "id": "f2b10512-8772-4c3e-adef-00f282b5691a",
        "type": "clothing",
        "name": "Down Vest",
        "weight": 0.25, "cost": 120.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "neck-gaiter-buff": {
        "id": "759ea7f7-1d01-4fa5-8a0b-1cd52071976d",
        "type": "clothing",
        "name": "Neck Gaiter / Buff",
        "weight": 0.02, "cost": 15.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "hiking-shorts": {
        "id": "9682d316-8706-4192-ae3b-111480861f5a",
        "type": "clothing",
        "name": "Lightweight Hiking Shorts",
        "weight": 0.18, "cost": 45.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "synthetic-underwear": {
        "id": "d5d836a8-1cc6-4534-b398-4c4f823fe340",
        "type": "clothing",
        "name": "Quick-Dry Underwear",
        "weight": 0.05, "cost": 20.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "rain-hood-extra": {
        "id": "55fa6a44-5699-46e5-b84d-c14bd6f027e5",
        "type": "clothing",
        "name": "Packable Emergency Rain Hood",
        "weight": 0.06, "cost": 12.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "tshirt-synthetic": {
        "id": "6fbf43c5-eeec-4753-a917-881be646e620",
        "type": "clothing",
        "name": "Synthetic Tech Tee",
        "weight": 0.15, "cost": 30.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "sun-hoodie": {
        "id": "11284ffb-e6a3-4f3e-96f6-dfe37564be98",
        "type": "clothing",
        "name": "UPF Sun Hoodie",
        "weight": 0.2, "cost": 60.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "fleece-midlayer": {
        "id": "5dd1db42-7b2d-4ca0-aca9-0ded71124066",
        "type": "clothing",
        "name": "Grid Fleece Midlayer",
        "weight": 0.35, "cost": 90.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "puffer-jacket": {
        "id": "9845e47d-01d2-4d6f-b220-9d35ec12761c",
        "type": "clothing",
        "name": "Down Puffer Jacket",
        "weight": 0.4, "cost": 250.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "rain-shell": {
        "id": "360daa4c-1d97-49d9-9caa-77b1525d9f76",
        "type": "clothing",
        "name": "Waterproof Rain Shell",
        "weight": 0.3, "cost": 150.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "hard-shell-alpine": {
        "id": "a700193a-ceca-4a37-8b5f-e6d6211f3841",
        "type": "clothing",
        "name": "Gore-Tex Alpine Shell",
        "weight": 0.5, "cost": 400.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "thermal-base-layer": {
        "id": "beac5d43-1de2-4cf4-a24d-e08b7e2a2f17",
        "type": "clothing",
        "name": "Merino Wool Base Layer",
        "weight": 0.2, "cost": 80.0,
        "weather_conditions": WeatherConditions.FREEZING
    },

    # ==================== CLOTHING (BOTTOMS/ACCESSORIES) ====================
    "hiking-pants-convertible": {
        "id": "2090e458-9357-4f2b-936c-1d8a5d407ec2",
        "type": "clothing",
        "name": "Convertible Hiking Pants",
        "weight": 0.3, "cost": 70.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "rain-pants": {
        "id": "0bff81a0-c6d0-4d35-bb16-81ec1bb94d70",
        "type": "clothing",
        "name": "Waterproof Rain Pants",
        "weight": 0.25, "cost": 90.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "gaiters-low": {
        "id": "6bcce3e3-c03c-48fd-b7b0-f7e0dcd8937a",
        "type": "clothing",
        "name": "Trail Gaiters (Low)",
        "weight": 0.1, "cost": 25.0,
        "weather_conditions": WeatherConditions.FINE
    },
    "gaiters-tall": {
        "id": "9c483ffc-d783-44e0-bcb0-73b991ed852a",
        "type": "clothing",
        "name": "Alpine Gaiters (Tall)",
        "weight": 0.3, "cost": 60.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "gloves-liner": {
        "id": "cf259a26-a343-4d53-9949-56486c955ba3",
        "type": "clothing",
        "name": "Liner Gloves",
        "weight": 0.05, "cost": 25.0,
        "weather_conditions": WeatherConditions.COLD
    },
    "gloves-insulated": {
        "id": "bd8054fb-d4e5-46ec-88fd-be04bbbbfd30",
        "type": "clothing",
        "name": "Waterproof Insulated Gloves",
        "weight": 0.2, "cost": 80.0,
        "weather_conditions": WeatherConditions.FREEZING
    },
    "sun-hat": {
        "id": "f5309bc0-1aa7-405d-b97b-60befb53652c",
        "type": "clothing",
        "name": "Wide Brim Sun Hat",
        "weight": 0.1, "cost": 30.0,
        "weather_conditions": WeatherConditions.WARM
    },
    "beanie-wool": {
        "id": "2ff7545d-e87e-4a9b-af02-debd77057712",
        "type": "clothing",
        "name": "Merino Wool Beanie",
        "weight": 0.1, "cost": 35.0,
        "weather_conditions": WeatherConditions.COLD
    },

    # ==================== PACKS ====================
    "backpack-day-20l": {
        "id": "9298b8d5-9ed6-4d40-aded-0b16dff85556",
        "type": "backpack",
        "name": "20L Daypack",
        "weight": 0.7, "cost": 90.0, "capacity_liters": 20.0
    },
    "backpack-multi-50l": {
        "id": "0a943e79-1acc-4407-90e9-f38d3b1f17d2",
        "type": "backpack",
        "name": "50L Backpacking Pack",
        "weight": 1.5, "cost": 200.0, "capacity_liters": 50.0
    },
    "backpack-expedition-75l": {
        "id": "9391dec0-0dd1-4a2b-8b1a-1a121151a9d1",
        "type": "backpack",
        "name": "75L Expedition Pack",
        "weight": 2.2, "cost": 350.0, "capacity_liters": 75.0
    },
     "stuff-sack-10l": {
        "id": "d237e6ec-cb3d-49bf-8ddb-a89740953a00",
        "type": "backpack",
        "name": "10L Compression Stuff Sack",
        "weight": 0.05, "cost": 12.0, "capacity_liters": 10.0
    },
    "bear-canister": {
        "id": "98ee92a5-5bb1-4a79-a671-142aef1247e4",
        "type": "backpack",
        "name": "Bear-Resistant Food Canister",
        "weight": 1.5, "cost": 120.0, "capacity_liters": 8.0
    },
    "dry-bag-20l": {
        "id": "cd1a85a9-8647-4c71-acc4-ea9ce47e2abd",
        "type": "backpack",
        "name": "20L Dry Bag",
        "weight": 0.18, "cost": 25.0, "capacity_liters": 20.0
    },
    # ==================== SLEEP SYSTEM (Multi-Day) ====================
    "tent-1p-ultralight": {
        "id": "bf3a90d4-87ae-4538-88d7-5296d772486b",
        "type": "backpack",
        "name": "1P Ultralight Tent",
        "weight": 0.9, "cost": 350.0, "capacity_liters": 0.0
    },
    "tent-2p-3season": {
        "id": "bd6d0367-1d69-4cfb-84e7-d30b3940ee71",
        "type": "backpack",
        "name": "2P 3-Season Tent",
        "weight": 2.0, "cost": 250.0, "capacity_liters": 0.0
    },
    "tent-4season": {
        "id": "38272098-6339-4a82-be27-14cfe0233844",
        "type": "backpack",
        "name": "4-Season Mountaineering Tent",
        "weight": 3.5, "cost": 600.0, "capacity_liters": 0.0
    },
    "sleeping-bag-30f": {
        "id": "6d2bec2a-11c3-40a6-aa9f-dd45f2907fbc",
        "type": "backpack",
        "name": "30°F Down Sleeping Bag",
        "weight": 0.8, "cost": 200.0, "capacity_liters": 0.0
    },
    "sleeping-bag-0f": {
        "id": "d54b759e-026f-4658-bfb2-6aef8cd9645f",
        "type": "backpack",
        "name": "0°F Winter Sleeping Bag",
        "weight": 1.4, "cost": 400.0, "capacity_liters": 0.0
    },
    "sleeping-pad-foam": {
        "id": "16c98043-d056-4098-975e-7036a88b6bf8",
        "type": "backpack",
        "name": "Closed Cell Foam Pad",
        "weight": 0.4, "cost": 45.0, "capacity_liters": 0.0
    },
    "sleeping-pad-inflatable": {
        "id": "52afd622-52a5-4f9f-8332-0c98517f61f2",
        "type": "backpack",
        "name": "Insulated Air Pad",
        "weight": 0.5, "cost": 150.0, "capacity_liters": 0.0
    },
    "hammock-1p": {
        "id": "ed437009-efe2-4022-addd-cc2f56a1d31b",
        "type": "backpack",
        "name": "1P Camping Hammock",
        "weight": 0.4, "cost": 80.0, "capacity_liters": 0.0
    },
    "tarp-3x3": {
        "id": "182821ff-1a3b-4fe4-8f08-cad5cb588988",
        "type": "backpack",
        "name": "3x3 Lightweight Tarp",
        "weight": 0.5, "cost": 60.0, "capacity_liters": 0.0
    },
    "sleeping-bag-liner": {
        "id": "dd6ad17f-74e1-4302-a4a4-a7a1ff96331b",
        "type": "backpack",
        "name": "Silk / Lightweight Sleeping Bag Liner",
        "weight": 0.12, "cost": 40.0, "capacity_liters": 0.0
    },

    # ==================== KITCHEN ====================
    "stove-canister": {
        "id": "65196f32-d915-4798-ae7f-427847e7f633",
        "type": "backpack",
        "name": "Ultralight Canister Stove",
        "weight": 0.1, "cost": 50.0, "capacity_liters": 0.0
    },
    "fuel-canister": {
        "id": "cecaf579-6737-4b9d-8767-3c8d88463baa",
        "type": "backpack",
        "name": "Isobutane Fuel (100g)",
        "weight": 0.2, "cost": 8.0, "capacity_liters": 0.0
    },
    "cook-pot-titanium": {
        "id": "93c06658-4942-4160-93d5-a7d61552b771",
        "type": "backpack",
        "name": "Titanium Pot 750ml",
        "weight": 0.1, "cost": 45.0, "capacity_liters": 0.75
    },
    "food-meal": {
        "id": "6ad9cabd-ecd3-4559-ae27-cdf908d1857d",
        "type": "backpack",
        "name": "Freeze-Dried Meal",
        "weight": 0.15, "cost": 12.0, "capacity_liters": 0.0
    },
    "food-snacks": {
        "id": "e32ff42b-1342-44ea-8b40-846c1dfc4125",
        "type": "backpack",
        "name": "Energy Bar/Snacks",
        "weight": 0.1, "cost": 3.0, "capacity_liters": 0.0
    },
     "spork": {
        "id": "0e85325e-8c83-4c21-bcb7-ae63f72e98b9",
        "type": "backpack",
        "name": "Ultralight Spork",
        "weight": 0.02, "cost": 4.0, "capacity_liters": 0.0
    },
    "lighter": {
        "id": "4b6eb29a-6453-4143-a612-e9bdaf568e0e",
        "type": "backpack",
        "name": "Refillable Lighter",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "matches-waterproof": {
        "id": "e7f4ffd3-9913-4d15-a72c-328fff01e305",
        "type": "backpack",
        "name": "Waterproof Matches (box)",
        "weight": 0.01, "cost": 3.0, "capacity_liters": 0.0
    },
    "pot-lid-press": {
        "id": "82319cef-9032-4060-8273-6d049696b982",
        "type": "backpack",
        "name": "Universal Pot Lid / Press",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
    "repair-kit": {
        "id": "fb485575-5dd9-4937-b057-fafd8bbd0f94",
        "type": "backpack",
        "name": "Field Repair Kit (duct tape, patches, cord)",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },

    # ==================== TECHNICAL / SNOW ====================
    "trekking-poles": {
        "id": "0deccee6-2b4a-4aa1-a14f-e3427a08a14a",
        "type": "backpack",
        "name": "Carbon Trekking Poles",
        "weight": 0.4, "cost": 120.0, "capacity_liters": 0.0
    },
    "crampons": {
        "id": "49817d1f-a2a3-45d7-81a9-8bd0968c2f64",
        "type": "shoes",
        "name": "12-Point Crampons",
        "weight": 0.9, "cost": 160.0,
        "weather_conditions": WeatherConditions.FREEZING,
        "crampons": True
    },
    "microspikes": {
        "id": "162c27be-6518-4272-a339-0c892103f1aa",
        "type": "shoes",
        "name": "Traction Microspikes",
        "weight": 0.4, "cost": 70.0,
        "weather_conditions": WeatherConditions.COLD,
        "crampons": False
    },
    "ice-axe": {
        "id": "e671fce6-c79a-481a-a755-3178a8686f44",
        "type": "backpack",
        "name": "General Mountaineering Axe",
        "weight": 0.5, "cost": 100.0, "capacity_liters": 0.0
    },
    "helmet-climbing": {
        "id": "cd086ef3-d51a-4537-bd06-7d07e5be7611",
        "type": "backpack",
        "name": "Climbing Helmet",
        "weight": 0.3, "cost": 80.0, "capacity_liters": 0.0
    },
    "harness": {
        "id": "1aeb23aa-e372-4d11-8828-cd77a145a887",
        "type": "backpack",
        "name": "Alpine Harness",
        "weight": 0.3, "cost": 60.0, "capacity_liters": 0.0
    },
    "rope-60m": {
        "id": "912dedd5-e215-40e6-a663-38009a77ff42",
        "type": "backpack",
        "name": "9.5mm Dry Rope (60m)",
        "weight": 3.5, "cost": 200.0, "capacity_liters": 0.0
    },
     "carabiner-locking": {
        "id": "6f375935-cca4-406c-8faf-d3496f2a2af5",
        "type": "backpack",
        "name": "Locking Carabiner (qty 1)",
        "weight": 0.05, "cost": 10.0, "capacity_liters": 0.0
    },
    "carabiner-wire": {
        "id": "d4fb2abb-a5fe-40c1-ac75-b058c6168e5c",
        "type": "backpack",
        "name": "Wiregate Carabiner (qty 1)",
        "weight": 0.04, "cost": 8.0, "capacity_liters": 0.0
    },
    "avalanche-beacon": {
        "id": "ce12529a-7f0d-4cfa-9967-8bb9ee6f672e",
        "type": "backpack",
        "name": "Avalanche Transceiver",
        "weight": 0.15, "cost": 300.0, "capacity_liters": 0.0
    },
    "avalanche-probe": {
        "id": "198cd5ca-f97c-46e0-a13b-c050452738f6",
        "type": "backpack",
        "name": "Avalanche Probe",
        "weight": 0.4, "cost": 130.0, "capacity_liters": 0.0
    },
    "avalanche-shovel": {
        "id": "24aca1b7-238c-4cf6-9315-fce3ef05af82",
        "type": "backpack",
        "name": "Avalanche Shovel",
        "weight": 0.9, "cost": 120.0, "capacity_liters": 0.0
    },

    # ==================== ELECTRONICS ====================
    "headlamp": {
        "id": "08085afd-864e-40e7-b4fc-48b0c58064e8",
        "type": "backpack",
        "name": "Rechargeable Headlamp",
        "weight": 0.1, "cost": 45.0, "capacity_liters": 0.0
    },
    "power-bank": {
        "id": "36ec386b-173f-40af-a270-91e534789831",
        "type": "backpack",
        "name": "10000mAh Power Bank",
        "weight": 0.2, "cost": 40.0, "capacity_liters": 0.0
    },
    "satellite-messenger": {
        "id": "2daee35b-1e19-425c-9cfc-37bb7290498e",
        "type": "backpack",
        "name": "Satellite Communicator",
        "weight": 0.2, "cost": 350.0, "capacity_liters": 0.0
    },
     "gps-handheld": {
        "id": "d6b724a6-e689-4b02-952f-ea8fb9146ca6",
        "type": "backpack",
        "name": "Handheld GPS Unit",
        "weight": 0.2, "cost": 200.0, "capacity_liters": 0.0
    },
    "altimeter-watch": {
        "id": "22ae91a1-4790-421d-b99c-cc595cd3247f",
        "type": "backpack",
        "name": "Altimeter / Barometer Watch",
        "weight": 0.1, "cost": 80.0, "capacity_liters": 0.0
    },
    "solar-panel-10w": {
        "id": "e28ff8cc-a5a3-412f-a611-68edb75fe8c5",
        "type": "backpack",
        "name": "10W Solar Charger Panel",
        "weight": 0.45, "cost": 120.0, "capacity_liters": 0.0
    },
    "extra-batteries-headlamp": {
        "id": "b0631157-806c-4152-8616-88747e0b95ab",
        "type": "backpack",
        "name": "Spare Batteries for Headlamp",
        "weight": 0.05, "cost": 5.0, "capacity_liters": 0.0
    },

    # ==================== SAFETY / ESSENTIALS ====================
    "first-aid-kit-basic": {
        "id": "2a8e70ce-e03d-4ff9-959c-887cdaa1bd21",
        "type": "backpack",
        "name": "Day Hiker First Aid Kit",
        "weight": 0.3, "cost": 30.0, "capacity_liters": 0.0
    },
    "first-aid-kit-mountain": {
        "id": "a6c03279-4c8d-4021-90d2-0999bac0efa2",
        "type": "backpack",
        "name": "Mountain Medical Kit",
        "weight": 0.8, "cost": 90.0, "capacity_liters": 0.0
    },
    "navigation-map-compass": {
        "id": "e2a125b1-b771-4fc5-bb30-f1db6e5e6ef8",
        "type": "backpack",
        "name": "Topo Map & Compass",
        "weight": 0.1, "cost": 25.0, "capacity_liters": 0.0
    },
    "bug-spray": {
        "id": "80a0185d-dccd-495b-8b8d-af48d38b13bf",
        "type": "backpack",
        "name": "DEET Insect Repellent",
        "weight": 0.1, "cost": 8.0, "capacity_liters": 0.0
    },
    "bear-spray": {
        "id": "c5064445-2d9b-4839-bd27-a51a44deca56",
        "type": "backpack",
        "name": "Bear Defense Spray",
        "weight": 0.3, "cost": 50.0, "capacity_liters": 0.0
    },
    "emergency-bivy": {
        "id": "9ee800d1-74a6-4e61-995b-5eb3e9623e1f",
        "type": "backpack",
        "name": "Emergency Mylar Bivy",
        "weight": 0.1, "cost": 20.0, "capacity_liters": 0.0
    },
    "whistle": {
        "id": "b98025e2-7150-434b-a77f-07ec5cd80e74",
        "type": "backpack",
        "name": "Emergency Whistle",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "multi-tool": {
        "id": "f9577b2d-8b21-4c3b-b238-384f45e8cf43",
        "type": "backpack",
        "name": "Multi-tool (plier-style)",
        "weight": 0.25, "cost": 50.0, "capacity_liters": 0.0
    },
    "sewing-kit": {
        "id": "3f30b605-f2d3-41a2-a8f5-e1db1f102d10",
        "type": "backpack",
        "name": "Mini Sewing / Patch Kit",
        "weight": 0.02, "cost": 5.0, "capacity_liters": 0.0
    },
    "trowel": {
        "id": "673c00c3-a33d-40d6-99b1-7ca9c3c5efe3",
        "type": "backpack",
        "name": "Folding Trowel (for cat-holes)",
        "weight": 0.08, "cost": 15.0, "capacity_liters": 0.0
    },
    "signal-mirror": {
        "id": "1e308698-4bac-4a7a-b814-f156cc477fbd",
        "type": "backpack",
        "name": "Signal Mirror",
        "weight": 0.02, "cost": 8.0, "capacity_liters": 0.0
    },
    "personal-locator-beacon": {
        "id": "eae0a90a-dfbc-4ba6-a876-900bbd2cb39d",
        "type": "backpack",
        "name": "PLB (Personal Locator Beacon)",
        "weight": 0.18, "cost": 250.0, "capacity_liters": 0.0
    }
}