from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import sys
import os

# Resolve paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import db, User, Bus, BusLocationLog, AuditLog
from backend.utils.security import role_required, get_client_ip

bus_bp = Blueprint('bus', __name__)

@bus_bp.route('/status', methods=['GET'])
@jwt_required()
def get_bus_status():
    buses = Bus.query.all()
    bus_data = []
    
    for bus in buses:
        # Get latest location
        latest_loc = BusLocationLog.query.filter_by(bus_id=bus.id)\
                                         .order_by(BusLocationLog.timestamp.desc()).first()
                                         
        driver_name_val = bus.driver_name if bus.driver_name else (bus.driver.username if bus.driver else "Unassigned")
        driver_phone_val = bus.driver_phone if bus.driver_phone else ""
        route_number_val = bus.route_number if bus.route_number else ""
        
        bus_info = {
            "id": bus.id,
            "bus_number": bus.bus_number,
            "route_name": bus.route_name or "",
            "route_number": route_number_val,
            "driver_name": driver_name_val,
            "driver_phone": driver_phone_val,
            "driver_id": bus.driver_id,
            "capacity": bus.capacity,
            "status": bus.status,
            "start_location": bus.start_location or "",
            "stops": bus.stops or "",
            "latitude": latest_loc.latitude if latest_loc else None,
            "longitude": latest_loc.longitude if latest_loc else None,
            "speed": latest_loc.speed if latest_loc else 0.0,
            "eta_mins": latest_loc.eta_mins if latest_loc else 0,
            "next_stop": latest_loc.next_stop if latest_loc else "Not Started",
            "last_updated": latest_loc.timestamp.strftime('%Y-%m-%d %H:%M:%S') if latest_loc else None
        }
        bus_data.append(bus_info)
        
    return jsonify({"buses": bus_data}), 200

@bus_bp.route('/location', methods=['POST'])
@jwt_required()
@role_required(['Driver'])
def update_bus_location():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    
    if not user:
        return jsonify({"error": "Not found", "message": "Driver not found"}), 404
        
    # Find bus assigned to this driver
    bus = Bus.query.filter_by(driver_id=user.id).first()
    if not bus:
        return jsonify({"error": "Forbidden", "message": "No bus assigned to this driver account."}), 403
        
    data = request.get_json() or {}
    
    try:
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        speed = float(data.get('speed', 0.0))
        eta_mins = int(data.get('eta_mins', 0))
        next_stop = data.get('next_stop', 'Main Campus')
    except (ValueError, TypeError):
        return jsonify({"error": "Bad request", "message": "Invalid latitude, longitude, speed, or ETA type."}), 400
        
    # Log location
    bus_location = BusLocationLog(
        bus_id=bus.id,
        latitude=latitude,
        longitude=longitude,
        speed=speed,
        eta_mins=eta_mins,
        next_stop=next_stop,
        timestamp=datetime.utcnow()
    )
    db.session.add(bus_location)
    
    # Auto toggle bus state to Active if driver is pushing coordinates
    if bus.status != "Active":
        bus.status = "Active"
        
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "Bus location telemetry logged",
        "bus_number": bus.bus_number
    }), 200

@bus_bp.route('/assign', methods=['POST'])
@jwt_required()
@role_required(['Admin'])
def assign_driver():
    data = request.get_json() or {}
    bus_id = data.get('bus_id')
    driver_id = data.get('driver_id')
    
    if not bus_id or not driver_id:
        return jsonify({"error": "Bad request", "message": "bus_id and driver_id are required"}), 400
        
    bus = db.session.get(Bus, int(bus_id))
    driver = db.session.get(User, int(driver_id))
    
    if not bus:
        return jsonify({"error": "Not found", "message": "Bus not found"}), 404
        
    if not driver or driver.role != 'Driver':
        return jsonify({"error": "Bad request", "message": "User is not a registered driver"}), 400
        
    # Check if driver is already assigned to another bus
    existing_assignment = Bus.query.filter(Bus.driver_id == driver.id, Bus.id != bus.id).first()
    if existing_assignment:
        return jsonify({
            "error": "Conflict", 
            "message": f"Driver is already assigned to Bus {existing_assignment.bus_number}."
        }), 409
        
    bus.driver_id = driver.id
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id),
        event_type="Bus Assignment",
        details=f"Assigned driver '{driver.username}' to bus '{bus.bus_number}'",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        "message": f"Driver {driver.username} successfully assigned to Bus {bus.bus_number}"
    }), 200

@bus_bp.route('/add', methods=['POST'])
@jwt_required()
@role_required(['Admin'])
def add_bus():
    data = request.get_json() or {}
    bus_number = data.get('bus_number')
    route_number = data.get('route_number')
    driver_name = data.get('driver_name')
    driver_phone = data.get('driver_phone')
    start_location = data.get('start_location')
    stops = data.get('stops')
    
    if not bus_number or not route_number:
        return jsonify({"error": "Bad request", "message": "Bus Number and Route Number are required"}), 400
        
    # Check duplicate bus number
    if Bus.query.filter_by(bus_number=bus_number).first():
        return jsonify({"error": "Conflict", "message": "Bus number already exists."}), 409
        
    # Link driver_id dynamically by looking up driver_name matching username
    d_id = None
    if driver_name:
        driver = User.query.filter_by(username=driver_name, role='Driver').first()
        if driver:
            # Check if driver already assigned
            existing = Bus.query.filter_by(driver_id=driver.id).first()
            if not existing:
                d_id = driver.id
        
    new_bus = Bus(
        bus_number=bus_number,
        route_name=f"Route {route_number}", # populate fallback route_name for backward compatibility
        route_number=route_number,
        driver_name=driver_name,
        driver_phone=driver_phone,
        driver_id=d_id,
        capacity=50,
        status="Inactive",
        start_location=start_location,
        stops=stops
    )
    db.session.add(new_bus)
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id),
        event_type="Bus Creation",
        details=f"Created new Bus '{bus_number}'",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Bus '{bus_number}' created successfully.", "bus_id": new_bus.id}), 201

@bus_bp.route('/edit/<int:bus_id>', methods=['PUT'])
@jwt_required()
@role_required(['Admin'])
def edit_bus(bus_id):
    bus = db.session.get(Bus, bus_id)
    if not bus:
        return jsonify({"error": "Not Found", "message": "Bus not found"}), 404
        
    data = request.get_json() or {}
    bus_number = data.get('bus_number')
    route_number = data.get('route_number')
    driver_name = data.get('driver_name')
    driver_phone = data.get('driver_phone')
    start_location = data.get('start_location')
    stops = data.get('stops')
    
    if bus_number:
        existing = Bus.query.filter(Bus.bus_number == bus_number, Bus.id != bus_id).first()
        if existing:
            return jsonify({"error": "Conflict", "message": "Bus number already exists."}), 409
        bus.bus_number = bus_number
        
    if route_number:
        bus.route_number = route_number
        bus.route_name = f"Route {route_number}"
        
    if 'driver_name' in data:
        bus.driver_name = driver_name
        # Auto link driver_id
        if driver_name:
            driver = User.query.filter_by(username=driver_name, role='Driver').first()
            if driver:
                existing = Bus.query.filter(Bus.driver_id == driver.id, Bus.id != bus_id).first()
                if not existing:
                    bus.driver_id = driver.id
            else:
                bus.driver_id = None
        else:
            bus.driver_id = None
            
    if 'driver_phone' in data:
        bus.driver_phone = driver_phone
        
    if 'start_location' in data:
        bus.start_location = start_location
        
    if 'stops' in data:
        bus.stops = stops
        
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id),
        event_type="Bus Update",
        details=f"Updated Bus '{bus.bus_number}' details",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Bus '{bus.bus_number}' updated successfully."}), 200

@bus_bp.route('/delete/<int:bus_id>', methods=['DELETE'])
@jwt_required()
@role_required(['Admin'])
def delete_bus(bus_id):
    bus = db.session.get(Bus, bus_id)
    if not bus:
        return jsonify({"error": "Not Found", "message": "Bus not found"}), 404
        
    bus_number = bus.bus_number
    
    # Clean up associated location logs
    BusLocationLog.query.filter_by(bus_id=bus_id).delete()
    
    db.session.delete(bus)
    db.session.commit()
    
    # Audit log
    admin_id = get_jwt_identity()
    audit = AuditLog(
        user_id=int(admin_id),
        event_type="Bus Deletion",
        details=f"Deleted Bus '{bus_number}' (ID: {bus_id})",
        ip_address=get_client_ip()
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Bus '{bus_number}' deleted successfully."}), 200
