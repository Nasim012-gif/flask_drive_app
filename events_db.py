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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                qr_code_path TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS event_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                local_path TEXT NOT NULL,
                drive_file_id TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
        ''')
        conn.commit()
    print("Database initialized successfully")


def create_event(name, date, location, description=""):
    """Create a new event."""
    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO events (name, date, location, description)
               VALUES (?, ?, ?, ?)''',
            (name, date, location, description)
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
