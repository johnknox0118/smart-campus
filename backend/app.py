import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate

# Import Config class
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config

# Import db from models to avoid circular imports
from backend.models import db
from backend.routes.auth import auth_bp
from backend.routes.gps import gps_bp
from backend.routes.bus import bus_bp
from backend.routes.leave import leave_bp
from backend.routes.emergency import emergency_bp
from backend.routes.analytics import analytics_bp
from backend.routes.notifications import notifications_bp
from backend.routes.attendance import attendance_bp
from backend.routes.attendance_report import attendance_report_bp

# Initialize Extensions
jwt = JWTManager()
bcrypt = Bcrypt()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(gps_bp, url_prefix='/api/gps')
    app.register_blueprint(bus_bp, url_prefix='/api/bus')
    app.register_blueprint(leave_bp, url_prefix='/api/leave')
    app.register_blueprint(emergency_bp, url_prefix='/api/emergency')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(attendance_report_bp, url_prefix='/api/attendance/report')
    
    # Ensure directories exist
    os.makedirs(os.path.join(app.root_path, '../logs'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '../uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '../database'), exist_ok=True)
    
    # Setup Logging
    configure_logging(app)
    
    # Simple root route
    @app.route('/')
    def index():
        app.logger.info("Root endpoint accessed")
        return jsonify({
            "status": "online",
            "message": "Smart Campus Management & Security System API is running",
            "version": "1.0.0"
        })
        
    # Global error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "Unauthorized", "message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "Forbidden", "message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server Error: {str(error)}")
        return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500
        
    return app

def configure_logging(app):
    log_dir = os.path.join(app.root_path, '../logs')
    log_file = os.path.join(log_dir, 'campus.log')
    
    log_level = logging.INFO
    if app.config['DEBUG']:
        log_level = logging.DEBUG
        
    # Standard format for logs
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    
    # File handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(log_level)
    app.logger.info("Smart Campus logging system initialized")

# Instantiate Flask App
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port)
