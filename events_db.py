"""
Database models and utilities for event management.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

from config import get_config

config = get_config()
DATABASE = config.DB_PATH

@contextmanager
def get_db():
    """Get database connection context manager."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        # Users table for photographer accounts
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                storage_used INTEGER DEFAULT 0,
                storage_limit INTEGER DEFAULT 5368709120,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Events table with optional user ownership
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                qr_code_path TEXT,
                local_gallery_path TEXT,
                storage_type TEXT DEFAULT 'cloudinary',
                drive_folder_id TEXT,
                photographer_refresh_token TEXT,
                expires_at TIMESTAMP,
                auto_delete_scheduled BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Event photos table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS event_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                local_path TEXT,
                drive_file_id TEXT,
                cloudinary_url TEXT,
                cloudinary_public_id TEXT,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        ''')
        
        # Face embeddings table for AI matching
        conn.execute('''
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                photo_id INTEGER NOT NULL,
                embedding BLOB NOT NULL,
                face_location TEXT,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (photo_id) REFERENCES event_photos(id) ON DELETE CASCADE
            )
        ''')
        
        # Password resets table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()
    print("Database initialized successfully")


def create_event(name, date, location, description="", local_gallery_path=None):
    """Create a new event."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO events (name, date, location, description, local_gallery_path)
               VALUES (?, ?, ?, ?, ?)''',
            (name, date, location, description, local_gallery_path)
        )
        conn.commit()
        return cursor.lastrowid


def get_all_events():
    """Get all events."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM events ORDER BY date DESC'
        )
        return [dict(row) for row in cursor.fetchall()]


def get_event(event_id):
    """Get a single event by ID."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM events WHERE id = ?',
            (event_id,)
        )
        row = cursor.fetchone()
        if not row:
            # Debug log
            count = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            print(f"DATABASE DEBUG: Event {event_id} not found. Total records: {count}")
        return dict(row) if row else None


def update_event_qr_path(event_id, qr_path):
    """Update the QR code path for an event."""
    with get_db() as conn:
        conn.execute(
            'UPDATE events SET qr_code_path = ? WHERE id = ?',
            (qr_path, event_id)
        )
        conn.commit()


def delete_event(event_id):
    """Delete an event."""
    with get_db() as conn:
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        return True


def get_event_count():
    """Get total number of events."""
    with get_db() as conn:
        cursor = conn.execute('SELECT COUNT(*) FROM events')
        return cursor.fetchone()[0]


def add_event_photo(event_id, filename, local_path, drive_file_id=None):
    """Add a photo to an event."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO event_photos (event_id, filename, local_path, drive_file_id)
               VALUES (?, ?, ?, ?)''',
            (event_id, filename, local_path, drive_file_id)
        )
        conn.commit()
        return cursor.lastrowid


def get_event_photos(event_id):
    """Get all photos for an event."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM event_photos WHERE event_id = ? ORDER BY uploaded_at DESC',
            (event_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_photo(photo_id):
    """Get a single photo by ID."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM event_photos WHERE id = ?',
            (photo_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_photo_drive_id(local_path, drive_file_id):
    """Update drive_file_id for a photo."""
    with get_db() as conn:
        conn.execute(
            'UPDATE event_photos SET drive_file_id = ? WHERE local_path = ?',
            (drive_file_id, local_path)
        )
        conn.commit()


# ==================== USER MANAGEMENT ====================

def create_user(email, password_hash, name):
    """Create a new user account."""
    with get_db() as conn:
        try:
            cursor = conn.execute(
                '''INSERT INTO users (email, password_hash, name)
                   VALUES (?, ?, ?)''',
                (email, password_hash, name)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # Email already exists


def get_user_by_email(email):
    """Get user by email."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """Get user by ID."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM users WHERE id = ?',
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_user_storage(user_id, bytes_delta):
    """Update user's storage used (add or subtract bytes)."""
    with get_db() as conn:
        conn.execute(
            'UPDATE users SET storage_used = storage_used + ? WHERE id = ?',
            (bytes_delta, user_id)
        )
        conn.commit()


def get_user_storage(user_id):
    """Get user's storage usage."""
    user = get_user_by_id(user_id)
    if user:
        return {
            'used': user['storage_used'],
            'limit': user['storage_limit'],
            'available': user['storage_limit'] - user['storage_used'],
            'percent_used': round((user['storage_used'] / user['storage_limit']) * 100, 1)
        }
    return None


def get_events_by_user(user_id):
    """Get all events for a specific user."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM events WHERE user_id = ? ORDER BY date DESC',
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def create_event_for_user(user_id, name, date, location, description="", local_gallery_path=None):
    """Create a new event for a specific user."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO events (user_id, name, date, location, description, local_gallery_path)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, name, date, location, description, local_gallery_path)
        )
        conn.commit()
        return cursor.lastrowid


def add_photo_with_cloudinary(event_id, filename, local_path, cloudinary_url, cloudinary_public_id, file_size):
    """Add a photo with Cloudinary info."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO event_photos (event_id, filename, local_path, cloudinary_url, cloudinary_public_id, file_size)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (event_id, filename, local_path, cloudinary_url, cloudinary_public_id, file_size)
        )
        conn.commit()
        return cursor.lastrowid


# ==================== PASSWORD RESET ====================

def create_reset_token(user_id, token, expires_at):
    """Create a password reset token for a user."""
    with get_db() as conn:
        # Delete any existing tokens for this user
        conn.execute('DELETE FROM password_resets WHERE user_id = ?', (user_id,))
        
        conn.execute(
            'INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)',
            (user_id, token, expires_at)
        )
        conn.commit()


def get_user_by_reset_token(token):
    """Get user information by reset token if not expired."""
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            '''SELECT u.* 
               FROM users u
               JOIN password_resets pr ON u.id = pr.user_id
               WHERE pr.token = ? AND pr.expires_at > ?''',
            (token, datetime.now())
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_reset_token(token):
    """Delete a reset token after use."""
    with get_db() as conn:
        conn.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        conn.commit()


def update_user_password(user_id, password_hash):
    """Update user's password hash."""
    with get_db() as conn:
        conn.execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            (password_hash, user_id)
        )
        conn.commit()


# ==================== MANUAL UPLOAD (DRIVE-BACKED EVENTS) ====================

def create_manual_event(user_id, name, drive_folder_id, refresh_token, photo_count, expires_at):
    """Create a Drive-backed event with expiration."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO events (
                user_id, name, date, location, storage_type, 
                drive_folder_id, photographer_refresh_token, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, name, datetime.now().strftime('%Y-%m-%d'), 
             'Manual Upload', 'drive', drive_folder_id, refresh_token, expires_at)
        )
        conn.commit()
        return cursor.lastrowid


def get_expired_events():
    """Get all events that have expired and not yet deleted."""
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            '''SELECT * FROM events 
               WHERE expires_at IS NOT NULL 
               AND expires_at < ? 
               AND auto_delete_scheduled = 0''',
            (datetime.now(),)
        )
        return [dict(row) for row in cursor.fetchall()]


def mark_event_deleted(event_id):
    """Mark event as deleted after cleanup."""
    with get_db() as conn:
        conn.execute(
            'UPDATE events SET auto_delete_scheduled = 1 WHERE id = ?',
            (event_id,)
        )
        conn.commit()


def get_event_time_remaining(event_id):
    """Get time remaining until event expiration."""
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            'SELECT expires_at FROM events WHERE id = ?',
            (event_id,)
        )
        row = cursor.fetchone()
        if row and row['expires_at']:
            expires_at = datetime.fromisoformat(row['expires_at'])
            now = datetime.now()
            if now >= expires_at:
                return {'expired': True, 'hours': 0, 'minutes': 0}
            delta = expires_at - now
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            return {'expired': False, 'hours': hours, 'minutes': minutes}
        return None


def update_photo_cloudinary_info(local_path, cloudinary_url, cloudinary_public_id, file_size):
    """Update Cloudinary info for a photo."""
    with get_db() as conn:
        conn.execute(
            '''UPDATE event_photos 
               SET cloudinary_url = ?, cloudinary_public_id = ?, file_size = ?
               WHERE local_path = ?''',
            (cloudinary_url, cloudinary_public_id, file_size, local_path)
        )
        conn.commit()


def get_photo(photo_id):
    """Get photo info including its event ownership."""
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            '''SELECT p.*, e.user_id 
               FROM event_photos p 
               JOIN events e ON p.event_id = e.id 
               WHERE p.id = ?''',
            (photo_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_photo(photo_id):
    """Delete a photo record from database."""
    with get_db() as conn:
        conn.execute('DELETE FROM event_photos WHERE id = ?', (photo_id,))
        conn.commit()
