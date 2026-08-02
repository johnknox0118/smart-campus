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

# Ensure database directory exists
db_dir = os.path.join(base_dir, 'database')
os.makedirs(db_dir, exist_ok=True)
db_file = os.path.abspath(os.path.join(db_dir, 'campus.db'))

database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    db_uri = database_url
else:
    db_uri = f'sqlite:///{db_file}'

class Config:
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key_12345')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key_12345')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Database Settings
    SQLALCHEMY_DATABASE_URI = db_uri
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
            "radius": 500,
            "color": "#3A5CCC"
        },
        "Academic Block": {
            "type": "circle",
            "lat": 13.092233,
            "lng": 79.973900,
            "radius": 100,
            "color": "#2ecc71"
        },
        "Library": {
            "type": "circle",
            "lat": 13.092300,
            "lng": 79.973900,
            "radius": 30,
            "color": "#e74c3c"
        },
        "Girls Hostel": {
            "type": "circle",
            "lat": 13.091300,
            "lng": 79.972300,
            "radius": 70,
            "color": "#9b59b6"
        },
        "Parking": {
            "type": "circle",
            "lat": 13.093200,
            "lng": 79.973900,
            "radius": 50,
            "color": "#f1c40f"
        },
        "Sports Ground": {
            "type": "circle",
            "lat": 13.092200,
            "lng": 79.971500,
            "radius": 90,
            "color": "#1abc9c"
        },
        "Boys Hostel": {
            "type": "circle",
            "lat": 13.089800,
            "lng": 79.974900,
            "radius": 60,
            "color": "#e67e22"
        }
    }
