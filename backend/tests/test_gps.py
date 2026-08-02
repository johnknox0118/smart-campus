import os
import sys
import pytest
from datetime import datetime, timedelta

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, LocationLog
from config.config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

@pytest.fixture
def client_with_auth():
    app = create_app(TestConfig)
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Setup users
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt(app)
            
            student = User(
                username="student_gps",
                password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
                email="student_gps@test.com",
                role="Student",
                is_active=True
            )
            
            admin = User(
                username="admin_gps",
                password_hash=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                email="admin_gps@test.com",
                role="Admin",
                is_active=True
            )
            
            db.session.add_all([student, admin])
            db.session.commit()
            
            # Get tokens
            student_resp = client.post('/api/auth/login', json={"username": "student_gps", "password": "student123"})
            student_token = student_resp.get_json()["access_token"]
            
            admin_resp = client.post('/api/auth/login', json={"username": "admin_gps", "password": "admin123"})
            admin_token = admin_resp.get_json()["access_token"]
            
        yield client, student_token, admin_token

def test_track_inside_campus(client_with_auth):
    """Test sending a valid GPS coordinate within the campus boundary"""
    client, token, _ = client_with_auth
    
    # Coordinate inside Entire Campus but outside specific sub-blocks
    response = client.post('/api/gps/track', json={
        "latitude": 13.0940,
        "longitude": 79.9730,
        "speed": 1.2,
        "accuracy": 10.0,
        "battery": 85,
        "mocked": False
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["geofence"] == "Entire Campus"
    assert data["is_spoofed"] is False

def test_track_inside_library(client_with_auth):
    """Test sending a valid GPS coordinate inside the Library sector"""
    client, token, _ = client_with_auth
    
    # Library center is 13.0848, 79.9968 (Radius 40m)
    response = client.post('/api/gps/track', json={
        "latitude": 13.092300,
        "longitude": 79.973900,
        "speed": 0.0,
        "accuracy": 5.0,
        "battery": 90
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["geofence"] == "Library"
    assert data["is_spoofed"] is False

def test_track_outside_campus(client_with_auth):
    """Test sending coordinates representing a user outside the campus bounds"""
    client, token, _ = client_with_auth
    
    # Poonamallee town coords (far from campus center)
    response = client.post('/api/gps/track', json={
        "latitude": 13.0450,
        "longitude": 80.0210,
        "speed": 5.0,
        "accuracy": 12.0,
        "battery": 60
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["geofence"] == "Outside"
    assert data["is_spoofed"] is False

def test_spoof_detection_mocked(client_with_auth):
    """Test that explicit client mock indicators trigger spoofing logs"""
    client, token, _ = client_with_auth
    
    response = client.post('/api/gps/track', json={
        "latitude": 13.092000,
        "longitude": 79.973500,
        "speed": 0.0,
        "accuracy": 10.0,
        "battery": 99,
        "mocked": True
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["is_spoofed"] is True
    assert "Mock GPS" in data["spoof_reason"]

def test_spoof_detection_impossible_speed(client_with_auth):
    """Test impossible traversal speeds logging"""
    client, token, _ = client_with_auth
    
    # 1. Inject a past log entry directly into the database backdated to 45 seconds ago
    with client.application.app_context():
        # Get the student user
        student = User.query.filter_by(username="student_gps").first()
        past_log = LocationLog(
            user_id=student.id,
            latitude=13.092300,
            longitude=79.973900,
            speed=0.0,
            accuracy=10.0,
            battery=99,
            geofence_name="Library",
            is_spoofed=False,
            timestamp=datetime.utcnow() - timedelta(seconds=45)
        )
        db.session.add(past_log)
        db.session.commit()
        
    # 3. Post a coordinate 2 kilometers away immediately
    # Dist = ~2000m traversed in 5s => speed = ~1440 km/h
    response_impossible = client.post('/api/gps/track', json={
        "latitude": 13.1000,
        "longitude": 79.9100,
        "speed": 1.2,
        "accuracy": 10.0,
        "battery": 98
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response_impossible.status_code == 200
    data = response_impossible.get_json()
    assert data["is_spoofed"] is True
    assert "Impossible traversal speed" in data["spoof_reason"]

def test_spoof_detection_multi_device(client_with_auth):
    """Test concurrent uploads from separate devices for same account"""
    client, token, _ = client_with_auth
    
    # 1. Post position 1
    response1 = client.post('/api/gps/track', json={
        "latitude": 13.092000,
        "longitude": 79.973500,
        "speed": 0.0,
        "accuracy": 10.0,
        "battery": 99
    }, headers={"Authorization": f"Bearer {token}"})
    assert response1.status_code == 200
    
    # 2. Immediately post position 2 (e.g. 500 meters away)
    response2 = client.post('/api/gps/track', json={
        "latitude": 13.0920,
        "longitude": 79.9755,
        "speed": 0.0,
        "accuracy": 10.0,
        "battery": 99
    }, headers={"Authorization": f"Bearer {token}"})
    
    assert response2.status_code == 200
    data = response2.get_json()
    assert data["is_spoofed"] is True
    assert "Concurrent uploads" in data["spoof_reason"]

def test_active_locations_and_history(client_with_auth):
    """Test retrieving history and active tracking lists"""
    client, token, admin_token = client_with_auth
    
    # Get history for student
    # First find student ID
    profile_resp = client.get('/api/auth/profile', headers={"Authorization": f"Bearer {token}"})
    student_id = profile_resp.get_json()["id"]
    
    history_resp = client.get(f'/api/gps/history/{student_id}', headers={"Authorization": f"Bearer {admin_token}"})
    assert history_resp.status_code == 200
    assert "history" in history_resp.get_json()
    
    active_resp = client.get('/api/gps/active', headers={"Authorization": f"Bearer {admin_token}"})
    assert active_resp.status_code == 200
    assert "users" in active_resp.get_json()
