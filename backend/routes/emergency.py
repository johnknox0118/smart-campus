from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, EmergencyAlert, Notification, AuditLog
from backend.utils.security import role_required, get_client_ip

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route('/sos', methods=['POST'])
@jwt_required()
def trigger_sos():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user:
        return jsonify({"error": "Not found", "message": "User not found"}), 404
        
    data = request.get_json() or {}
    
    try:
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
    except (ValueError, TypeError):
        return jsonify({"error": "Bad request", "message": "Latitude and Longitude are required to trigger SOS."}), 400
        
    # Log emergency alert
    alert = EmergencyAlert(
        user_id=user.id,
        latitude=latitude,
        longitude=longitude,
        status="Active",
        created_at=datetime.utcnow()
    )
    db.session.add(alert)
    db.session.commit()
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        event_type="SOS Alert",
        details=f"User '{user.username}' triggered SOS from ({latitude}, {longitude})",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    
    # Broadcast notification to all Admin & Security users
    staff_roles = ['Admin', 'Security']
    security_staff = User.query.filter(User.role.in_(staff_roles)).all()
    
    for staff in security_staff:
        sos_notif = Notification(
            user_id=staff.id,
            type="Emergency",
            message=f"CRITICAL SOS: {user.username} ({user.role}) is in distress! Location: ({latitude}, {longitude})."
        )
        db.session.add(sos_notif)
        
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "Emergency SOS triggered! Dispatching security response team.",
        "alert_id": alert.id
    }), 201

@emergency_bp.route('/active', methods=['GET'])
@jwt_required()
@role_required(['Admin', 'Security'])
def active_emergencies():
    alerts = EmergencyAlert.query.filter_by(status="Active")\
                                 .order_by(EmergencyAlert.created_at.desc()).all()
                                 
    active = []
    for alert in alerts:
        active.append({
            "id": alert.id,
            "username": alert.reporter.username,
            "role": alert.reporter.role,
            "phone": alert.reporter.email, # email/contact info
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "created_at": alert.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({"alerts": active}), 200

@emergency_bp.route('/resolve/<int:alert_id>', methods=['POST'])
@jwt_required()
@role_required(['Admin', 'Security'])
def resolve_emergency(alert_id):
    user_id = get_jwt_identity()
    resolver = db.session.get(User, int(user_id))
    
    alert = db.session.get(EmergencyAlert, alert_id)
    if not alert:
        return jsonify({"error": "Not found", "message": "Emergency alert not found"}), 404
        
    if alert.status != "Active":
        return jsonify({"error": "Conflict", "message": "Alert is already resolved."}), 409
        
    alert.status = "Resolved"
    alert.resolved_by = resolver.id
    alert.resolved_at = datetime.utcnow()
    
    # Audit log
    audit = AuditLog(
        user_id=resolver.id,
        event_type="SOS Resolved",
        details=f"Emergency SOS {alert_id} (reported by {alert.reporter.username}) was resolved by '{resolver.username}'",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        "message": "Emergency SOS marked as resolved."
    }), 200
