import os
import sys
from datetime import datetime, timedelta

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, LocationLog
from backend.utils.geofence import haversine_distance
from config.config import Config

def detect_impossible_speed(user_id, current_lat, current_lng, current_time, role):
    """
    Detects spoofing by calculating speed between the current and last recorded coordinates.
    Returns: (is_spoofed, calculated_speed_kph)
    """
    # Query last recorded location log (excluding previously identified spoofed points to avoid cascade alerts)
    last_log = LocationLog.query.filter_by(user_id=user_id, is_spoofed=False)\
                                .order_by(LocationLog.timestamp.desc()).first()
    
    if not last_log:
        return False, 0.0
        
    time_diff_seconds = (current_time - last_log.timestamp).total_seconds()
    
    # Check if time diff is negligible (avoid duplicate logs within 1 second throwing division by zero)
    if time_diff_seconds < 1.0:
        return False, 0.0
        
    distance_meters = haversine_distance(
        last_log.latitude, last_log.longitude, 
        current_lat, current_lng
    )
    
    # Calculate speed in km/h
    # (distance in km) / (time in hours)
    speed_kph = (distance_meters / 1000.0) / (time_diff_seconds / 3600.0)
    
    # Define speed thresholds based on user role
    threshold = Config.MAX_VEHICLE_SPEED if role == 'Driver' else Config.MAX_PEDESTRIAN_SPEED
    
    # Ignore tiny GPS jitters (e.g. less than 15 meters) to avoid false positives
    if speed_kph > threshold and distance_meters > 15.0:
        return True, speed_kph
        
    return False, speed_kph

def detect_mock_gps(accuracy, mocked_flag=False):
    """
    Checks for simulated or mocked GPS parameters.
    - Android mock provider flags
    - Suspicious values (e.g., accuracy exactly 0.0 or simulated static accuracy)
    """
    if mocked_flag:
        return True
    if accuracy == 0.0:
        return True
    return False

def detect_multi_device(user_id, current_lat, current_lng, current_time):
    """
    Detects if coordinates are being sent from multiple devices simultaneously.
    If a user uploads locations from two distinct coordinates within 15 seconds 
    and the distance between them is > 100 meters, it triggers a multi-device warning.
    """
    # Look for logs within the last 15 seconds
    recent_logs = LocationLog.query.filter(
        LocationLog.user_id == user_id,
        LocationLog.timestamp >= current_time - timedelta(seconds=15),
        LocationLog.is_spoofed == False
    ).all()
    
    for log in recent_logs:
        dist = haversine_distance(log.latitude, log.longitude, current_lat, current_lng)
        # If logs are within 15s and distance > 100m, it's mathematically impossible for 1 physical device
        if dist > 100.0:
            return True, dist
            
    return False, 0.0
