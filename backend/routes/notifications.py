from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, Notification

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/unread', methods=['GET'])
@jwt_required()
def get_unread_notifications():
    user_id = get_jwt_identity()
    
    notifications = Notification.query.filter_by(user_id=int(user_id), is_read=False)\
                                      .order_by(Notification.created_at.desc()).all()
                                      
    unread = []
    for notif in notifications:
        unread.append({
            "id": notif.id,
            "type": notif.type,
            "message": notif.message,
            "created_at": notif.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({"notifications": unread}), 200

@notifications_bp.route('/read/<int:notif_id>', methods=['POST'])
@jwt_required()
def mark_as_read(notif_id):
    user_id = get_jwt_identity()
    
    notif = db.session.get(Notification, notif_id)
    if not notif:
        return jsonify({"error": "Not found", "message": "Notification not found"}), 404
        
    # Security check: User can only mark their own notifications as read
    if notif.user_id != int(user_id):
        return jsonify({"error": "Forbidden", "message": "Unauthorized action."}), 403
        
    notif.is_read = True
    db.session.commit()
    
    return jsonify({"message": "Notification marked as read"}), 200
