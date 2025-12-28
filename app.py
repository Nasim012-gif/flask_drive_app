"""
Flask application for Google Drive API integration.
Provides RESTful endpoints for Drive file operations.
"""

from flask import Flask, request, jsonify, redirect, session, send_file, render_template
from flask_cors import CORS
import os
import tempfile
import zipfile
import shutil
import threading
from werkzeug.utils import secure_filename

from config import get_config
import drive_service
import events_db
import qr_generator
import face_service
import api_keys

# Initialize Flask app
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Enable CORS
CORS(app)

# Initialize database
events_db.init_db()

# Initialize API key manager for camera uploads
api_key_manager = api_keys.APIKeyManager(data_dir=config.DATA_DIR)

# Keep track of database sync status
_db_pulled = False

def maybe_sync_db(direction='pull', force=False):
    """Helper to sync database with Google Drive if authenticated."""
    # Only perform sync on production (Render)
    if not os.environ.get('RENDER'):
        return
        
    service = drive_service.get_drive_service()
    if not service:
        # Silently skip if not authenticated yet
        return
        
    global _db_pulled
    if direction == 'pull':
        if not _db_pulled or force:
            print(f"DEBUG: Pulling DB from Drive (force={force})...")
            if drive_service.sync_db_from_drive(service, config.DB_PATH):
                _db_pulled = True
    else:
        # direction is 'push'
        print("DEBUG: Pushing DB to Drive persistence...")
        drive_service.sync_db_to_drive(service, config.DB_PATH)

def get_base_url():
    """Helper to get the base URL for the application."""
    # Priority 1: Environment variable (useful for production)
    env_url = os.environ.get('BASE_URL')
    if env_url:
        return env_url.rstrip('/')
    
    # Priority 2: Use host from request if in a request context
    try:
        if request:
            return request.host_url.rstrip('/')
    except RuntimeError:
        pass
    
    # Priority 3: Default to IP-based local URL (for mobile local testing)
    return "https://192.168.1.100:5000"


@app.route('/')
def index():
    """Landing page."""
    maybe_sync_db('pull')
    return render_template('index.html')


@app.route('/auth')
def auth():
    """
    Initiate OAuth 2.0 authorization flow.
    Redirects user to Google's authorization page.
    """
    try:
        authorization_url, state = drive_service.get_authorization_url()
        session['state'] = state
        return redirect(authorization_url)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/auth/callback')
def auth_callback():
    """
    OAuth 2.0 callback handler.
    Exchanges authorization code for credentials.
    """
    try:
        # Verify state to prevent CSRF
        state = session.get('state')
        if not state or state != request.args.get('state'):
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        # Get authorization code
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'Authorization code not provided'}), 400
        
        # Exchange code for credentials
        drive_service.exchange_code_for_credentials(code, state)
        
        return jsonify({
            'status': 'success',
            'message': 'Authentication successful! You can now use the API.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/files', methods=['GET'])
def list_files():
    """
    List files from Google Drive.
    
    Query parameters:
        - page_size: Number of files to return (default: 10)
        - query: Optional search query
    """
    try:
        service = drive_service.get_drive_service()
        
        if not service:
            return jsonify({
                'error': 'Not authenticated. Please visit /auth to authenticate.'
            }), 401
        
        # Get query parameters
        page_size = request.args.get('page_size', 10, type=int)
        query = request.args.get('query', None)
        
        # List files
        files = drive_service.list_files(service, page_size=page_size, query=query)
        
        return jsonify({
            'status': 'success',
            'count': len(files),
            'files': files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a file to Google Drive.
    
    Form data:
        - file: File to upload (required)
        - name: Custom name for the file (optional)
        - folder_id: Parent folder ID (optional)
    """
    try:
        service = drive_service.get_drive_service()
        
        if not service:
            return jsonify({
                'error': 'Not authenticated. Please visit /auth to authenticate.'
            }), 401
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get optional parameters
        custom_name = request.form.get('name')
        folder_id = request.form.get('folder_id')
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(temp_path)
        
        try:
            # Upload to Drive
            uploaded_file = drive_service.upload_file(
                service,
                temp_path,
                file_name=custom_name or filename,
                mime_type=file.content_type,
                folder_id=folder_id
            )
            
            if uploaded_file:
                return jsonify({
                    'status': 'success',
                    'message': 'File uploaded successfully',
                    'file': uploaded_file
                })
            else:
                return jsonify({'error': 'Upload failed'}), 500
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """
    Download a file from Google Drive.
    
    Path parameters:
        - file_id: ID of the file to download
    """
    try:
        service = drive_service.get_drive_service()
        
        if not service:
            return jsonify({
                'error': 'Not authenticated. Please visit /auth to authenticate.'
            }), 401
        
        # Download file
        file_content, file_metadata = drive_service.download_file(service, file_id)
        
        if file_content is None:
            return jsonify({'error': 'File not found or download failed'}), 404
        
        # Create temporary file
        temp_path = os.path.join(tempfile.gettempdir(), file_metadata['name'])
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        # Send file
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=file_metadata['name'],
            mimetype=file_metadata.get('mimeType', 'application/octet-stream')
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/delete/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """
    Delete a file from Google Drive.
    
    Path parameters:
        - file_id: ID of the file to delete
    """
    try:
        service = drive_service.get_drive_service()
        
        if not service:
            return jsonify({
                'error': 'Not authenticated. Please visit /auth to authenticate.'
            }), 401
        
        # Delete file
        success = drive_service.delete_file(service, file_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'File {file_id} deleted successfully'
            })
        else:
            return jsonify({'error': 'Delete failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/search', methods=['GET'])
def search_files():
    """
    Search for files in Google Drive.
    
    Query parameters:
        - q: Search query (required)
    
    Example queries:
        - name contains 'report'
        - mimeType='application/pdf'
        - modifiedTime > '2023-01-01T00:00:00'
    """
    try:
        service = drive_service.get_drive_service()
        
        if not service:
            return jsonify({
                'error': 'Not authenticated. Please visit /auth to authenticate.'
            }), 401
        
        # Get query parameter
        query = request.args.get('q')
        
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        # Search files
        files = drive_service.search_files(service, query)
        
        return jsonify({
            'status': 'success',
            'count': len(files),
            'files': files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EVENT MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/admin')
def admin_panel():
    """Admin panel for event management."""
    maybe_sync_db('pull')
    return render_template('admin.html')


@app.route('/api/events', methods=['GET'])
def list_events():
    """List all events."""
    maybe_sync_db('pull')
    try:
        events = events_db.get_all_events()
        return jsonify({
            'status': 'success',
            'count': len(events),
            'events': events
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events', methods=['POST'])
def create_event():
    """Create a new event."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'date', 'location']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create event
        event_id = events_db.create_event(
            name=data['name'],
            date=data['date'],
            location=data['location'],
            description=data.get('description', '')
        )
        
        # Generate QR code
        qr_path = qr_generator.generate_event_qr(event_id, base_url=get_base_url())
        events_db.update_event_qr_path(event_id, qr_path)
        
        # Sync to Drive
        maybe_sync_db('push')
        
        return jsonify({
            'status': 'success',
            'message': 'Event created successfully',
            'event_id': event_id,
            'qr_code_url': f'/api/events/{event_id}/qr'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """Get event details."""
    maybe_sync_db('pull')
    try:
        event = events_db.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        return jsonify({
            'status': 'success',
            'event': event
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/qr', methods=['GET'])
def get_event_qr(event_id):
    """Get QR code for an event."""
    maybe_sync_db('pull')
    try:
        event = events_db.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Check if QR code exists, generate if not
        if not event['qr_code_path'] or not os.path.exists(event['qr_code_path']):
            qr_path = qr_generator.generate_event_qr(event_id, base_url=get_base_url())
            events_db.update_event_qr_path(event_id, qr_path)
        else:
            qr_path = event['qr_code_path']
        
        return send_file(qr_path, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event_route(event_id):
    """Delete an event."""
    try:
        event = events_db.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Delete QR code file
        if event['qr_code_path']:
            qr_generator.delete_qr_code(event['qr_code_path'])
        
        # Delete event from database
        events_db.delete_event(event_id)
        
        # Sync to Drive
        maybe_sync_db('push')
        
        return jsonify({
            'status': 'success',
            'message': f'Event {event_id} deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/event/<int:event_id>')
def view_event(event_id):
    """Public event details page (for QR code redirect)."""
    maybe_sync_db('pull')
    event = events_db.get_event(event_id)
    
    if not event:
        return render_template('error.html', message='Event not found'), 404
    
    return render_template('event_view.html', event=event)


# ============================================================================
# FACE RECOGNITION ENDPOINTS
# ============================================================================

# Face recognition photo directory
PHOTOS_DIR = config.EVENT_PHOTOS_DIR
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

@app.route('/api/events/<int:event_id>/photos', methods=['POST'])
def upload_event_photos(event_id):
    """Admin upload of event photos."""
    maybe_sync_db('pull')
    print(f"DEBUG: Photo upload started for event {event_id}")
    try:
        # Check if event exists
        event = events_db.get_event(event_id)
        if not event:
            # Fallback: Maybe the DB isn't synced in this worker?
            print(f"DEBUG: Event {event_id} not found locally. Forcing a Drive pull...")
            maybe_sync_db('pull', force=True)
            event = events_db.get_event(event_id)
            
        if not event:
            print(f"DEBUG: Event {event_id} STILL NOT found after force pull. Current database path: {config.DB_PATH}")
            return jsonify({
                'error': f'Event #{event_id} not found',
                'details': 'The event might have been deleted or the database sync failed. Visit /admin and log in again.'
            }), 404
        
        print(f"DEBUG: Found event: {event['name']}")

        if 'photos' not in request.files:
            return jsonify({'error': 'No photos provided'}), 400

        photos = request.files.getlist('photos')
        print(f"DEBUG: Received {len(photos)} photos")
        uploaded_count = 0
        
        # Ensure event directory exists
        event_dir = os.path.join(PHOTOS_DIR, str(event_id))
        if not os.path.exists(event_dir):
            os.makedirs(event_dir)

        # Get Drive service for backup
        service = drive_service.get_drive_service()

        for photo in photos:
            if photo.filename == '':
                continue
                
            filename = secure_filename(photo.filename)
            file_path = os.path.join(event_dir, filename)
            print(f"DEBUG: Saving photo {filename}")
            photo.save(file_path)
            
            # Backup to Google Drive
            drive_id = None
            if service:
                print(f"DEBUG: Syncing {filename} to Google Drive...")
                drive_id = drive_service.sync_photo_to_drive(service, file_path, event_id)
            
            # Add to database
            events_db.add_event_photo(event_id, filename, file_path, drive_id)
            uploaded_count += 1
            print(f"DEBUG: Successfully saved {filename} (Drive ID: {drive_id})")

        # Sync to Drive
        maybe_sync_db('push')

        return jsonify({
            'status': 'success',
            'message': f'Uploaded {uploaded_count} photos',
            'count': uploaded_count,
            'cloud_sync_active': service is not None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/photos/zip', methods=['POST'])
def upload_event_photos_zip(event_id):
    """Admin upload of event photos via ZIP file."""
    maybe_sync_db('pull')
    print(f"DEBUG: ZIP upload started for event {event_id}")
    
    try:
        # Check if event exists
        event = events_db.get_event(event_id)
        if not event:
            # Fallback: Maybe the DB isn't synced in this worker?
            print(f"DEBUG: Event {event_id} not found locally. Forcing a Drive pull...")
            maybe_sync_db('pull', force=True)
            event = events_db.get_event(event_id)
            
        if not event:
            return jsonify({
                'error': f'Event #{event_id} not found',
                'details': 'The event might have been deleted or the database sync failed.'
            }), 404
        
        if 'zipfile' not in request.files:
            return jsonify({'error': 'No ZIP file provided'}), 400

        zip_file = request.files['zipfile']
        
        if not zip_file.filename.endswith('.zip'):
            return jsonify({'error': 'File must be a ZIP archive'}), 400
        
        print(f"DEBUG: Processing ZIP file: {zip_file.filename}")
        
        # Create temp directory for extraction
        temp_extract_dir = tempfile.mkdtemp()
        temp_zip_path = os.path.join(temp_extract_dir, 'upload.zip')
        
        try:
            # Save uploaded ZIP
            zip_file.save(temp_zip_path)
            
            # Extract ZIP
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            # Remove the ZIP file itself
            os.remove(temp_zip_path)
            
            # Find all image files
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
                              '.cr2', '.nef', '.arw', '.dng', '.raw', '.orf', '.rw2'}
            
            uploaded_count = 0
            event_dir = os.path.join(PHOTOS_DIR, str(event_id))
            if not os.path.exists(event_dir):
                os.makedirs(event_dir)
            
            # Get Drive service for backup
            service = drive_service.get_drive_service()
            
            # Walk through extracted files
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    file_lower = file.lower()
                    if any(file_lower.endswith(ext) for ext in image_extensions):
                        source_path = os.path.join(root, file)
                        filename = secure_filename(file)
                        
                        # Avoid duplicates
                        dest_path = os.path.join(event_dir, filename)
                        counter = 1
                        while os.path.exists(dest_path):
                            name, ext = os.path.splitext(filename)
                            filename = f"{name}_{counter}{ext}"
                            dest_path = os.path.join(event_dir, filename)
                            counter += 1
                        
                        # Copy file to event directory
                        shutil.copy2(source_path, dest_path)
                        print(f"DEBUG: Extracted and saved {filename}")
                        
                        # Backup to Google Drive
                        drive_id = None
                        if service:
                            drive_id = drive_service.sync_photo_to_drive(service, dest_path, event_id)
                        
                        # Add to database
                        events_db.add_event_photo(event_id, filename, dest_path, drive_id)
                        uploaded_count += 1
            
            print(f"DEBUG: Successfully extracted {uploaded_count} photos from ZIP")
            
            # Sync database to Drive
            maybe_sync_db('push')
            
            return jsonify({
                'status': 'success',
                'message': f'Extracted and uploaded {uploaded_count} photos from ZIP',
                'count': uploaded_count,
                'cloud_sync_active': service is not None
            })
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'ZIP processing failed: {str(e)}'}), 500


def background_sync_task(file_path, event_id, filename):
    """Background task to sync photo to Drive."""
    try:
        service = drive_service.get_drive_service()
        if service:
            drive_id = drive_service.sync_photo_to_drive(service, file_path, event_id)
            # Update DB with drive_id
            events_db.update_photo_drive_id(file_path, drive_id)
            print(f"DEBUG: Background sync complete for {filename}")
            
            # Push updated DB to Drive
            maybe_sync_db('push')
    except Exception as e:
        print(f"ERROR: Background sync failed for {filename}: {e}")


@app.route('/api/camera/upload', methods=['POST'])
def camera_upload():
    """Direct upload from camera WiFi. Requires API key authentication."""
    try:
        # Check for API key in header or query param
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({
                'error': 'Missing API key',
                'message': 'Include X-API-Key header or api_key query parameter'
            }), 401
        
        # Validate API key
        key_data = api_key_manager.validate_key(api_key)
        if not key_data:
            return jsonify({'error': 'Invalid or inactive API key'}), 403
        
        # Get event ID from key data or request
        event_id = key_data.get('event_id') or request.form.get('event_id')
        
        if not event_id:
            return jsonify({'error': 'No event_id specified'}), 400
        
        event_id = int(event_id)
        
        print(f"DEBUG: Camera upload from {key_data['photographer_name']} to event {event_id}")
        
        # Check if event exists
        event = events_db.get_event(event_id)
        if not event:
            return jsonify({'error': f'Event {event_id} not found'}), 404
        
        # Get uploaded file
        if 'photo' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No photo file in request'}), 400
        
        photo = request.files.get('photo') or request.files.get('file')
        
        if not photo or photo.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Save photo
        filename = secure_filename(photo.filename)
        event_dir = os.path.join(PHOTOS_DIR, str(event_id))
        
        if not os.path.exists(event_dir):
            os.makedirs(event_dir)
        
        # Handle duplicate filenames
        file_path = os.path.join(event_dir, filename)
        counter = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{counter}{ext}"
            file_path = os.path.join(event_dir, filename)
            counter += 1
        
        # Save file
        photo.save(file_path)
        print(f"DEBUG: Saved camera photo {filename}")
        
        # Add to database immediately (without drive_id for now)
        events_db.add_event_photo(event_id, filename, file_path, None)
        
        # Start background sync to Drive
        thread = threading.Thread(
            target=background_sync_task,
            args=(file_path, event_id, filename)
        )
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Photo received and processing in background',
            'filename': filename,
            'event_id': event_id,
            'photographer': key_data['photographer_name']
        }), 201
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/api/camera/key/generate', methods=['POST'])
def generate_api_key():
    """Generate a new API key for camera uploads. Admin only."""
    try:
        # Simple admin check (you can enhance this)
        admin_password = request.json.get('admin_password')
        if admin_password != os.environ.get('ADMIN_PASSWORD', 'getphotos2025'):
            return jsonify({'error': 'Unauthorized'}), 403
        
        photographer_name = request.json.get('photographer_name', 'Unknown')
        event_id = request.json.get('event_id')
        
        # Generate key
        api_key = api_key_manager.generate_key(photographer_name, event_id)
        
        return jsonify({
            'status': 'success',
            'api_key': api_key,
            'photographer_name': photographer_name,
            'event_id': event_id,
            'message': 'Configure this key in your camera WiFi settings'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/events/<int:event_id>/find_me', methods=['POST'])
def find_my_photos(event_id):
    """Guest face matching endpoint."""
    maybe_sync_db('pull')
    try:
        if 'selfie' not in request.files:
            return jsonify({'error': 'No selfie provided'}), 400

        selfie = request.files['selfie']
        
        # Save selfie temporarily
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_selfie:
            selfie.save(temp_selfie.name)
            selfie_path = temp_selfie.name

        try:
            # Get all photos for this event
            db_photos = events_db.get_event_photos(event_id)
            if not db_photos:
                return jsonify({'matches': []})

            # Ensure all photos exist locally (they might have been wiped)
            service = drive_service.get_drive_service()
            for p in db_photos:
                if not os.path.exists(p['local_path']):
                    print(f"DEBUG: Photo {p['filename']} missing locally. Attempting to restore from Drive...")
                    if service:
                        restored = drive_service.download_photo_from_drive(service, p['filename'], event_id, p['local_path'])
                        print(f"DEBUG: Restore result for {p['filename']}: {restored}")
                    else:
                        print(f"DEBUG: Skipping restore for {p['filename']} - Google service not authenticated.")

            # Extract local paths (only for files that actually exist)
            target_paths = [p['local_path'] for p in db_photos if os.path.exists(p['local_path'])]
            print(f"DEBUG: Scannable photos found: {len(target_paths)} of {len(db_photos)}")
            
            if not target_paths:
                print("DEBUG: No local photos found and restore failed.")
                return jsonify({
                    'status': 'no_photos',
                    'matches': [],
                    'message': 'No photos available on server. Try logging in to Google to restore them.'
                })
                
            # Perform face matching
            # Use smart_verify_face to handle group photos with super-resolution
            # This automatically enhances blurry group photos to find small faces
            matches = face_service.smart_verify_face(selfie_path, target_paths)
            
            # Filter results by photo count limit (optional) or score
            # DeepFace already handles threshold internally
            
            # Prepare result URLs
            matched_urls = []
            for match_path in matches:
                # Convert file path to URL
                # Path is like static/event_photos/1/photo.jpg
                # We want /static/event_photos/1/photo.jpg
                rel_path = os.path.relpath(match_path, app.root_path)
                matched_urls.append(f"/{rel_path}")

            return jsonify({
                'status': 'success',
                'matches': matched_urls,
                'count': len(matched_urls)
            })
            
        finally:
            # Clean up temp selfie
            if os.path.exists(selfie_path):
                os.remove(selfie_path)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Check if credentials file exists
    if not os.path.exists(config.CREDENTIALS_FILE):
        print("\n" + "="*70)
        print("WARNING: credentials.json not found!")
        print("Please follow the setup guide to obtain Google Cloud credentials.")
        print("See SETUP_GUIDE.md for detailed instructions.")
        print("="*70 + "\n")
    
    print(f"\nFlask Google Drive API + Event Management Server")
    print(f"Running on http://localhost:5000")
    print(f"\n📁 Google Drive API:")
    print(f"  GET  /              - Health check")
    print(f"  GET  /auth          - Authenticate with Google")
    print(f"  GET  /files         - List Drive files")
    print(f"  POST /upload        - Upload file to Drive")
    print(f"  GET  /download/<id> - Download file from Drive")
    print(f"  DELETE /delete/<id> - Delete file from Drive")
    print(f"  GET  /search        - Search Drive files")
    print(f"\n📅 Event Management:")
    print(f"  GET  /admin         - Admin panel")
    print(f"  GET  /api/events    - List all events")
    print(f"  POST /api/events    - Create new event")
    print(f"  GET  /api/events/<id>/qr - Get event QR code")
    print(f"  GET  /event/<id>    - View event details")
    # Production Startup
    port = int(os.environ.get('PORT', 5000))
    is_prod = os.environ.get('RENDER') is not None
    
    if not is_prod:
        print(f"\n🔐 To authenticate with Google Drive: https://localhost:{port}/auth")
        print(f"🎯 To manage events (Admin): https://localhost:{port}/admin")
        print(f"📱 For mobile devices (Guests): https://192.168.1.100:{port}/event/id\n")
        print(f"⚠️  NOTE: You will see a security warning. Click 'Advanced' -> 'Proceed' to continue.")
        # allow external connections with HTTPS locally
        app.run(debug=config.DEBUG, port=port, host='0.0.0.0', ssl_context=('cert.pem', 'key.pem'))
    else:
        # On Render, SSL is handled by the platform
        app.run(debug=False, port=port, host='0.0.0.0')
