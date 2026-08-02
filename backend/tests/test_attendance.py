import os
import sys
import pytest
from datetime import datetime, date, timedelta

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, Attendance, LeaveRequest, Notification
from backend.utils.attendance import trigger_auto_attendance, run_daily_attendance_cleanup
from config.config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

@pytest.fixture
def app_ctx():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        
        # Setup mock Student and Staff
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt(app)
        
        student = User(
            username="student_att",
            password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
            email="student_att@test.com",
            role="Student",
            is_active=True
        )
        
        staff = User(
            username="staff_att",
            password_hash=bcrypt.generate_password_hash("staff123").decode('utf-8'),
            email="staff_att@test.com",
            role="Staff",
            is_active=True
        )
        
        db.session.add_all([student, staff])
        db.session.commit()
        
        yield app

def test_attendance_outside_campus(app_ctx):
    """Test that coordinates outside the campus do not trigger check-in"""
    student = User.query.filter_by(username="student_att").first()
    
    # 8:15 AM check-in, but outside campus bounds
    current_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=15)
    status = trigger_auto_attendance(student.id, "Outside", False, current_time)
    
    assert status is None
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record is None

def test_attendance_present_early(app_ctx):
    """Test standard Present marking (before 8:30 AM)"""
    student = User.query.filter_by(username="student_att").first()
    
    # 8:15 AM inside campus block
    current_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=15)
    status = trigger_auto_attendance(student.id, "Library", False, current_time)
    
    assert status == "Present"
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record is not None
    assert record.status == "Present"
    assert record.check_in_time == current_time
    
    # Check notification dispatch
    notif = Notification.query.filter_by(user_id=student.id, type="Attendance").first()
    assert notif is not None
    assert "marked 'Present'" in notif.message

def test_attendance_late(app_ctx):
    """Test Late marking (8:31 AM to 12:00 PM)"""
    student = User.query.filter_by(username="student_att").first()
    
    # 9:15 AM check-in inside campus
    current_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=9, minute=15)
    status = trigger_auto_attendance(student.id, "Academic Block", False, current_time)
    
    assert status == "Late"
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record.status == "Late"

def test_attendance_half_day(app_ctx):
    """Test Half Day marking (after 12:00 PM)"""
    student = User.query.filter_by(username="student_att").first()
    
    # 1:15 PM check-in inside campus
    current_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=13, minute=15)
    status = trigger_auto_attendance(student.id, "Academic Block", False, current_time)
    
    assert status == "Half Day"
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record.status == "Half Day"

def test_attendance_on_leave_override(app_ctx):
    """Test that a student with an approved leave gets marked 'On Leave' even if they enter campus"""
    student = User.query.filter_by(username="student_att").first()
    
    # Create approved leave request for today
    leave = LeaveRequest(
        user_id=student.id,
        start_date=date.today(),
        end_date=date.today(),
        reason="Medical",
        status="Approved"
    )
    db.session.add(leave)
    db.session.commit()
    
    current_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=15)
    status = trigger_auto_attendance(student.id, "Hostel", False, current_time)
    
    assert status == "On Leave"
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record.status == "On Leave"

def test_attendance_checkout_update(app_ctx):
    """Test that subsequent logs inside campus update the checkout time and total hours"""
    student = User.query.filter_by(username="student_att").first()
    
    # 1. First log at 8:00 AM (Check-in)
    in_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=0)
    trigger_auto_attendance(student.id, "Library", False, in_time)
    
    # 2. Second log at 11:30 AM (Check-out update)
    out_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=11, minute=30)
    status = trigger_auto_attendance(student.id, "Academic Block", False, out_time)
    
    record = Attendance.query.filter_by(user_id=student.id, date=date.today()).first()
    assert record.check_out_time == out_time
    assert record.total_hours == 3.5  # 3.5 hours difference

def test_daily_attendance_cleanup(app_ctx):
    """Test the daily absenteeism sweep logic at the end of the day"""
    student = User.query.filter_by(username="student_att").first()
    staff = User.query.filter_by(username="staff_att").first()
    
    # Case: student did check-in (Present)
    in_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=15)
    trigger_auto_attendance(student.id, "Library", False, in_time)
    
    # Case: staff has approved leave for today
    leave = LeaveRequest(
        user_id=staff.id,
        start_date=date.today(),
        end_date=date.today(),
        reason="Personal",
        status="Approved"
    )
    db.session.add(leave)
    db.session.commit()
    
    # Run cleanup sweep
    marked_absent, marked_leave = run_daily_attendance_cleanup(date.today())
    
    # Verify:
    # 1. 0 absent since student was present, staff was on leave
    # 2. staff marked 'On Leave'
    assert marked_leave == 1
    
    staff_record = Attendance.query.filter_by(user_id=staff.id, date=date.today()).first()
    assert staff_record is not None
    assert staff_record.status == "On Leave"
    assert staff_record.check_in_time is None

@pytest.fixture
def client_with_roles():
    app = create_app(TestConfig)
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Setup users with roles
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt(app)
            
            student = User(
                username="student_test",
                password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
                email="student_test@test.com",
                role="Student",
                is_active=True
            )
            
            staff = User(
                username="staff_test",
                password_hash=bcrypt.generate_password_hash("staff123").decode('utf-8'),
                email="staff_test@test.com",
                role="Staff",
                is_active=True
            )
            
            db.session.add_all([student, staff])
            db.session.commit()
            
            # Generate JWT tokens
            student_resp = client.post('/api/auth/login', json={"username": "student_test", "password": "student123"})
            student_token = student_resp.get_json()["access_token"]
            
            staff_resp = client.post('/api/auth/login', json={"username": "staff_test", "password": "staff123"})
            staff_token = staff_resp.get_json()["access_token"]
            
        yield client, student_token, staff_token

def test_get_students_attendance_as_staff(client_with_roles):
    """Test retrieving student attendance list as a staff member"""
    client, _, staff_token = client_with_roles
    
    response = client.get('/api/attendance/students', headers={"Authorization": f"Bearer {staff_token}"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "student_test"
    assert data["students"][0]["attendance_today"]["status"] == "Not Marked"

def test_mark_attendance_as_staff(client_with_roles):
    """Test manually marking student attendance as present/late/absent by staff"""
    client, _, staff_token = client_with_roles
    
    # 1. Fetch student ID
    response = client.get('/api/attendance/students', headers={"Authorization": f"Bearer {staff_token}"})
    student_id = response.get_json()["students"][0]["student_id"]
    
    # 2. Mark student as Late
    mark_response = client.post('/api/attendance/mark', json={
        "student_id": student_id,
        "status": "Late"
    }, headers={"Authorization": f"Bearer {staff_token}"})
    
    assert mark_response.status_code == 200
    assert mark_response.get_json()["success"] is True
    
    # 3. Verify status changed
    verify_resp = client.get('/api/attendance/students', headers={"Authorization": f"Bearer {staff_token}"})
    student_data = verify_resp.get_json()["students"][0]
    assert student_data["attendance_today"]["status"] == "Late"

def test_unauthorized_attendance_actions(client_with_roles):
    """Verify that a student cannot fetch student list or mark attendance manually"""
    client, student_token, _ = client_with_roles
    
    # 1. Try to get student list
    get_resp = client.get('/api/attendance/students', headers={"Authorization": f"Bearer {student_token}"})
    assert get_resp.status_code == 403
    
    # 2. Try to mark attendance
    mark_resp = client.post('/api/attendance/mark', json={
        "student_id": 1,
        "status": "Present"
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert mark_resp.status_code == 403
