import os
import sys
import pytest
import tempfile
from datetime import datetime

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, Department, ClassRoom
from config.config import Config

class TestConfig(Config):
    TESTING = True
    # Use in-memory SQLite database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    ACCOUNT_LOCKOUT_LIMIT = 3  # Lower limit for testing lockout
    LOCKOUT_DURATION_MINS = 5

@pytest.fixture
def client():
    app = create_app(TestConfig)
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Setup seed data
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt(app)
            
            admin = User(
                username="admin_test",
                password_hash=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                email="admin_test@test.com",
                role="Admin",
                is_active=True
            )
            
            student = User(
                username="student_test",
                password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
                email="student_test@test.com",
                role="Student",
                is_active=True
            )
            
            db.session.add_all([admin, student])
            db.session.commit()
            
        yield client

def test_login_success(client):
    """Test login with valid credentials"""
    response = client.post('/api/auth/login', json={
        "username": "admin_test",
        "password": "admin123"
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert "access_token" in json_data
    assert "refresh_token" in json_data
    assert json_data["user"]["role"] == "Admin"

def test_login_invalid_password(client):
    """Test login with incorrect password"""
    response = client.post('/api/auth/login', json={
        "username": "admin_test",
        "password": "wrong_password"
    })
    assert response.status_code == 401
    json_data = response.get_json()
    assert "access_token" not in json_data
    assert "attempts remaining" in json_data["message"]

def test_login_nonexistent_user(client):
    """Test login with non-existent username"""
    response = client.post('/api/auth/login', json={
        "username": "ghost_user",
        "password": "some_password"
    })
    assert response.status_code == 401
    json_data = response.get_json()
    assert "Invalid username or password" in json_data["message"]

def test_profile_access(client):
    """Test getting profile information using JWT"""
    # 1. Login to get token
    login_resp = client.post('/api/auth/login', json={
        "username": "student_test",
        "password": "student123"
    })
    token = login_resp.get_json()["access_token"]
    
    # 2. Access profile with header
    headers = {"Authorization": f"Bearer {token}"}
    profile_resp = client.get('/api/auth/profile', headers=headers)
    assert profile_resp.status_code == 200
    profile_data = profile_resp.get_json()
    assert profile_data["username"] == "student_test"
    assert profile_data["role"] == "Student"

def test_profile_unauthorized(client):
    """Test profile access without credentials"""
    response = client.get('/api/auth/profile')
    assert response.status_code == 401

def test_role_based_access_control(client):
    """Test that student cannot register users, but admin can"""
    # 1. Try registration as student
    student_login = client.post('/api/auth/login', json={
        "username": "student_test",
        "password": "student123"
    })
    student_token = student_login.get_json()["access_token"]
    
    reg_response = client.post('/api/auth/register', json={
        "username": "new_staff",
        "password": "Staff123!",
        "email": "staff@test.com",
        "role": "Staff"
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert reg_response.status_code == 403  # Forbidden
    
    # 2. Register as Admin
    admin_login = client.post('/api/auth/login', json={
        "username": "admin_test",
        "password": "admin123"
    })
    admin_token = admin_login.get_json()["access_token"]
    
    reg_response_ok = client.post('/api/auth/register', json={
        "username": "new_staff",
        "password": "Staff123!",
        "email": "staff@test.com",
        "role": "Staff"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert reg_response_ok.status_code == 201  # Created
    assert reg_response_ok.get_json()["user"]["username"] == "new_staff"

def test_account_lockout(client):
    """Test that too many failed logins locks the account"""
    # Failed attempt 1
    resp = client.post('/api/auth/login', json={"username": "admin_test", "password": "wrong_password"})
    assert resp.status_code == 401
    
    # Failed attempt 2
    resp = client.post('/api/auth/login', json={"username": "admin_test", "password": "wrong_password"})
    assert resp.status_code == 401
    
    # Failed attempt 3 -> Lockout triggers (Limit is set to 3 in TestConfig)
    resp = client.post('/api/auth/login', json={"username": "admin_test", "password": "wrong_password"})
    assert resp.status_code == 403
    assert "locked due to too many failed attempts" in resp.get_json()["message"]
    
    # Try logging in with CORRECT password after lockout -> Still locked
    resp_correct = client.post('/api/auth/login', json={"username": "admin_test", "password": "admin123"})
    assert resp_correct.status_code == 403
