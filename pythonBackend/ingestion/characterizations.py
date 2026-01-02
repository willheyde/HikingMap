import math
from PyObjects.Hike import DifficultyLevel # Ensure this path exists in your project

SAC_SCALE_MAP = {
    "hiking": DifficultyLevel.EASY,
    "mountain_hiking": DifficultyLevel.MODERATE,
    "demanding_mountain_hiking": DifficultyLevel.DIFFICULT,
    "alpine_hiking": DifficultyLevel.EXPERT,
    "demanding_alpine_hiking": DifficultyLevel.EXPERT,
}

def infer_difficulty(tags: dict) -> DifficultyLevel:
    sac = tags.get("sac_scale")
    return SAC_SCALE_MAP.get(sac, DifficultyLevel.MODERATE)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def compute_metrics(points):
    distance = 0
    gain = 0
    for i in range(1, len(points)):
        p1, p2 = points[i-1], points[i]
        distance += haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        
        # Only calculate gain if we have valid elevation data
        if p2["ele"] > p1["ele"] and p1["ele"] > 0:
            gain += (p2["ele"] - p1["ele"])
            
    return distance, gain

def infer_season(tags: dict):
    if tags.get("seasonal") == "yes":
        return 5, 9
    if tags.get("winter_service") == "yes":
        return 1, 12
    return 4, 10

def infer_required_gear(tags: dict, difficulty):
    gear = []
    if tags.get("surface") in {"rock", "scree"}:
        gear.append("sturdy_boots")
    if tags.get("sac_scale") in {"alpine_hiking", "demanding_alpine_hiking"}:
        gear.extend(["helmet", "navigation_tools"])
    if tags.get("winter_service") == "no":
        gear.append("seasonal_awareness")
    return list(set(gear))

def infer_region(lat, lon):
    if 35 <= lat <= 40 and -85 <= lon <= -75:
        return "Appalachian Mountains"
    if 45 <= lat <= 48 and 6 <= lon <= 10:
        return "Swiss Alps"
    return "Unknown Region"