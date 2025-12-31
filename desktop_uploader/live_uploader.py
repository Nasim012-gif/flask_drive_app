#!/usr/bin/env python3
"""
GetPhotos Desktop Live Uploader
Watches a folder and automatically uploads new photos to GetPhotos server.
"""

import os
import sys
import time
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
SERVER_URL = "https://nasim-event-app-2025.onrender.com"
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.cr2', '.nef', '.arw', '.dng', '.raw'}

class PhotoUploader(FileSystemEventHandler):
    def __init__(self, api_key, event_id):
        self.api_key = api_key
        self.event_id = event_id
        self.uploaded_files = set()
        self.upload_count = 0
        
    def on_created(self, event):
        if event.is_directory:
            return
            
        file_path = event.src_path
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in SUPPORTED_EXTENSIONS:
            return
            
        if file_path in self.uploaded_files:
            return
            
        # Wait a moment for file to finish writing
        time.sleep(0.5)
        
        self.upload_photo(file_path)
        
    def upload_photo(self, file_path):
        try:
            filename = os.path.basename(file_path)
            print(f"📤 Uploading: {filename}...", end=" ", flush=True)
            
            with open(file_path, 'rb') as f:
                files = {'photo': (filename, f)}
                params = {'api_key': self.api_key}
                
                response = requests.post(
                    f"{SERVER_URL}/api/camera/upload",
                    files=files,
                    params=params,
                    data={'event_id': self.event_id},
                    timeout=60
                )
                
            if response.status_code == 201:
                self.uploaded_files.add(file_path)
                self.upload_count += 1
                print(f"✅ Done! (Total: {self.upload_count})")
            else:
                print(f"❌ Failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

def get_api_key():
    """Generate or get API key."""
    print("\n📷 GetPhotos Desktop Live Uploader")
    print("=" * 40)
    
    api_key = input("\nEnter your API key (or press Enter to generate): ").strip()
    
    if not api_key:
        print("\nGenerating new API key...")
        name = input("Your name: ").strip() or "Photographer"
        event_id = input("Event ID: ").strip()
        
        try:
            response = requests.post(
                f"{SERVER_URL}/api/camera/key/generate",
                json={
                    "admin_password": "getphotos2025",
                    "photographer_name": name,
                    "event_id": int(event_id) if event_id else None
                }
            )
            
            if response.status_code == 201:
                data = response.json()
                api_key = data['api_key']
                print(f"\n✅ API Key generated: {api_key}")
                print("   (Save this key for future use!)")
            else:
                print(f"❌ Failed to generate key: {response.text}")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
            
    return api_key

def main():
    print("""
    ╔═══════════════════════════════════════════╗
    ║     📸 GetPhotos Live Uploader v1.0       ║
    ║   Automatic Photo Upload for Events       ║
    ╚═══════════════════════════════════════════╝
    """)
    
    # Get API key
    api_key = get_api_key()
    
    # Get event ID
    event_id = input("\nEvent ID to upload to: ").strip()
    if not event_id:
        print("❌ Event ID is required!")
        sys.exit(1)
    
    # Get folder to watch
    print("\nEnter the folder path to watch for new photos.")
    print("(This is where your camera imports photos to)")
    watch_folder = input("Folder path: ").strip()
    
    if not os.path.isdir(watch_folder):
        print(f"❌ Folder not found: {watch_folder}")
        sys.exit(1)
    
    # Start watching
    print(f"\n🔍 Watching folder: {watch_folder}")
    print(f"📤 Uploading to Event #{event_id}")
    print("\n" + "=" * 40)
    print("Drop photos into the folder to upload them!")
    print("Press Ctrl+C to stop.\n")
    
    event_handler = PhotoUploader(api_key, event_id)
    observer = Observer()
    observer.schedule(event_handler, watch_folder, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(f"\n\n📊 Upload Summary:")
        print(f"   Total photos uploaded: {event_handler.upload_count}")
        print("   Goodbye! 👋")
        
    observer.join()

if __name__ == "__main__":
    main()
