from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import date, datetime
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, Attendance, Notification
from backend.utils.security import role_required

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/students', methods=['GET'])
@jwt_required()
@role_required(['Admin', 'Staff'])
def get_students_attendance():
    """
    Returns a list of all students with their today's geofence status (last seen)
    and their attendance record for today.
    """
    today = date.today()
    
    current_user_id = get_jwt_identity()
    current_user = db.session.get(User, int(current_user_id))
    
    if current_user.role == 'Staff':
        students = User.query.filter_by(role='Student', department_id=current_user.department_id, is_active=True).all()
    else:
        students = User.query.filter_by(role='Student', is_active=True).all()
    
    result = []
    for student in students:
        # Get today's attendance record
        att_record = Attendance.query.filter_by(user_id=student.id, date=today).first()
        
        # Get last seen location to see geofence status
        from backend.models import LocationLog
        last_log = LocationLog.query.filter_by(user_id=student.id).order_by(LocationLog.timestamp.desc()).first()
        current_zone = last_log.geofence_name if last_log else "Outside"
        
        result.append({
            "student_id": student.id,
            "username": student.username,
            "name": f"{student.username.capitalize()} (Student)",
            "department": student.department.name if student.department else "General",
            "year": student.year or "",
            "section": student.section or "",
            "last_seen_geofence": current_zone,
            "attendance_today": {
                "status": att_record.status if att_record else "Not Marked",
                "check_in": att_record.check_in_time.strftime('%I:%M %p') if (att_record and att_record.check_in_time) else "-",
                "check_out": att_record.check_out_time.strftime('%I:%M %p') if (att_record and att_record.check_out_time) else "-",
                "total_hours": att_record.total_hours if att_record else 0.0
            }
        })
        
    return jsonify({"success": True, "students": result})

@attendance_bp.route('/mark', methods=['POST'])
@jwt_required()
@role_required(['Admin', 'Staff'])
def mark_attendance():
    """
    Manually creates or updates a student's attendance record for today.
    """
    data = request.get_json() or {}
    student_id = data.get('student_id')
    status = data.get('status') # 'Present', 'Absent', 'Late', 'On Leave'
    
    if not student_id or not status:
        return jsonify({"error": "Bad Request", "message": "Missing student_id or status"}), 400
        
    if status not in ['Present', 'Absent', 'Late', 'On Leave']:
        return jsonify({"error": "Bad Request", "message": "Invalid status value"}), 400
        
    student = db.session.get(User, int(student_id))
    if not student or student.role != 'Student':
        return jsonify({"error": "Not Found", "message": "Student not found"}), 404
        
    today = date.today()
    current_time = datetime.utcnow()
    
    # Query today's attendance record
    att_record = Attendance.query.filter_by(user_id=student.id, date=today).first()
    
    if not att_record:
        # Create a new attendance record
        att_record = Attendance(
            user_id=student.id,
            date=today,
            status=status,
            check_in_time=current_time if status in ['Present', 'Late'] else None,
            check_out_time=current_time if status in ['Present', 'Late'] else None,
            total_hours=0.0
        )
        db.session.add(att_record)
    else:
        # Update existing record
        att_record.status = status
        if status in ['Present', 'Late']:
            if not att_record.check_in_time:
                att_record.check_in_time = current_time
            att_record.check_out_time = current_time
        else:
            att_record.check_in_time = None
            att_record.check_out_time = None
            att_record.total_hours = 0.0
            
    # Send Notification to the student
    notif = Notification(
        user_id=student.id,
        type="Attendance",
        message=f"Attendance manually marked/updated: Marked '{status}' for today by Staff/Admin."
    )
    db.session.add(notif)
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": f"Successfully marked attendance as '{status}' for {student.username}."
    })
