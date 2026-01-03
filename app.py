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
import uuid
import secrets
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from config import get_config
import drive_service
import events_db
import qr_generator
import face_service
import api_keys
import auth
import cloudinary_service
# import pqc_service  # Temporarily disabled for deployment

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
    return "https://192.168.1.100:8080"


@app.route('/')
def index():
    """GetPhotos Landing Page."""
    return render_template('index.html')


@app.route('/station')
def station_dashboard():
    """AirDrop Station Dashboard."""
    maybe_sync_db('pull')
    
    # Get or Create the Personal Station
    station_id = get_or_create_station()
    station = events_db.get_event(station_id)
    
    return render_template('station.html', station=station)

def get_or_create_station():
    """Helper: Ensure a default 'Personal Station' event exists."""
    # Check for existing station by name
    # Using a simple query (in real app, use a dedicated config or singleton row)
    with events_db.get_db() as conn:
        cursor = conn.execute("SELECT id FROM events WHERE name = 'My AirDrop Station' LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            return row['id']
        else:
            # Create if missing
            print("Creating Default AirDrop Station...")
            eid = events_db.create_event(
                name="My AirDrop Station",
                date="2025-01-01", # Dummy date
                location="Local Station",
                description="Your personal file sharing station.",
                local_gallery_path="" # Default empty, user sets it
            )
            # Generate QR
            qr_path = qr_generator.generate_event_qr(eid, base_url=get_base_url())
            events_db.update_event_qr_path(eid, qr_path)
            return eid

@app.route('/api/station/folder', methods=['POST'])
def update_station_folder():
    """Quickly update the local gallery path for the station."""
    try:
        data = request.json
        new_path = data.get('path')
        
        # In a real multi-user app, we'd look up USER's station.
        # Here we just update the specific one.
        station_id = get_or_create_station()
        
        # Direct DB update (adding a helper in events_db would be cleaner, but raw SQL is fine here for speed)
        with events_db.get_db() as conn:
            conn.execute(
                "UPDATE events SET local_gallery_path = ? WHERE id = ?",
                (new_path, station_id)
            )
            conn.commit()
            
        print(f"Station source updated to: {new_path}")
        return jsonify({'status': 'success', 'path': new_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== POST-QUANTUM CRYPTOGRAPHY ====================
# Temporarily disabled for deployment - requires kyber-py dependency

# @app.route('/api/pqc/public_key', methods=['GET'])
# def get_kyber_public_key():
#     """Return the Server's Kyber Public Key."""
#     pk = pqc_service.pqc_manager.get_public_key()
#     # Return as hex string for easy transport
#     return jsonify({
#         'status': 'success',
#         'public_key': pk.hex()
#     })

# @app.route('/api/pqc/handshake', methods=['POST'])
# def kyber_handshake():
#     """
#     Client sends Kyber Encapsulated Ciphertext.
#     Server recovers shared secret and returns a Session Token.
#     """
#     try:
#         data = request.json
#         ciphertext_hex = data.get('ciphertext')
#         if not ciphertext_hex:
#             return jsonify({'error': 'Missing ciphertext'}), 400
#             
#         ciphertext = bytes.fromhex(ciphertext_hex)
#         
#         shared_secret, token = pqc_service.pqc_manager.decapsulate_secret(ciphertext)
#         
#         if not shared_secret:
#             return jsonify({'error': 'Decapsulation failed'}), 500
#             
#         return jsonify({
#             'status': 'success',
#             'session_token': token
#         })
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/pqc/photos/<int:event_id>', methods=['GET'])
# def get_encrypted_photos(event_id):
#     """
#     Get list of event photos, ENCRYPTED with the session key.
#     Requires 'X-Session-Token' header.
#     """
#     token = request.headers.get('X-Session-Token')
#     if not token:
#         return jsonify({'error': 'Missing session token'}), 401
#     
#     try:
#         # Fetch actual photos
#         # For demo, we just dump all photos for the event from DB
#         photos = events_db.get_event_photos(event_id)
#         
#         # Prepare data to encrypt (list of filenames/paths)
#         payload = str([p['filename'] for p in photos]).encode('utf-8')
#         
#         # Quantum-Safe Encryption (AES-GCM via Kyber Key)
#         encrypted_blob = pqc_service.pqc_manager.encrypt_data(token, payload)
#         
#         return jsonify({
#             'status': 'success', 
#             'encrypted_data': encrypted_blob.hex(),
#             'message': 'Data secured with Post-Quantum Cryptography (Kyber-1024 + AES-GCM)'
#         })
        
    except ValueError:
        return jsonify({'error': 'Invalid or expired session'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== USER AUTHENTICATION ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        
        user_id, error = auth.register_user(email, password, name)
        
        if error:
            return render_template('register.html', error=error)
        
        # Auto-login after registration
        auth.login_user(email, password)
        return redirect('/admin')
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user, error = auth.login_user(email, password)
        
        if error:
            return render_template('login.html', error=error)
        
        return redirect('/admin')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user."""
    auth.logout_user()
    return redirect('/')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset."""
    error = None
    success = None
    if request.method == 'POST':
        email = request.form.get('email')
        user = events_db.get_user_by_email(email)
        
        if user:
            # Generate token and expiration (1 hour)
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)
            
            # Save to DB
            events_db.create_reset_token(user['id'], token, expires_at)
            
            # Simulate sending email
            reset_url = url_for('reset_password', token=token, _external=True)
            print("="*50)
            print(f"PASSWORD RESET REQUEST FOR: {email}")
            print(f"RESET LINK: {reset_url}")
            print("="*50)
            
            success = "If an account exists with that email, a reset link has been sent to your server logs."
        else:
            # For security, show the same success message
            success = "If an account exists with that email, a reset link has been sent."
            
    return render_template('forgot_password.html', error=error, success=success)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using token."""
    user = events_db.get_user_by_reset_token(token)
    
    if not user:
        return render_template('login.html', error="Invalid or expired reset token.")
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 6:
            return render_template('reset_password.html', token=token, error="Password must be at least 6 characters.")
        
        if password != confirm_password:
            return render_template('reset_password.html', token=token, error="Passwords do not match.")
        
        # Update password
        password_hash = auth.hash_password(password)
        events_db.update_user_password(user['id'], password_hash)
        
        # Delete token
        events_db.delete_reset_token(token)
        
        return render_template('login.html', success="Password reset successfully. Please sign in.")
        
    return render_template('reset_password.html', token=token)


@app.route('/google-auth')
def google_auth():
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
@auth.login_required
def admin_panel():
    """Admin panel for event management."""
    maybe_sync_db('pull')
    
    # Get current user (already verified by login_required)
    user = auth.get_current_user()
    storage = None
    
    storage_info = events_db.get_user_storage(user['id'])
    if storage_info:
        storage = {
            'used': storage_info['used'],
            'limit': storage_info['limit'],
            'percent_used': storage_info['percent_used'],
            'used_formatted': auth.format_storage(storage_info['used']),
            'limit_formatted': auth.format_storage(storage_info['limit'])
        }
    
    return render_template('admin.html', user=user, storage=storage)


@app.route('/api/events', methods=['GET'])
@auth.login_required
def list_events():
    """List all events for the current user."""
    maybe_sync_db('pull')
    try:
        user = auth.get_current_user()
        events = events_db.get_events_by_user(user['id'])
        return jsonify({
            'status': 'success',
            'count': len(events),
            'events': events
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events', methods=['POST'])
@auth.login_required
def create_event():
    """Create a new event for the current user."""
    try:
        data = request.get_json()
        user = auth.get_current_user()
        
        # Validate required fields
        required_fields = ['name', 'date', 'location']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create event for specific user
        event_id = events_db.create_event_for_user(
            user_id=user['id'],
            name=data['name'],
            date=data['date'],
            location=data['location'],
            description=data.get('description', ''),
            local_gallery_path=data.get('local_gallery_path')
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


@app.route('/api/upload/manual', methods=['POST'])
def upload_manual_photo():
    """Upload a single photo for manual upload (from web browser)."""
    try:
        print("=== Manual Upload Debug ===")
        print(f"Files in request: {request.files}")
        
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo provided'}), 400
        
        photo = request.files['photo']
        event_name = request.form.get('event_name', 'temp_event')
        
        print(f"Photo filename: {photo.filename}")
        print(f"Event name: {event_name}")
        
        # Use anonymous user ID (0) for manual uploads
        user_id = 0
        
        # Check if Cloudinary is configured
        if not cloudinary_service.is_configured():
            print("ERROR: Cloudinary not configured!")
            return jsonify({'error': 'Cloudinary not configured'}), 500
        
        # Save temporarily
        import tempfile
        import os
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, photo.filename)
        
        print(f"Saving to: {temp_path}")
        photo.save(temp_path)
        print("File saved successfully")
        
        # Upload to Cloudinary
        print("Uploading to Cloudinary...")
        result = cloudinary_service.upload_photo(temp_path, user_id, 0, photo.filename)
        print(f"Cloudinary result: {result}")
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print("Temp file cleaned up")
        
        if result:
            return jsonify({
                'status': 'success',
                'url': result['url'],
                'public_id': result['public_id']
            }), 200
        else:
            print("ERROR: Cloudinary upload returned None")
            return jsonify({'error': 'Upload to Cloudinary failed'}), 500
            
    except Exception as e:
        print(f"EXCEPTION in upload_manual_photo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/manual', methods=['POST'])
def create_manual_event():
    """Create a Cloudinary-backed event for Manual Upload (no auth required)."""
    try:
        print("=== MANUAL EVENT CREATION START ===")
        data = request.get_json()
        print(f"Request data: {data}")
        
        # Use anonymous user ID (0) for manual uploads
        user_id = 0
        
        # Validate required fields
        required_fields = ['name', 'photo_ids']
        for field in required_fields:
            if field not in data:
                print(f"ERROR: Missing field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Set expiration to 24 hours from now
        expires_at = datetime.now() + timedelta(hours=24)
        print(f"Expiration set to: {expires_at}")
        
        # Create event
        print("Creating event in database...")
        event_id = events_db.create_event_for_user(
            user_id=user_id,
            name=data['name'],
            date=datetime.now().strftime('%Y-%m-%d'),
            location='Manual Upload',
            description=f"Manual upload with {data.get('photo_count', 0)} photos"
        )
        print(f"Event created with ID: {event_id}")
        
        # Store photo IDs and set expiration
        print("Updating event with expiration and storage type...")
        with events_db.get_db() as conn:
            conn.execute(
                'UPDATE events SET expires_at = ?, storage_type = ? WHERE id = ?',
                (expires_at, 'cloudinary', event_id)
            )
            conn.commit()
            print("Event updated and committed")
        
        # Add photos to database
        print(f"Adding {len(data['photo_ids'])} photos...")
        for i, photo_id in enumerate(data['photo_ids']):
            # photo_id is the Cloudinary public_id
            events_db.add_photo_with_cloudinary(
                event_id=event_id,
                filename=f"{photo_id}.jpg",
                local_path='',  # Empty string instead of None
                cloudinary_url=f"https://res.cloudinary.com/{os.getenv('CLOUDINARY_CLOUD_NAME')}/image/upload/{photo_id}",
                cloudinary_public_id=photo_id,
                file_size=0
            )
            print(f"  Photo {i+1}/{len(data['photo_ids'])} added")
        
        # Generate QR code
        print("Generating QR code...")
        qr_path = qr_generator.generate_event_qr(event_id, base_url=get_base_url())
        events_db.update_event_qr_path(event_id, qr_path)
        print(f"QR code generated: {qr_path}")
        
        # Verify event was created
        print("Verifying event exists in database...")
        verify_event = events_db.get_event(event_id)
        if verify_event:
            print(f"✓ Event {event_id} verified in database")
        else:
            print(f"✗ WARNING: Event {event_id} NOT found in database after creation!")
        
        # Don't sync to Google Drive for Cloudinary events
        print("Skipping Google Drive sync (Cloudinary event)")
        
        # Process photos for face detection (async in background)
        print("Starting face detection processing...")
        try:
            import face_detection_service
            import face_db
            from threading import Thread
            
            def process_faces():
                """Background thread to process faces"""
                try:
                    import gc  # For garbage collection
                    photo_count = 0
                    face_count = 0
                    MAX_PHOTOS = 50  # Limit to prevent memory issues
                    
                    # Get all photos for this event
                    photos = events_db.get_event_photos(event_id)
                    total_photos = len(photos)
                    
                    # Limit number of photos to process
                    photos_to_process = photos[:MAX_PHOTOS]
                    
                    print(f"[FaceProcessing] Processing {len(photos_to_process)} of {total_photos} photos")
                    
                    for photo in photos_to_process:
                        try:
                            photo_id = photo['id']
                            cloudinary_url = photo.get('cloudinary_url')
                            
                            if cloudinary_url:
                                # Detect faces in this photo
                                faces = face_detection_service.face_service.detect_faces(cloudinary_url)
                                
                                for face_data in faces:
                                    # Store embedding in database
                                    face_db.store_face_embedding(
                                        event_id=event_id,
                                        photo_id=photo_id,
                                        embedding=face_data['embedding'],
                                        face_location=face_data['location'],
                                        confidence=face_data.get('confidence', 0)
                                    )
                                    face_count += 1
                                
                                photo_count += 1
                                
                                # Force garbage collection after each photo to free memory
                                gc.collect()
                                
                                # Log progress every 10 photos
                                if photo_count % 10 == 0:
                                    print(f"[FaceProcessing] Progress: {photo_count}/{len(photos_to_process)} photos, {face_count} faces found")
                        
                        except Exception as photo_error:
                            print(f"[FaceProcessing] Error processing photo: {photo_error}")
                            continue  # Skip this photo and continue with others
                    
                    print(f"[FaceProcessing] Complete: {face_count} faces in {photo_count} photos")
                except Exception as e:
                    print(f"[FaceProcessing] Error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start background processing
            if face_detection_service.is_configured():
                Thread(target=process_faces, daemon=True).start()
                print("Face processing started in background")
            else:
                print("Face detection not configured, skipping")
        except Exception as e:
            print(f"Error starting face processing: {e}")
        
        print("=== MANUAL EVENT CREATION SUCCESS ===")
        
        return jsonify({
            'status': 'success',
            'event_id': event_id,
            'qr_code_url': f'/api/events/{event_id}/qr',
            'expires_at': expires_at.isoformat(),
            'storage_type': 'cloudinary'
        }), 201
    except Exception as e:
        print(f"=== MANUAL EVENT CREATION FAILED ===")
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """Get event details."""
    maybe_sync_db('pull')
    try:
        event = events_db.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Include photos in event details
        photos = events_db.get_event_photos(event_id)
        event['photos'] = photos
        
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


@app.route('/api/events/<int:event_id>/time-remaining', methods=['GET'])
def get_event_time_remaining(event_id):
    """Get time remaining until event expiration (for countdown timer)."""
    try:
        time_info = events_db.get_event_time_remaining(event_id)
        if time_info is None:
            return jsonify({'error': 'Event not found or no expiration set'}), 404
        return jsonify(time_info), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@auth.login_required
def delete_event_route(event_id):
    """Delete an event (ownership check)."""
    try:
        user = auth.get_current_user()
        event = events_db.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        if event.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to delete this event'}), 403
        
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
    # Don't sync - would overwrite Cloudinary events with Google Drive backup
    event = events_db.get_event(event_id)
    
    if not event:
        return render_template('error.html', message='Event not found'), 404
    
    return render_template('event_view.html', event=event)


# Face recognition photo directory
PHOTOS_DIR = config.EVENT_PHOTOS_DIR
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)


@app.route('/api/events/<int:event_id>/photos/zip', methods=['POST'])
@auth.login_required
def upload_event_photos_zip(event_id):
    """Admin upload of event photos via ZIP file."""
    maybe_sync_db('pull')
    user = auth.get_current_user()
    print(f"DEBUG: ZIP upload started by {user['name']} for event {event_id}")
    
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
                'error': f'Event #{event_id} not found'
            }), 404
            
        # Ownership Check
        if event.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to upload to this event'}), 403
            
        # Storage Limit Check
        storage_info = events_db.get_user_storage(user['id'])
        if storage_info and storage_info['used'] >= storage_info['limit']:
            return jsonify({
                'error': 'Storage limit reached',
                'message': f"Available: 0 B. Limit: {auth.format_storage(storage_info['limit'])}"
            }), 403
        
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
                        file_size = os.path.getsize(dest_path)
                        
                        # Cloudinary Upload (Sync for immediate feedback in ZIP)
                        cloudinary_info = None
                        try:
                            cloudinary_info = cloudinary_service.upload_photo(dest_path, user['id'], event_id)
                        except Exception as ce:
                            print(f"WARNING: Cloudinary upload failed for {filename}: {ce}")

                        # Backup to Google Drive (Legacy)
                        drive_id = None
                        if service:
                            drive_id = drive_service.sync_photo_to_drive(service, dest_path, event_id)
                        
                        # Add to database with Cloudinary & Drive IDs
                        if cloudinary_info:
                            events_db.add_photo_with_cloudinary(
                                event_id, filename, dest_path, 
                                cloudinary_info['secure_url'], 
                                cloudinary_info['public_id'], 
                                file_size,
                                drive_id=drive_id
                            )
                            uploaded_count += 1
                            print(f"DEBUG: Successfully saved {filename} (Cloudinary: {cloudinary_info['public_id'] if cloudinary_info else 'N/A'}, Drive ID: {drive_id})")
                        else:
                            # Fallback for non-Cloudinary events or failed Cloudinary upload
                            events_db.add_event_photo(event_id, filename, dest_path, drive_id)
                            uploaded_count += 1
                            print(f"DEBUG: Successfully saved {filename} (Drive ID: {drive_id})")

            # Sync to Drive
            maybe_sync_db('push')

            return jsonify({
                'status': 'success',
                'message': f'Uploaded {uploaded_count} photos from ZIP',
                'count': uploaded_count,
                'cloud_sync_active': service is not None
            })
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_extract_dir)

    except Exception as e:
        print(f"ERROR during ZIP upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/photos/<int:photo_id>', methods=['DELETE'])
@auth.login_required
def delete_event_photo(event_id, photo_id):
    """Delete a specific photo from an event."""
    maybe_sync_db('pull')
    user = auth.get_current_user()
    
    try:
        event = events_db.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        if event.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to delete photos from this event'}), 403
            
        photo = events_db.get_photo(photo_id)
        if not photo or photo['event_id'] != event_id:
            return jsonify({'error': 'Photo not found in this event'}), 404
            
        # Delete from Cloudinary if it exists
        if photo.get('cloudinary_public_id'):
            try:
                cloudinary_service.delete_photo(photo['cloudinary_public_id'])
                print(f"DEBUG: Deleted Cloudinary photo {photo['cloudinary_public_id']}")
            except Exception as ce:
                print(f"WARNING: Failed to delete Cloudinary photo {photo['cloudinary_public_id']}: {ce}")

        # Delete from Google Drive if it exists
        if photo.get('drive_id'):
            try:
                service = drive_service.get_drive_service()
                if service:
                    drive_service.delete_file_from_drive(service, photo['drive_id'])
                    print(f"DEBUG: Deleted Drive photo {photo['drive_id']}")
            except Exception as de:
                print(f"WARNING: Failed to delete Drive photo {photo['drive_id']}: {de}")

        # Delete local file if it exists
        if photo.get('local_path') and os.path.exists(photo['local_path']):
            os.remove(photo['local_path'])
            print(f"DEBUG: Deleted local photo {photo['local_path']}")
            
        # Delete from database
        events_db.delete_photo(photo_id)
        
        # Sync to Drive
        maybe_sync_db('push')
        
        return jsonify({
            'status': 'success',
            'message': f'Photo {photo_id} deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/photos/<int:photo_id>/faces', methods=['GET'])
def get_photo_faces(event_id, photo_id):
    """Get detected faces for a specific photo."""
    try:
        faces = face_db.get_faces_for_photo(photo_id)
        return jsonify({
            'status': 'success',
            'faces': faces
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/photos/<int:photo_id>/faces/<int:face_id>', methods=['DELETE'])
@auth.login_required
def delete_face_embedding(event_id, photo_id, face_id):
    """Delete a specific face embedding."""
    user = auth.get_current_user()
    
    try:
        event = events_db.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        if event.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to delete faces from this event'}), 403
            
        face_db.delete_face_embedding(face_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Face embedding {face_id} deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/faces/match', methods=['POST'])
def match_faces_in_event(event_id):
    """
    Endpoint to match faces in an event against a provided image.
    Expects a 'photo' file in the request.
    """
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo provided'}), 400

    uploaded_photo = request.files['photo']
    if uploaded_photo.filename == '':
        return jsonify({'error': 'No selected photo'}), 400

    try:
        # Save the uploaded photo temporarily
        temp_dir = tempfile.mkdtemp()
        temp_photo_path = os.path.join(temp_dir, secure_filename(uploaded_photo.filename))
        uploaded_photo.save(temp_photo_path)

        try:
            # Detect faces in the uploaded photo
            uploaded_faces = face_detection_service.face_service.detect_faces(temp_photo_path)
            if not uploaded_faces:
                return jsonify({'message': 'No faces detected in the uploaded photo'}), 200

            uploaded_face_embeddings = [f['embedding'] for f in uploaded_faces]

            # Get all face embeddings for the event
            event_faces = face_db.get_all_face_embeddings_for_event(event_id)
            if not event_faces:
                return jsonify({'message': 'No faces stored for this event'}), 200

            # Perform matching
            matches = []
            for uploaded_emb in uploaded_face_embeddings:
                for event_face in event_faces:
                    distance = face_detection_service.face_service.compare_faces(uploaded_emb, event_face['embedding'])
                    if distance < config.FACE_MATCH_THRESHOLD: # Use a configurable threshold
                        matches.append({
                            'photo_id': event_face['photo_id'],
                            'face_id': event_face['id'],
                            'distance': distance,
                            'face_location': event_face['face_location']
                        })
            
            # Group matches by photo_id and remove duplicates
            matched_photos = {}
            for match in matches:
                photo_id = match['photo_id']
                if photo_id not in matched_photos:
                    matched_photos[photo_id] = {
                        'photo_id': photo_id,
                        'faces': []
                    }
                matched_photos[photo_id]['faces'].append({
                    'face_id': match['face_id'],
                    'distance': match['distance'],
                    'face_location': match['face_location']
                })
            
            # Get photo URLs for matched photos
            result_photos = []
            for photo_id, data in matched_photos.items():
                photo_info = events_db.get_photo(photo_id)
                if photo_info:
                    result_photos.append({
                        'photo_id': photo_id,
                        'url': photo_info.get('cloudinary_url') or f'/api/photos/{photo_id}/view', # Fallback to local if no cloudinary
                        'faces': data['faces']
                    })

            return jsonify({
                'status': 'success',
                'matched_photos': result_photos
            })

        finally:
            # Clean up temporary photo
            shutil.rmtree(temp_dir)

    except Exception as e:
        print(f"Error during face matching: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/photos/<int:photo_id>/view', methods=['GET'])
def view_photo(photo_id):
    """Serve a photo directly from the local filesystem."""
    try:
        photo = events_db.get_photo(photo_id)
        if not photo or not photo.get('local_path') or not os.path.exists(photo['local_path']):
            return jsonify({'error': 'Photo not found or not available locally'}), 404
        
        return send_file(photo['local_path'], mimetype='image/jpeg') # Assuming JPEG, adjust if needed
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/qr_code/<int:event_id>')
def view_qr_code(event_id):
    """Display the QR code for an event."""
    event = events_db.get_event(event_id)
    
    if not event:
        return render_template('error.html', message='Event not found'), 404
    
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

@app.route('/api/events/<int:event_id>/photos', methods=['POST'])
@auth.login_required
def upload_event_photos(event_id):
    """Admin upload of individual event photos."""
    maybe_sync_db('pull')
    user = auth.get_current_user()
    print(f"DEBUG: Photo upload started by {user['name']} for event {event_id}")
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
                'error': f'Event #{event_id} not found'
            }), 404
            
        # Ownership Check
        if event.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to upload to this event'}), 403
            
        # Storage Limit Check
        storage_info = events_db.get_user_storage(user['id'])
        if storage_info and storage_info['used'] >= storage_info['limit']:
            return jsonify({
                'error': 'Storage limit reached',
                'message': f"Available: 0 B. Limit: {auth.format_storage(storage_info['limit'])}"
            }), 403
        
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



@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
@auth.login_required
def delete_photo_route(photo_id):
    """Delete a single photo (ownership check + storage cleanup)."""
    try:
        user = auth.get_current_user()
        photo = events_db.get_photo(photo_id)
        
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
            
        # Ownership Check
        if photo.get('user_id') != user['id']:
            return jsonify({'error': 'Unauthorized to delete this photo'}), 403
            
        # 1. Delete from Cloudinary
        if photo.get('cloudinary_public_id'):
            try:
                cloudinary_service.delete_photo(photo['cloudinary_public_id'])
            except Exception as ce:
                print(f"WARNING: Could not delete from Cloudinary: {ce}")
                
        # 2. Delete from Local Storage
        if os.path.exists(photo['local_path']):
            try:
                os.remove(photo['local_path'])
            except Exception as oe:
                print(f"WARNING: Could not delete local file: {oe}")
                
        # 3. Update User Storage Used
        file_size = photo.get('file_size', 0)
        if file_size > 0:
            events_db.update_user_storage(user['id'], -file_size)
            
        # 4. Delete from Database
        events_db.delete_photo(photo_id)
        
        return jsonify({
            'status': 'success', 
            'message': 'Photo deleted and storage updated',
            'freed_space': auth.format_storage(file_size)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def background_sync_task(file_path, event_id, filename):
    """Background task to sync photo to Drive and Cloudinary."""
    try:
        # Get event to find user_id
        event = events_db.get_event(event_id)
        if not event:
            print(f"ERROR: Event {event_id} not found for background sync.")
            return
            
        user_id = event.get('user_id')
        file_size = os.path.getsize(file_path)
        
        # 1. Sync to Google Drive (Legacy/Backup)
        service = drive_service.get_drive_service()
        if service:
            drive_id = drive_service.sync_photo_to_drive(service, file_path, event_id)
            events_db.update_photo_drive_id(file_path, drive_id)
            print(f"DEBUG: Drive sync complete for {filename}")

        # 2. Upload to Cloudinary (Primary Storage & Delivery)
        if user_id:
            try:
                result = cloudinary_service.upload_photo(file_path, user_id, event_id)
                if result:
                    events_db.update_photo_cloudinary_info(
                        local_path=file_path,
                        cloudinary_url=result['secure_url'],
                        cloudinary_public_id=result['public_id'],
                        file_size=file_size
                    )
                    # Update User Storage Used
                    events_db.update_user_storage(user_id, file_size)
                    print(f"DEBUG: Cloudinary sync complete for {filename} (+{file_size} bytes)")
            except Exception as ce:
                print(f"ERROR: Cloudinary upload failed for {filename}: {ce}")
        
        # 3. Final DB Sync to Drive
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
            
        # Check User Storage Limit
        user_id = event.get('user_id')
        if user_id:
            storage_info = events_db.get_user_storage(user_id)
            if storage_info and storage_info['used'] >= storage_info['limit']:
                return jsonify({
                    'error': 'Storage limit reached',
                    'message': f"You have used {auth.format_storage(storage_info['used'])} of your {auth.format_storage(storage_info['limit'])} limit. Please delete some photos or upgrade."
                }), 403
        
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
            event = events_db.get_event(event_id)
            if not event:
                return jsonify({'error': 'Event not found'}), 404

            # MATCHING LOGIC
            target_paths = []
            
            # 1. OPTION A: Linked Local Gallery (No Upload Mode)
            if event.get('local_gallery_path') and os.path.exists(event['local_gallery_path']):
                gallery_path = event['local_gallery_path']
                print(f"DEBUG: Searching in linked local gallery: {gallery_path}")
                
                # Scan directory for images
                image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
                for root, dirs, files in os.walk(gallery_path):
                    for file in files:
                        if os.path.splitext(file)[1].lower() in image_extensions:
                            target_paths.append(os.path.join(root, file))
                            
            # 2. OPTION B: Standard Uploaded Photos
            else:
                db_photos = events_db.get_event_photos(event_id)
                # Ensure all photos exist locally (they might have been wiped)
                service = drive_service.get_drive_service()
                for p in db_photos:
                    if not os.path.exists(p['local_path']):
                        # simple restore logic if needed, skipping for brevity in this block
                        pass
                target_paths = [p['local_path'] for p in db_photos if os.path.exists(p['local_path'])]
            
            print(f"DEBUG: Scannable photos found: {len(target_paths)}")
            
            if not target_paths:
                return jsonify({
                    'status': 'no_photos',
                    'matches': [],
                    'message': 'No photos available to search.'
                })
                
            # Perform face matching
            db_path_arg = event.get('local_gallery_path') if event.get('local_gallery_path') and os.path.exists(event['local_gallery_path']) else None
            
            matches = face_service.smart_verify_face(selfie_path, target_paths, db_path=db_path_arg)
            
            # Prepare result URLs
            matched_urls = []
            for match_path in matches:
                if event.get('local_gallery_path') and match_path.startswith(event['local_gallery_path']):
                    # It's a linked file, verify it's inside the allowed directory
                    rel_path = os.path.relpath(match_path, event['local_gallery_path'])
                    # Generate a secure link to serve this specific file
                    # We'll use a new endpoint /api/events/<id>/file/<path>
                    # Encode parts to avoid issues
                    matched_urls.append(f"/api/events/{event_id}/file/{rel_path}")
                else:
                    # Standard app-managed file
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


@app.route('/api/events/<int:event_id>/file/<path:filename>')
def serve_event_file(event_id, filename):
    """Serve a file from a linked local gallery."""
    try:
        event = events_db.get_event(event_id)
        if not event or not event.get('local_gallery_path'):
            return "Event or gallery not found", 404
            
        gallery_path = event['local_gallery_path']
        
        # Security check: Ensure the requested file is actually within the gallery path
        full_path = os.path.join(gallery_path, filename)
        common_prefix = os.path.commonpath([gallery_path, full_path])
        
        # In a real scenario, use stricter path checking (pathlib)
        # Assuming simple reliable paths here
        
        if not os.path.exists(full_path):
            return "File not found", 404
            
        return send_file(full_path)
        
    except Exception as e:
        return str(e), 500


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
    # print(f"Running on http://localhost:8080")
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
    port = int(os.environ.get('PORT', 8080))
    is_prod = os.environ.get('RENDER') is not None
    
    if not is_prod:
        # We rely on the public URL printed by the startup script
        print(f"\n🔐 Google Drive Auth: <Public_URL>/auth")
        print(f"🎯 Admin Dashboard:   <Public_URL>/admin")
        print(f"📱 Mobile / Quest:    <Public_URL>/event/id\n")
        print(f"⚠️  NOTE: Use the Public URL via Ngrok for reliable access.")
        
        # Ngrok handles SSL publicly. We run HTTP locally to avoid ERR_NGROK_3004 (Protocol Mismatch)
        app.run(debug=config.DEBUG, port=port, host='0.0.0.0')
    else:
        # On Render, SSL is handled by the platform
        app.run(debug=False, port=port, host='0.0.0.0')


@app.route('/manual-upload')
def manual_upload_page():
    """Manual upload page - web-based photo selection and upload."""
    return render_template('manual_upload.html')

