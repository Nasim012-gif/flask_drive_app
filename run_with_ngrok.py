
import time
import ssl
import sys
import os
from pyngrok import ngrok
from dotenv import load_dotenv

# Bypass SSL verify for pyngrok downloads/checks
ssl._create_default_https_context = ssl._create_unverified_context

# Load env to ensure we don't mess up paths
load_dotenv()

def start_app_with_tunnel():
    # 1. Start Ngrok Tunnel
    # Connect to port 5000
    try:
        # Point to local binary if present
        ngrok_path = os.path.join(os.getcwd(), 'ngrok')
        print(f"DEBUG: Checking for ngrok at {ngrok_path}")
        if os.path.exists(ngrok_path):
            print("DEBUG: Found local ngrok binary")
            from pyngrok.conf import PyngrokConfig
            # Ensure we don't try to update
            ngrok.set_auth_token(os.getenv('NGROK_AUTH_TOKEN')) if os.getenv('NGROK_AUTH_TOKEN') else None
            conf = PyngrokConfig(ngrok_path=ngrok_path)
            public_url = ngrok.connect(8080, pyngrok_config=conf).public_url
        else:
            public_url = ngrok.connect(5000).public_url
            
        print(f"✅ Ngrok Tunnel Established: {public_url}")
    except Exception as e:
        print(f"❌ Failed to start ngrok: {e}")
        print("Please ensure you have internet connection.")
        sys.exit(1)

    # 2. Update QR Codes with new URL
    print("🔄 Updating QR Codes to point to public URL...")
    
    # Import here to avoid early config loading issues
    from qr_generator import generate_event_qr
    import sqlite3
    
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    events = cursor.execute('SELECT * FROM events').fetchall()
    
    for event in events:
        generate_event_qr(event['id'], public_url)
    
    conn.commit()
    conn.close()
    print("✅ QR Codes Updated!")

    # 3. Print Instructions
    print("\n" + "="*60)
    print(f"🌍 GLOBAL STATION ONLINE")
    print(f"🔗 DASHBOARD & MOBILE URL: {public_url}")
    print(f"👉 Use this URL for EVERYTHING (Admin, Sharing, Guest Access)")
    print("="*60 + "\n")

    # 4. Start Flask App
    # We use os.system to run it so it takes over the process
    os.system("./venv/bin/python app.py")

if __name__ == "__main__":
    start_app_with_tunnel()
