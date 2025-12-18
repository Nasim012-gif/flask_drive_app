
import sqlite3
import os
from qr_generator import generate_event_qr

DB_PATH = 'events.db'
BASE_URL = 'https://192.168.1.100:5000'

def update_qrs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    events = cursor.execute('SELECT * FROM events').fetchall()
    print(f"Found {len(events)} events. Regenerating QR codes...")
    
    for event in events:
        event_id = event['id']
        print(f"Regenerating for Event {event_id}...")
        
        # Generate new QR
        qr_path = generate_event_qr(event_id, BASE_URL)
        
        # Update DB (though path usually stays same, good to be sure)
        conn.execute('UPDATE events SET qr_code_path = ? WHERE id = ?', (qr_path, event_id))
    
    conn.commit()
    conn.close()
    print("✅ All QR codes regenerated with URL:", BASE_URL)

if __name__ == "__main__":
    update_qrs()
