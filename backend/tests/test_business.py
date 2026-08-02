import os
import sys
import pytest
from datetime import datetime, date, timedelta

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, Bus, BusLocationLog, LeaveRequest, EmergencyAlert, Notification
from config.config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

@pytest.fixture
def test_setup():
    app = create_app(TestConfig)
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt(app)
            
            # Setup users
            admin = User(
                username="admin_biz",
                password_hash=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                email="admin_biz@test.com",
                role="Admin",
                is_active=True
            )
            
            student = User(
                username="student_biz",
                password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
                email="student_biz@test.com",
                role="Student",
                is_active=True
            )
            
            driver = User(
                username="driver_biz",
                password_hash=bcrypt.generate_password_hash("driver123").decode('utf-8'),
                email="driver_biz@test.com",
                role="Driver",
                is_active=True
            )
            
            security = User(
                username="security_biz",
                password_hash=bcrypt.generate_password_hash("security123").decode('utf-8'),
                email="security_biz@test.com",
                role="Security",
                is_active=True
            )
            
            db.session.add_all([admin, student, driver, security])
            db.session.commit()
            
            # Setup a Bus
            bus = Bus(
                bus_number="TEST-BUS-01",
                route_name="Route 1 to Campus",
                driver_id=driver.id,
                capacity=40,
                status="Inactive"
            )
            db.session.add(bus)
            db.session.commit()
            
            # Get login tokens
            admin_token = client.post('/api/auth/login', json={"username": "admin_biz", "password": "admin123"}).get_json()["access_token"]
            student_token = client.post('/api/auth/login', json={"username": "student_biz", "password": "student123"}).get_json()["access_token"]
            driver_token = client.post('/api/auth/login', json={"username": "driver_biz", "password": "driver123"}).get_json()["access_token"]
            security_token = client.post('/api/auth/login', json={"username": "security_biz", "password": "security123"}).get_json()["access_token"]
            
        yield client, {
            "Admin": admin_token,
            "Student": student_token,
            "Driver": driver_token,
            "Security": security_token
        }

def test_bus_tracking_workflow(test_setup):
    """Test updating and reading bus telemetry logs"""
    client, tokens = test_setup
    
    # 1. Update bus coordinates (Driver)
    response_loc = client.post('/api/bus/location', json={
        "latitude": 13.0800,
        "longitude": 79.9700,
        "speed": 45.5,
        "eta_mins": 10,
        "next_stop": "Campus Main Entrance"
    }, headers={"Authorization": f"Bearer {tokens['Driver']}"})
    
    assert response_loc.status_code == 200
    assert response_loc.get_json()["status"] == "success"
    
    # 2. View bus status list (Student)
    response_status = client.get('/api/bus/status', headers={"Authorization": f"Bearer {tokens['Student']}"})
    assert response_status.status_code == 200
    buses_list = response_status.get_json()["buses"]
    assert len(buses_list) == 1
    assert buses_list[0]["bus_number"] == "TEST-BUS-01"
    assert buses_list[0]["latitude"] == 13.0800
    assert buses_list[0]["speed"] == 45.5
    assert buses_list[0]["status"] == "Active"  # status toggled automatically

def test_leave_workflow(test_setup):
    """Test leave request, pending list, and approval steps"""
    client, tokens = test_setup
    
    # 1. Request leave (Student)
    response_req = client.post('/api/leave/request', json={
        "start_date": "2026-07-20",
        "end_date": "2026-07-22",
        "reason": "Family function"
    }, headers={"Authorization": f"Bearer {tokens['Student']}"})
    
    assert response_req.status_code == 201
    leave_id = response_req.get_json()["leave_id"]
    
    # 2. View pending leaves (Admin)
    response_pending = client.get('/api/leave/pending', headers={"Authorization": f"Bearer {tokens['Admin']}"})
    assert response_pending.status_code == 200
    pending_list = response_pending.get_json()["pending"]
    assert len(pending_list) == 1
    assert pending_list[0]["id"] == leave_id
    assert pending_list[0]["username"] == "student_biz"
    
    # 3. Approve leave (Admin)
    response_app = client.post(f'/api/leave/approve/{leave_id}', json={
        "status": "Approved"
    }, headers={"Authorization": f"Bearer {tokens['Admin']}"})
    assert response_app.status_code == 200
    
    # Check leave status is updated
    with client.application.app_context():
        leave_obj = db.session.get(LeaveRequest, leave_id)
        assert leave_obj.status == "Approved"

def test_emergency_sos_workflow(test_setup):
    """Test SOS broadcast trigger and resolution lifecycle"""
    client, tokens = test_setup
    
    # 1. Trigger SOS (Student)
    response_sos = client.post('/api/emergency/sos', json={
        "latitude": 13.092233,
        "longitude": 79.973900
    }, headers={"Authorization": f"Bearer {tokens['Student']}"})
    
    assert response_sos.status_code == 201
    alert_id = response_sos.get_json()["alert_id"]
    
    # Check notifications dispatched to Security
    unread_resp = client.get('/api/notifications/unread', headers={"Authorization": f"Bearer {tokens['Security']}"})
    assert unread_resp.status_code == 200
    notifs = unread_resp.get_json()["notifications"]
    assert len(notifs) >= 1
    assert "CRITICAL SOS" in notifs[0]["message"]
    
    # 2. View active SOS logs (Security)
    active_resp = client.get('/api/emergency/active', headers={"Authorization": f"Bearer {tokens['Security']}"})
    assert active_resp.status_code == 200
    active_list = active_resp.get_json()["alerts"]
    assert len(active_list) == 1
    assert active_list[0]["id"] == alert_id
    
    # 3. Resolve SOS (Security)
    resolve_resp = client.post(f'/api/emergency/resolve/{alert_id}', headers={"Authorization": f"Bearer {tokens['Security']}"})
    assert resolve_resp.status_code == 200
    
    with client.application.app_context():
        alert_obj = db.session.get(EmergencyAlert, alert_id)
        assert alert_obj.status == "Resolved"

def test_dashboard_analytics(test_setup):
    """Test requesting dashboard metrics for Chart.js and stat cards"""
    client, tokens = test_setup
    
    # Get dashboard stats (Admin)
    response = client.get('/api/analytics/dashboard', headers={"Authorization": f"Bearer {tokens['Admin']}"})
    assert response.status_code == 200
    data = response.get_json()
    assert "cards" in data
    assert "charts" in data
    assert "students_present" in data["cards"]
    assert "monthly_trends" in data["charts"]
