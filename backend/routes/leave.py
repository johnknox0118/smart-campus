from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, LeaveRequest, Notification, AuditLog
from backend.utils.security import role_required, get_client_ip

leave_bp = Blueprint('leave', __name__)

@leave_bp.route('/request', methods=['POST'])
@jwt_required()
def request_leave():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user or user.role not in ['Student', 'Staff']:
        return jsonify({"error": "Forbidden", "message": "Only students and staff can request leaves."}), 403
        
    data = request.get_json() or {}
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    reason = data.get('reason')
    
    if not start_date_str or not end_date_str or not reason:
        return jsonify({"error": "Bad request", "message": "start_date, end_date, and reason are required"}), 400
        
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Bad request", "message": "Dates must be in format YYYY-MM-DD"}), 400
        
    if start_date > end_date:
        return jsonify({"error": "Bad request", "message": "start_date cannot be after end_date"}), 400
        
    leave_request = LeaveRequest(
        user_id=user.id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status="Pending"
    )
    db.session.add(leave_request)
    db.session.commit()
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        event_type="Leave Request",
        details=f"User '{user.username}' requested leave from {start_date_str} to {end_date_str}",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        "message": "Leave request submitted successfully",
        "leave_id": leave_request.id
    }), 201

@leave_bp.route('/history', methods=['GET'])
@jwt_required()
def leave_history():
    user_id = get_jwt_identity()
    
    leaves = LeaveRequest.query.filter_by(user_id=int(user_id))\
                              .order_by(LeaveRequest.created_at.desc()).all()
                              
    history = []
    for leave in leaves:
        history.append({
            "id": leave.id,
            "start_date": leave.start_date.strftime('%Y-%m-%d'),
            "end_date": leave.end_date.strftime('%Y-%m-%d'),
            "reason": leave.reason,
            "status": leave.status,
            "created_at": leave.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({"history": history}), 200

@leave_bp.route('/pending', methods=['GET'])
@jwt_required()
@role_required(['Staff', 'Admin'])
def pending_leaves():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    
    # Staff can only view leaves of students in their department (if they have one)
    # Admin can view all leaves
    if user.role == 'Admin' or not user.department_id:
        pending_list = LeaveRequest.query.filter_by(status="Pending")\
                                         .order_by(LeaveRequest.created_at.asc()).all()
    else:
        # Filter leaves where student belongs to same department as staff
        pending_list = LeaveRequest.query.join(User, LeaveRequest.user_id == User.id)\
                                         .filter(User.department_id == user.department_id, LeaveRequest.status == "Pending")\
                                         .order_by(LeaveRequest.created_at.asc()).all()
                                         
    pending = []
    for leave in pending_list:
        pending.append({
            "id": leave.id,
            "username": leave.user.username,
            "role": leave.user.role,
            "department": leave.user.department.name if leave.user.department else None,
            "start_date": leave.start_date.strftime('%Y-%m-%d'),
            "end_date": leave.end_date.strftime('%Y-%m-%d'),
            "reason": leave.reason,
            "created_at": leave.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify({"pending": pending}), 200

@leave_bp.route('/approve/<int:request_id>', methods=['POST'])
@jwt_required()
@role_required(['Staff', 'Admin'])
def approve_leave(request_id):
    user_id = get_jwt_identity()
    approver = db.session.get(User, int(user_id))
    
    leave = db.session.get(LeaveRequest, request_id)
    if not leave:
        return jsonify({"error": "Not found", "message": "Leave request not found"}), 404
        
    if leave.status != "Pending":
        return jsonify({"error": "Conflict", "message": f"Leave request is already {leave.status}."}), 409
        
    data = request.get_json() or {}
    decision = data.get('status')  # Approved, Rejected
    
    if decision not in ['Approved', 'Rejected']:
        return jsonify({"error": "Bad request", "message": "Status must be 'Approved' or 'Rejected'"}), 400
        
    # Check if staff belongs to same department as student (for non-admin)
    if approver.role != 'Admin' and approver.department_id != leave.user.department_id:
        return jsonify({"error": "Forbidden", "message": "You can only approve leaves within your department."}), 403
        
    leave.status = decision
    leave.approved_by = approver.id
    db.session.commit()
    
    # Notify user
    notif = Notification(
        user_id=leave.user_id,
        type="Leave",
        message=f"Leave request update: Your leave starting {leave.start_date.strftime('%Y-%m-%d')} has been {decision}."
    )
    db.session.add(notif)
    
    # Audit log
    audit = AuditLog(
        user_id=approver.id,
        event_type="Leave Approval",
        details=f"Leave request {request_id} for user '{leave.user.username}' was {decision} by '{approver.username}'",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        "message": f"Leave request successfully marked as {decision}",
        "leave_id": leave.id
    }), 200
