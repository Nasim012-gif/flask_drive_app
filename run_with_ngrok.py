
import time
import sys
import os
from pyngrok import ngrok
from dotenv import load_dotenv

# Load env to ensure we don't mess up paths
load_dotenv()

def start_app_with_tunnel():
    # 1. Start Ngrok Tunnel
    # Connect to port 5000
    try:
        # Point to local binary if present
        ngrok_path = os.path.join(os.getcwd(), 'ngrok')
        if os.path.exists(ngrok_path):
            from pyngrok.conf import PyngrokConfig
            ngrok.set_auth_token(os.getenv('NGROK_AUTH_TOKEN')) if os.getenv('NGROK_AUTH_TOKEN') else None
            conf = PyngrokConfig(ngrok_path=ngrok_path)
            public_url = ngrok.connect(5000, pyngrok_config=conf).public_url
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
    print(f"🌍 PUBLIC ACCESS URL: {public_url}")
    print(f"📱 SCAN THE QR CODE NOW - IT WILL WORK GLOBALLY!")
    print("="*60 + "\n")

    # 4. Start Flask App
    # We use os.system to run it so it takes over the process
    os.system("./venv/bin/python app.py")

if __name__ == "__main__":
    start_app_with_tunnel()
