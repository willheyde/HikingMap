
MIN_DISTANCE_M = 1000   
MIN_GAIN_M = 0          

def is_valid_hike(distance_m, elevation_gain_m):
    return (
        distance_m >= MIN_DISTANCE_M and
        elevation_gain_m >= MIN_GAIN_M
    )