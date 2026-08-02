import math
import os
import sys

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in meters.
    """
    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula 
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters.
    return c * r

def determine_geofence(lat, lng):
    """
    Determines which geofence zone the user is inside.
    Checks sub-zones first (Library, Academic Block, Hostel, Sports Ground, Parking, Bus Parking)
    and then checks the overall Entire Campus boundary.
    Returns the name of the geofence, or 'Outside' if outside the campus.
    """
    geofences = Config.GEOFENCES
    
    # Check sub-zones first
    sub_zones = [k for k in geofences.keys() if k != "Entire Campus"]
    
    for zone in sub_zones:
        config = geofences[zone]
        if config["type"] == "circle":
            dist = haversine_distance(lat, lng, config["lat"], config["lng"])
            if dist <= config["radius"]:
                return zone
                
    # If not in any sub-zone, check if in Entire Campus
    campus_config = geofences.get("Entire Campus")
    if campus_config:
        dist = haversine_distance(lat, lng, campus_config["lat"], campus_config["lng"])
        if dist <= campus_config["radius"]:
            return "Entire Campus"
            
    return "Outside"
