import os
import sys
from datetime import datetime, date

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, Attendance, LeaveRequest, Notification
from config.config import Config

def trigger_auto_attendance(user_id, geofence_name, is_spoofed, current_time):
    """
    Evaluates tracking logs and automatically marks check-in/check-out.
    Triggered upon receiving telemetry logs inside the campus.
    """
    # 1. Verification checks
    if is_spoofed:
        return None # Ignore spoofed locations for attendance
        
    user = db.session.get(User, user_id)
    if not user or user.role not in ['Student', 'Staff']:
        return None # Only students and staff have attendance logs
        
    current_date = current_time.date()
    
    # Verify operational hours (e.g. 8 AM - 4 PM)
    start_hour = Config.COLLEGE_START_HOUR
    end_hour = Config.COLLEGE_END_HOUR
    
    if not (start_hour <= current_time.hour <= end_hour):
        return None
        
    # Check if record already exists for today
    record = Attendance.query.filter_by(user_id=user_id, date=current_date).first()
    
    if not record:
        # If user is outside, we do not mark check-in yet
        if geofence_name == 'Outside':
            return None
            
        # Check for approved leaves
        leave = LeaveRequest.query.filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.start_date <= current_date,
            LeaveRequest.end_date >= current_date,
            LeaveRequest.status == 'Approved'
        ).first()
        
        status = "Present"
        if leave:
            status = "On Leave"
        else:
            # Calculate check-in status
            check_in_limit = datetime.combine(current_date, datetime.min.time()).replace(
                hour=start_hour, minute=Config.LATE_THRESHOLD_MINS
            )
            
            if current_time <= check_in_limit:
                status = "Present"
            elif current_time.hour < 12:
                status = "Late"
            else:
                status = "Half Day"
                
        # Write attendance log
        attendance = Attendance(
            user_id=user_id,
            date=current_date,
            status=status,
            check_in_time=current_time,
            check_out_time=current_time,
            total_hours=0.0
        )
        db.session.add(attendance)
        
        # Send Notification
        notif = Notification(
            user_id=user_id,
            type="Attendance",
            message=f"Attendance auto-marked: You have been marked '{status}' today at {current_time.strftime('%I:%M %p')}."
        )
        db.session.add(notif)
        db.session.commit()
        return status
        
    else:
        # Record exists, update check-out time if currently inside the campus
        if geofence_name != 'Outside':
            record.check_out_time = current_time
            time_diff = current_time - record.check_in_time
            record.total_hours = round(time_diff.total_seconds() / 3600.0, 2)
            
            # If student was marked 'On Leave' but physically arrived, update status
            if record.status == 'On Leave':
                check_in_limit = datetime.combine(current_date, datetime.min.time()).replace(
                    hour=start_hour, minute=Config.LATE_THRESHOLD_MINS
                )
                if record.check_in_time <= check_in_limit:
                    record.status = "Present"
                elif record.check_in_time.hour < 12:
                    record.status = "Late"
                else:
                    record.status = "Half Day"
                    
            db.session.commit()
            
    return record.status

def run_daily_attendance_cleanup(current_date):
    """
    Sweep operation that marks all students and staff who never entered the campus
    during operational hours as either 'Absent' or 'On Leave'.
    Should run at COLLEGE_END_HOUR (4:00 PM).
    """
    # Fetch all students and staff
    users = User.query.filter(User.role.in_(['Student', 'Staff']), User.is_active == True).all()
    marked_absent_count = 0
    marked_leave_count = 0
    
    for user in users:
        # Check if attendance exists
        record = Attendance.query.filter_by(user_id=user.id, date=current_date).first()
        if not record:
            # Check for approved leaves
            leave = LeaveRequest.query.filter(
                LeaveRequest.user_id == user.id,
                LeaveRequest.start_date <= current_date,
                LeaveRequest.end_date >= current_date,
                LeaveRequest.status == 'Approved'
            ).first()
            
            status = "On Leave" if leave else "Absent"
            
            attendance = Attendance(
                user_id=user.id,
                date=current_date,
                status=status,
                check_in_time=None,
                check_out_time=None,
                total_hours=0.0
            )
            db.session.add(attendance)
            
            # Notify user
            notif = Notification(
                user_id=user.id,
                type="Attendance",
                message=f"Attendance marked: You have been marked '{status}' for today ({current_date.strftime('%Y-%m-%d')})."
            )
            db.session.add(notif)
            
            if leave:
                marked_leave_count += 1
            else:
                marked_absent_count += 1
                
    db.session.commit()
    return marked_absent_count, marked_leave_count
