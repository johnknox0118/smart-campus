import os
import sys
from datetime import datetime, date

# Add parent directory to path so config/models can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db, User, Department, ClassRoom, Bus, AuditLog

def seed_database():
    app = create_app()
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("Tables created successfully.")
        
        # Check if database is already seeded
        if User.query.first():
            print("Database already has data. Skipping seeding.")
            return
            
        print("Seeding database...")
        
        # 1. Create Departments
        cse = Department(name="Computer Science & Engineering")
        ece = Department(name="Electronics & Communication Engineering")
        it = Department(name="Information Technology")
        db.session.add_all([cse, ece, it])
        db.session.commit()
        print("Departments seeded.")
        
        # 2. Create Classes
        cse_a = ClassRoom(name="CSE-A", department_id=cse.id)
        ece_a = ClassRoom(name="ECE-A", department_id=ece.id)
        it_a = ClassRoom(name="IT-A", department_id=it.id)
        db.session.add_all([cse_a, ece_a, it_a])
        db.session.commit()
        print("Classes seeded.")
        
        # 3. Create Users (We hash passwords using Flask-Bcrypt in registration, but here we can do it directly)
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt(app)
        
        admin = User(
            username="admin",
            password_hash=bcrypt.generate_password_hash("admin123").decode('utf-8'),
            email="admin@prathyusha.edu.in",
            role="Admin",
            is_active=True
        )
        
        student = User(
            username="student",
            password_hash=bcrypt.generate_password_hash("student123").decode('utf-8'),
            email="student@prathyusha.edu.in",
            role="Student",
            department_id=cse.id,
            class_id=cse_a.id,
            is_active=True
        )
        
        staff = User(
            username="staff",
            password_hash=bcrypt.generate_password_hash("staff123").decode('utf-8'),
            email="staff@prathyusha.edu.in",
            role="Staff",
            department_id=cse.id,
            is_active=True
        )
        
        driver = User(
            username="driver",
            password_hash=bcrypt.generate_password_hash("driver123").decode('utf-8'),
            email="driver@prathyusha.edu.in",
            role="Driver",
            is_active=True
        )
        
        security = User(
            username="security",
            password_hash=bcrypt.generate_password_hash("security123").decode('utf-8'),
            email="security@prathyusha.edu.in",
            role="Security",
            is_active=True
        )
        
        db.session.add_all([admin, student, staff, driver, security])
        db.session.commit()
        print("Users seeded.")
        
        # 4. Create Buses
        bus = Bus(
            bus_number="PEC-001",
            route_name="Poonamallee - Tiruvallur Road to PEC Campus",
            driver_id=driver.id,
            capacity=50,
            status="Inactive"
        )
        db.session.add(bus)
        db.session.commit()
        print("Buses seeded.")
        
        # 5. Add an audit log entry for initialization
        log = AuditLog(
            user_id=admin.id,
            event_type="Database Init",
            details="Database schema initialized and seeded with default roles and accounts.",
            ip_address="127.0.0.1"
        )
        db.session.add(log)
        db.session.commit()
        
        print("Database initialization complete.")

if __name__ == "__main__":
    seed_database()
