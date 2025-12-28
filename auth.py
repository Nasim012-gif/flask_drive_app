"""
Authentication module for user login/registration.
Uses bcrypt for password hashing and Flask sessions for auth state.
"""

import hashlib
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash

import events_db


def hash_password(password):
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password, stored_hash):
    """Verify a password against stored hash."""
    try:
        salt, hash_value = stored_hash.split(':')
        password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return password_hash == hash_value
    except:
        return False


def register_user(email, password, name):
    """Register a new user."""
    # Validate input
    if not email or not password or not name:
        return None, "All fields are required"
    
    if len(password) < 6:
        return None, "Password must be at least 6 characters"
    
    # Check if email exists
    existing = events_db.get_user_by_email(email)
    if existing:
        return None, "Email already registered"
    
    # Create user
    password_hash = hash_password(password)
    user_id = events_db.create_user(email, password_hash, name)
    
    if user_id:
        return user_id, None
    else:
        return None, "Registration failed"


def login_user(email, password):
    """Authenticate user and create session."""
    user = events_db.get_user_by_email(email)
    
    if not user:
        return None, "Email not found"
    
    if not verify_password(password, user['password_hash']):
        return None, "Incorrect password"
    
    # Set session
    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session['user_name'] = user['name']
    
    return user, None


def logout_user():
    """Clear user session."""
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)


def get_current_user():
    """Get current logged in user."""
    user_id = session.get('user_id')
    if user_id:
        return events_db.get_user_by_id(user_id)
    return None


def is_logged_in():
    """Check if user is logged in."""
    return 'user_id' in session


def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def format_storage(bytes_value):
    """Format bytes as human-readable string."""
    if bytes_value >= 1073741824:  # 1 GB
        return f"{bytes_value / 1073741824:.2f} GB"
    elif bytes_value >= 1048576:  # 1 MB
        return f"{bytes_value / 1048576:.1f} MB"
    elif bytes_value >= 1024:  # 1 KB
        return f"{bytes_value / 1024:.0f} KB"
    else:
        return f"{bytes_value} B"
