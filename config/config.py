import os
from dotenv import load_dotenv

# Define path to .env file
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, 'config', '.env')

# Load environment variables
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()

class Config:
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key_12345')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key_12345')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Database Settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(base_dir, 'database', 'campus.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security Settings
    ACCOUNT_LOCKOUT_LIMIT = int(os.environ.get('ACCOUNT_LOCKOUT_LIMIT', 5))
    LOCKOUT_DURATION_MINS = int(os.environ.get('LOCKOUT_DURATION_MINS', 15))
    SESSION_TIMEOUT_MINS = int(os.environ.get('SESSION_TIMEOUT_MINS', 30))
    
    # GPS Tracking & Spoof Detection Settings
    MAX_PEDESTRIAN_SPEED = float(os.environ.get('MAX_PEDESTRIAN_SPEED', 15.0))  # km/h
    MAX_VEHICLE_SPEED = float(os.environ.get('MAX_VEHICLE_SPEED', 80.0))        # km/h
    GPS_INTERVAL_SECS = 15
    
    # Core Geofences (Centered around Prathyusha Engineering College: 13.092233, 79.973900)
    GEOFENCES = {
        "Entire Campus": {
            "type": "circle",
            "lat": 13.092233,
            "lng": 79.973900,
            "radius": 500  # meters
        },
        "Library": {
            "type": "circle",
            "lat": 13.092300,
            "lng": 79.973900,
            "radius": 30
        },
        "Academic Block": {
            "type": "circle",
            "lat": 13.092233,
            "lng": 79.973900,
            "radius": 100
        },
        "Girls Hostel": {
            "type": "circle",
            "lat": 13.091300,
            "lng": 79.972300,
            "radius": 70
        },
        "Parking": {
            "type": "circle",
            "lat": 13.093200,
            "lng": 79.973900,
            "radius": 50
        },
        "Sports Ground": {
            "type": "circle",
            "lat": 13.092200,
            "lng": 79.971500,
            "radius": 90
        },
        "Boys Hostel": {
            "type": "circle",
            "lat": 13.089800,
            "lng": 79.974900,
            "radius": 60
        }
    }
    
    # Academic Hours (for auto attendance)
    COLLEGE_START_HOUR = 8  # 8:00 AM
    COLLEGE_END_HOUR = 16   # 4:00 PM
    LATE_THRESHOLD_MINS = 30  # Present, but marked 'Late' if checked in after 8:30 AM
    HALF_DAY_THRESHOLD_HOURS = 4  # Marked 'Half Day' if checked in for less than 4 hours
