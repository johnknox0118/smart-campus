from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, LocationLog, AuditLog, Notification
from backend.utils.security import role_required, get_client_ip
from backend.utils.geofence import determine_geofence
from backend.utils.spoof_detector import detect_impossible_speed, detect_mock_gps, detect_multi_device
from backend.utils.attendance import trigger_auto_attendance

gps_bp = Blueprint('gps', __name__)

@gps_bp.route('/track', methods=['POST'])
@jwt_required()
def track():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user:
        return jsonify({"error": "Not found", "message": "User not found"}), 404
        
    data = request.get_json() or {}
    
    try:
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        speed = float(data.get('speed', 0.0))
        accuracy = float(data.get('accuracy', 0.0))
        battery = int(data.get('battery', 100))
        mocked = bool(data.get('mocked', False))
    except (ValueError, TypeError):
        return jsonify({"error": "Bad request", "message": "Invalid latitude, longitude, speed, accuracy, or battery type."}), 400
        
    # Validation range checks
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return jsonify({"error": "Bad request", "message": "Coordinates out of bounds."}), 400
        
    current_time = datetime.utcnow()
    
    # 1. Determine Geofence Zone
    geofence_name = determine_geofence(latitude, longitude)
    
    # 2. Run Cybersecurity Spoofing Checks
    is_mocked = detect_mock_gps(accuracy, mocked)
    is_impossible, calc_speed = detect_impossible_speed(user.id, latitude, longitude, current_time, user.role)
    is_multi_device, multi_dist = detect_multi_device(user.id, latitude, longitude, current_time)
    
    is_spoofed = is_mocked or is_impossible or is_multi_device
    
    # Assemble spoofing reason
    reasons = []
    if is_mocked:
        reasons.append("Mock GPS provider/anomalous accuracy detected")
    if is_impossible:
        reasons.append(f"Impossible traversal speed: {calc_speed:.1f} km/h")
    if is_multi_device:
        reasons.append(f"Concurrent uploads from separate devices (distance: {multi_dist:.1f}m)")
        
    spoof_reason = "; ".join(reasons) if is_spoofed else None
    
    # 3. Create Location Log
    location_log = LocationLog(
        user_id=user.id,
        latitude=latitude,
        longitude=longitude,
        speed=speed if speed > 0.0 else calc_speed,
        accuracy=accuracy,
        battery=battery,
        geofence_name=geofence_name,
        is_spoofed=is_spoofed,
        spoof_reason=spoof_reason,
        timestamp=current_time
    )
    db.session.add(location_log)
    
    # 4. Trigger Automatic Attendance Engine
    attendance_status = trigger_auto_attendance(user.id, geofence_name, is_spoofed, current_time)
    
    # 5. Handle Spoofing Alert Actions
    if is_spoofed:
        # Audit Log Event
        audit = AuditLog(
            user_id=user.id,
            event_type="Spoof Attempt",
            details=f"GPS Spoof detected for user '{user.username}'. Reason: {spoof_reason}",
            ip_address=get_client_ip()
        )
        db.session.add(audit)
        
        # Dispatch alert notification to the user themselves (warnings)
        warning_notif = Notification(
            user_id=user.id,
            type="Security",
            message=f"System Warning: Suspicious GPS activity detected on your account. Reason: {spoof_reason}."
        )
        db.session.add(warning_notif)
        
        # Query active Security/Admin users to notify them
        staff_roles = ['Admin', 'Security']
        security_staff = User.query.filter(User.role.in_(staff_roles)).all()
        for staff in security_staff:
            alert_notif = Notification(
                user_id=staff.id,
                type="Emergency",
                message=f"SECURITY ALERT: GPS Spoofing by {user.username} ({user.role}) inside zone {geofence_name}. Reason: {spoof_reason}."
            )
            db.session.add(alert_notif)
            
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "geofence": geofence_name,
        "is_spoofed": is_spoofed,
        "spoof_reason": spoof_reason,
        "attendance_status": attendance_status,
        "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@gps_bp.route('/history/<int:target_user_id>', methods=['GET'])
@jwt_required()
@role_required(['Admin', 'Security', 'Staff'])
def get_history(target_user_id):
    # Check if target user exists
    target = db.session.get(User, target_user_id)
    if not target:
        return jsonify({"error": "Not found", "message": "User not found"}), 404
        
    # Get last 100 tracking entries
    logs = LocationLog.query.filter_by(user_id=target_user_id)\
                            .order_by(LocationLog.timestamp.desc())\
                            .limit(100).all()
                            
    history = []
    for log in logs:
        history.append({
            "id": log.id,
            "latitude": log.latitude,
            "longitude": log.longitude,
            "speed": log.speed,
            "accuracy": log.accuracy,
            "battery": log.battery,
            "geofence_name": log.geofence_name,
            "is_spoofed": log.is_spoofed,
            "spoof_reason": log.spoof_reason,
            "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({
        "username": target.username,
        "role": target.role,
        "history": history
    }), 200

@gps_bp.route('/active', methods=['GET'])
@jwt_required()
@role_required(['Admin', 'Security'])
def get_active_locations():
    """
    Returns the latest valid (non-spoofed) coordinates of all users
    who have uploaded locations in the last 10 minutes.
    """
    ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
    
    # Query distinct active users who posted tracking logs
    active_logs = db.session.query(
        LocationLog.user_id,
        db.func.max(LocationLog.timestamp).label('max_timestamp')
    ).filter(
        LocationLog.timestamp >= ten_mins_ago,
        LocationLog.is_spoofed == False
    ).group_by(LocationLog.user_id).subquery()
    
    latest_locations = LocationLog.query.join(
        active_logs,
        (LocationLog.user_id == active_logs.c.user_id) & 
        (LocationLog.timestamp == active_logs.c.max_timestamp)
    ).all()
    
    active_users_data = []
    for log in latest_locations:
        active_users_data.append({
            "user_id": log.user.id,
            "username": log.user.username,
            "role": log.user.role,
            "latitude": log.latitude,
            "longitude": log.longitude,
            "speed": log.speed,
            "battery": log.battery,
            "geofence_name": log.geofence_name,
            "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({
        "active_count": len(active_users_data),
        "users": active_users_data
    }), 200
