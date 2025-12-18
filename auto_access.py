
import socket
import os
import sys
import sqlite3
import subprocess
import time
from qr_generator import generate_event_qr

def get_ip():
    """Detect the local IP address connected to the network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def update_qrs(base_url):
    """Regenerate all QR codes with the current base URL."""
    print(f"🔄 Updating QR Codes to point to: {base_url}")
    
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        events = cursor.execute('SELECT * FROM events').fetchall()
        for event in events:
            generate_event_qr(event['id'], base_url)
        conn.commit()
    except Exception as e:
        print(f"⚠️ Could not update QR codes: {e}")
    finally:
        conn.close()

def main():
    # 1. Detect IP
    ip = get_ip()
    port = 5000
    base_url = f"https://{ip}:{port}"
    
    print("="*60)
    print(f"🚀 STARTING SECURE EVENT SERVER")
    print(f"📍 Local IP Detected: {ip}")
    print("="*60)
    
    # 2. Update QRs
    update_qrs(base_url)
    
    # 3. Check for Certificates
    if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
        print("⚡ Generating SSL Certificates...")
        subprocess.run(
            "openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj '/CN=EventServer'", 
            shell=True, check=True
        )
    
    # 4. Start Flask (replacing this process)
    print("\nStarting Flask Server...")
    print(f"✅ Admin URL: {base_url}/admin")
    print(f"✅ Guest URL: {base_url}/event/<id>")
    print("\n⚠️  NOTE: Accept the 'Not Secure' warning in your browser.")
    
    # Pass the detected IP to the app via environment variable if needed, 
    # but app.py listens on 0.0.0.0 so it handles traffic to any IP.
    # The important part was generating the Correct QR codes.
    
    # We use subprocess instead of importing app to ensure a clean process state
    # and to allow Ctrl+C to work cleanly.
    cmd = [sys.executable, "app.py"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Server Stopped.")

if __name__ == "__main__":
    main()
