import re
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def role_required(allowed_roles):
    """
    Decorator to restrict access to specific roles.
    Allowed roles should be a list of strings: ['Admin', 'Security', 'Staff', etc.]
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Verify JWT is present in request
            verify_jwt_in_request()
            
            # Get claims from JWT
            claims = get_jwt()
            user_role = claims.get('role')
            
            if not user_role or user_role not in allowed_roles:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Access denied. Required role: {', '.join(allowed_roles)}"
                }), 403
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def validate_password_strength(password):
    """
    Validates that a password is:
    - At least 8 characters long
    - Contains at least 1 uppercase letter
    - Contains at least 1 lowercase letter
    - Contains at least 1 number
    """
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True

def get_client_ip():
    """
    Helper to extract real IP address from request, handling proxies
    """
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr
