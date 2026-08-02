from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='department', lazy=True)
    classes = db.relationship('ClassRoom', backref='department', lazy=True)

class ClassRoom(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='class_room', lazy=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Student, Staff, Driver, Security, Admin
    
    # Links to department/class (Optional based on role)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    
    # Security parameters
    is_active = db.Column(db.Boolean, default=True)
    is_locked = db.Column(db.Boolean, default=False)
    failed_logins = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    custom_id = db.Column(db.String(50), nullable=True)
    mobile_no = db.Column(db.String(20), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    section = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    locations = db.relationship('LocationLog', backref='user', lazy=True)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True)
    leave_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.user_id', backref='user', lazy=True)
    approved_leaves = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.approved_by', backref='approver', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)
    emergency_alerts = db.relationship('EmergencyAlert', foreign_keys='EmergencyAlert.user_id', backref='reporter', lazy=True)
    resolved_alerts = db.relationship('EmergencyAlert', foreign_keys='EmergencyAlert.resolved_by', backref='resolver', lazy=True)
    bus_assignment = db.relationship('Bus', backref='driver', uselist=False, lazy=True)

class LocationLog(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float, default=0.0)      # Speed in km/h
    accuracy = db.Column(db.Float, default=0.0)   # GPS accuracy in meters
    battery = db.Column(db.Integer, default=100)  # Battery level percentage
    geofence_name = db.Column(db.String(50), default="Outside")
    is_spoofed = db.Column(db.Boolean, default=False)
    spoof_reason = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Present, Late, Half Day, Absent, On Leave
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bus(db.Model):
    __tablename__ = 'buses'
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(20), unique=True, nullable=False)
    route_name = db.Column(db.String(100), nullable=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    capacity = db.Column(db.Integer, default=50)
    status = db.Column(db.String(20), default="Inactive")  # Active, Inactive
    start_location = db.Column(db.String(100), nullable=True)
    stops = db.Column(db.String(255), nullable=True)
    route_number = db.Column(db.String(50), nullable=True)
    driver_phone = db.Column(db.String(20), nullable=True)
    driver_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    locations = db.relationship('BusLocationLog', backref='bus', lazy=True)

class BusLocationLog(db.Model):
    __tablename__ = 'bus_locations'
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float, default=0.0)
    eta_mins = db.Column(db.Integer, default=0)        # Estimated time of arrival to main campus in minutes
    next_stop = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Pending")  # Pending, Approved, Rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # Attendance, Bus, Leave, Emergency, Announcement
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Can be null if failed login
    event_type = db.Column(db.String(50), nullable=False)  # Login Success, Login Failure, Spoof Attempt, SOS Alert, Route Deviation, Geofence Crossing
    details = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class EmergencyAlert(db.Model):
    __tablename__ = 'emergency_alerts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Active")  # Active, Resolved
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
