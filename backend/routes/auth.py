from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, get_jwt
)
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import re

# Resolve relative path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, Department, ClassRoom, AuditLog
from backend.utils.security import role_required, validate_password_strength, get_client_ip

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

@auth_bp.route('/register', methods=['POST'])
@jwt_required()
@role_required(['Admin'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    role = data.get('role')  # Student, Staff, Driver, Security, Admin
    
    # Validation
    if not all([username, password, email, role]):
        return jsonify({"error": "Bad request", "message": "All fields are required"}), 400
        
    # Category Normalization
    role_lower = role.lower().strip()
    if role_lower == 'non teaching':
        role = 'Non Teaching Staff'
    elif role_lower == 'deriver':
        role = 'Driver'
    else:
        role = role.title()
        
    if role not in ['Student', 'Staff', 'Driver', 'Security', 'Admin', 'Non Teaching Staff']:
        return jsonify({"error": "Bad request", "message": "Invalid role specified"}), 400
        
    if not validate_password_strength(password):
        return jsonify({
            "error": "Weak password", 
            "message": "Password must be at least 8 characters long, contain uppercase, lowercase, and numeric characters."
        }), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Conflict", "message": "Username already exists"}), 409
        
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Conflict", "message": "Email already exists"}), 409
        
    # Department & Class handling (Optional)
    department_id = None
    class_id = None
    
    dept_name = data.get('department_name')
    if dept_name:
        dept = Department.query.filter_by(name=dept_name).first()
        if not dept:
            dept = Department(name=dept_name)
            db.session.add(dept)
            db.session.commit()
        department_id = dept.id
            
    if data.get('class_name'):
        cls = ClassRoom.query.filter_by(name=data.get('class_name')).first()
        if cls:
            class_id = cls.id
            
    # Create User
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(
        username=username,
        password_hash=password_hash,
        email=email,
        role=role,
        department_id=department_id,
        class_id=class_id,
        is_active=True,
        custom_id=data.get('custom_id'),
        mobile_no=data.get('mobile_no'),
        year=data.get('year'),
        section=data.get('section')
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id) if admin_id else None,
        event_type="User Registration",
        details=f"Registered new user '{username}' with role '{role}'",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        "message": "User registered successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role
        }
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Bad request", "message": "Username and password are required"}), 400
        
    user = User.query.filter_by(username=username).first()
    
    # Standard security measure: generic failure message to prevent username harvesting
    generic_error = {"error": "Unauthorized", "message": "Invalid username or password"}
    ip_addr = get_client_ip()
    
    if not user:
        # Audit Log
        audit = AuditLog(
            user_id=None,
            event_type="Login Failure",
            details=f"Attempted login with non-existent username: '{username}'",
            ip_address=ip_addr
        )
        db.session.add(audit)
        db.session.commit()
        return jsonify(generic_error), 401
        
    # Check if account is locked
    if user.is_locked:
        if user.lockout_until and datetime.utcnow() < user.lockout_until:
            remaining_mins = int((user.lockout_until - datetime.utcnow()).total_seconds() / 60) + 1
            return jsonify({
                "error": "Locked out",
                "message": f"Account is locked due to too many failed attempts. Try again in {remaining_mins} minutes."
            }), 403
        else:
            # Lockout expired, unlock account
            user.is_locked = False
            user.failed_logins = 0
            user.lockout_until = None
            db.session.commit()
            
    # Verify password
    if bcrypt.check_password_hash(user.password_hash, password):
        # Reset failed attempts
        user.failed_logins = 0
        user.lockout_until = None
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate JWT Tokens
        # Load claims
        additional_claims = {
            "role": user.role,
            "username": user.username
        }
        
        access_token = create_access_token(
            identity=str(user.id), 
            additional_claims=additional_claims,
            expires_delta=timedelta(minutes=current_app.config['SESSION_TIMEOUT_MINS'])
        )
        refresh_token = create_refresh_token(identity=str(user.id))
        
        # Log audit
        audit = AuditLog(
            user_id=user.id,
            event_type="Login Success",
            details=f"User '{username}' logged in successfully.",
            ip_address=ip_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        }), 200
    else:
        # Password failed, increment counter
        user.failed_logins += 1
        limit = current_app.config['ACCOUNT_LOCKOUT_LIMIT']
        
        if user.failed_logins >= limit:
            user.is_locked = True
            user.lockout_until = datetime.utcnow() + timedelta(minutes=current_app.config['LOCKOUT_DURATION_MINS'])
            db.session.commit()
            
            audit = AuditLog(
                user_id=user.id,
                event_type="Account Locked",
                details=f"User '{username}' locked out due to {user.failed_logins} failed login attempts.",
                ip_address=ip_addr
            )
            db.session.add(audit)
            db.session.commit()
            
            return jsonify({
                "error": "Locked out",
                "message": f"Account is locked due to too many failed attempts. Try again in {current_app.config['LOCKOUT_DURATION_MINS']} minutes."
            }), 403
        else:
            db.session.commit()
            
            audit = AuditLog(
                user_id=user.id,
                event_type="Login Failure",
                details=f"Failed login attempt for user '{username}' (Attempt {user.failed_logins}/{limit})",
                ip_address=ip_addr
            )
            db.session.add(audit)
            db.session.commit()
            
            attempts_left = limit - user.failed_logins
            return jsonify({
                "error": "Unauthorized",
                "message": f"Invalid username or password. {attempts_left} attempts remaining before account lockout."
            }), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user or not user.is_active:
        return jsonify({"error": "Unauthorized", "message": "Invalid session"}), 401
        
    additional_claims = {
        "role": user.role,
        "username": user.username
    }
    
    new_access_token = create_access_token(
        identity=user_id,
        additional_claims=additional_claims,
        expires_delta=timedelta(minutes=current_app.config['SESSION_TIMEOUT_MINS'])
    )
    
    return jsonify({
        "access_token": new_access_token
    }), 200

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user:
        return jsonify({"error": "Not found", "message": "User profile not found"}), 404
        
    profile_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "last_login": user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
        "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Department / Class specific detail
    if user.department:
        profile_data["department"] = user.department.name
    if user.class_room:
        profile_data["class_room"] = user.class_room.name
        
    return jsonify(profile_data), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if user:
        # Audit Log
        audit = AuditLog(
            user_id=user.id,
            event_type="Logout",
            details=f"User '{user.username}' logged out.",
            ip_address=get_client_ip()
        )
        db.session.add(audit)
        db.session.commit()
        
    return jsonify({"message": "Logout successful"}), 200

# User Management APIs (Admin Only)
@auth_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required(['Admin'])
def get_all_users():
    users = User.query.all()
    user_list = []
    for u in users:
        user_list.append({
            "id": u.id,
            "custom_id": u.custom_id or "",
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "department": u.department.name if u.department else None,
            "class_room": u.class_room.name if u.class_room else None,
            "mobile_no": u.mobile_no or "",
            "year": u.year or "",
            "section": u.section or "",
            "is_active": u.is_active,
            "created_at": u.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"success": True, "users": user_list}), 200

@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@role_required(['Admin'])
def modify_user(user_id):
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "Not Found", "message": "User not found"}), 404
        
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    role = data.get('role')
    password = data.get('password')
    is_active = data.get('is_active')
    
    if username:
        existing = User.query.filter(User.username == username, User.id != user_id).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Username already exists"}), 409
        u.username = username
        
    if email:
        existing = User.query.filter(User.email == email, User.id != user_id).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Email already exists"}), 409
        u.email = email
        
    if role:
        role_lower = role.lower().strip()
        if role_lower == 'non teaching':
            role = 'Non Teaching Staff'
        elif role_lower == 'deriver':
            role = 'Driver'
        else:
            role = role.title()
            
        if role not in ['Student', 'Staff', 'Driver', 'Security', 'Admin', 'Non Teaching Staff']:
            return jsonify({"error": "Bad request", "message": "Invalid role specified"}), 400
        u.role = role
        
    if password:
        if not validate_password_strength(password):
            return jsonify({
                "error": "Weak password",
                "message": "Password must be at least 8 characters long, contain uppercase, lowercase, and numeric characters."
            }), 400
        u.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
    if is_active is not None:
        u.is_active = bool(is_active)
        
    if 'custom_id' in data:
        u.custom_id = data.get('custom_id')
        
    if 'mobile_no' in data:
        u.mobile_no = data.get('mobile_no')
        
    if 'year' in data:
        u.year = data.get('year')
        
    if 'section' in data:
        u.section = data.get('section')
        
    # Optional Department & Class
    if 'department_name' in data:
        dept_name = data.get('department_name')
        if dept_name:
            dept = Department.query.filter_by(name=dept_name).first()
            if not dept:
                dept = Department(name=dept_name)
                db.session.add(dept)
                db.session.commit()
            u.department_id = dept.id
        else:
            u.department_id = None
            
    if 'class_name' in data:
        if data['class_name']:
            cls = ClassRoom.query.filter_by(name=data['class_name']).first()
            if cls:
                u.class_id = cls.id
        else:
            u.class_id = None
            
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id),
        event_type="User Update",
        details=f"Modified user '{u.username}' details",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"User '{u.username}' updated successfully."}), 200

@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@role_required(['Admin'])
def delete_user(user_id):
    admin_id = get_jwt_identity()
    if int(admin_id) == user_id:
        return jsonify({"error": "Bad Request", "message": "Cannot delete your own admin account."}), 400
        
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "Not Found", "message": "User not found"}), 404
        
    username = u.username
    
    # Safely delete associated logs/child records first to prevent IntegrityError
    from backend.models import LocationLog, Attendance, LeaveRequest, Notification, AuditLog as DB_AuditLog, EmergencyAlert, Bus
    
    LocationLog.query.filter_by(user_id=user_id).delete()
    Attendance.query.filter_by(user_id=user_id).delete()
    LeaveRequest.query.filter((LeaveRequest.user_id == user_id) | (LeaveRequest.approved_by == user_id)).delete()
    Notification.query.filter_by(user_id=user_id).delete()
    DB_AuditLog.query.filter_by(user_id=user_id).delete()
    EmergencyAlert.query.filter((EmergencyAlert.user_id == user_id) | (EmergencyAlert.resolved_by == user_id)).delete()
    
    # Clean up bus assignment
    bus = Bus.query.filter_by(driver_id=user_id).first()
    if bus:
        bus.driver_id = None
        
    db.session.delete(u)
    db.session.commit()
    
    # Create final log audit
    audit = DB_AuditLog(
        user_id=int(admin_id),
        event_type="User Deletion",
        details=f"Deleted user account '{username}' (ID: {user_id})",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"User '{username}' deleted successfully."}), 200
