# GetPhotos Desktop Live Uploader 📷⚡

**Automatically upload photos to GetPhotos as you shoot!**

This app watches a folder on your computer. When new photos appear (from your camera), it instantly uploads them to GetPhotos.

## 📦 Installation

1. **Make sure you have Python 3.8+**

2. **Install dependencies:**
```bash
cd desktop_uploader
pip install -r requirements.txt
```

## 🚀 How to Use

1. **Run the app:**
```bash
python live_uploader.py
```

2. **Enter your API key** (or generate a new one)

3. **Enter the Event ID** you want to upload to

4. **Enter the folder path** where your camera saves photos

5. **Start shooting!** Photos will upload automatically ⚡

## 📷 Camera Setup

### Option 1: Camera USB Tethering
- Connect camera to laptop via USB
- Set camera to "Tether Mode" or "PC Remote"
- Photos save directly to laptop folder

### Option 2: SD Card Reader
- Use a card reader connected to laptop
- Point the app at the SD card folder

### Option 3: Camera WiFi → Phone → Laptop
- Camera sends to phone app
- Phone auto-syncs to laptop folder (via Dropbox/Google Drive)
- Desktop app watches that folder

## ⚡ Performance

- Upload time: **2-3 seconds per photo**
- Supported formats: JPG, PNG, CR2, NEF, ARW, DNG, RAW
- Works with any camera that can save to a folder!

## 🔑 API Key

Your API key is generated the first time you run the app. **Save it!**

You can also pre-generate one:
```bash
curl -X POST https://nasim-event-app-2025.onrender.com/api/camera/key/generate \
  -H "Content-Type: application/json" \
  -d '{"admin_password":"getphotos2025","photographer_name":"YourName","event_id":1}'
```

## 💡 Tips

- Keep the laptop plugged in (WiFi + uploads use battery)
- Use 5GHz WiFi for faster uploads
- Upload JPEG instead of RAW for speed (3MB vs 30MB)
