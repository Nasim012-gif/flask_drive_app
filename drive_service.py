"""
Google Drive API service wrapper.
Handles authentication and provides methods for Drive operations.
"""

import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io

from config import get_config

config = get_config()


def get_client_config():
    """
    Get client configuration from environment variables or file.
    Favors environment variables for security in production.
    """
    # Try environment variables first
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if client_id and client_secret:
        return {
            "web": {
                "client_id": client_id,
                "project_id": os.environ.get('GOOGLE_PROJECT_ID', 'event-admin-app'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": [config.REDIRECT_URI]
            }
        }
    
    # Fallback to file if it exists
    if os.path.exists(config.CREDENTIALS_FILE):
        with open(config.CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    
    return None


def get_credentials():
    """
    Get valid user credentials from storage.
    
    Returns:
        Credentials object or None if no valid credentials available.
    """
    creds = None
    
    # Load credentials from token file if it exists
    if os.path.exists(config.TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.SCOPES)
    
    # If credentials are invalid or don't exist, return None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save the refreshed credentials
                save_credentials(creds)
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                return None
        else:
            return None
    
    return creds


def save_credentials(creds):
    """
    Save credentials to token file.
    
    Args:
        creds: Credentials object to save.
    """
    with open(config.TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())


def get_authorization_url():
    """
    Generate the authorization URL for OAuth flow.
    
    Returns:
        tuple: (authorization_url, state)
    """
    client_config = get_client_config()
    if not client_config:
        raise ValueError("Google client configuration not found. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET or provide credentials.json")

    flow = Flow.from_client_config(
        client_config,
        scopes=config.SCOPES,
        redirect_uri=config.REDIRECT_URI
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return authorization_url, state


def exchange_code_for_credentials(code, state):
    """
    Exchange authorization code for credentials.
    
    Args:
        code: Authorization code from OAuth callback.
        state: State parameter for CSRF protection.
    
    Returns:
        Credentials object.
    """
    client_config = get_client_config()
    if not client_config:
        raise ValueError("Google client configuration not found.")

    flow = Flow.from_client_config(
        client_config,
        scopes=config.SCOPES,
        redirect_uri=config.REDIRECT_URI,
        state=state
    )
    
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    # Save credentials for future use
    save_credentials(creds)
    
    return creds


def get_drive_service():
    """
    Build and return Google Drive service.
    
    Returns:
        Google Drive service object or None if authentication fails.
    """
    creds = get_credentials()
    
    if not creds:
        return None
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building Drive service: {e}")
        return None


def list_files(service, page_size=10, query=None):
    """
    List files from Google Drive.
    
    Args:
        service: Google Drive service object.
        page_size: Number of files to return (default: 10).
        query: Optional query string to filter files.
    
    Returns:
        List of file metadata dictionaries.
    """
    try:
        # Build query parameters
        params = {
            'pageSize': page_size,
            'fields': 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink)'
        }
        
        if query:
            params['q'] = query
        
        # Execute API call
        results = service.files().list(**params).execute()
        files = results.get('files', [])
        
        return files
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []


def upload_file(service, file_path, file_name=None, mime_type=None, folder_id=None):
    """
    Upload a file to Google Drive.
    
    Args:
        service: Google Drive service object.
        file_path: Path to the file to upload.
        file_name: Name for the file in Drive (optional, defaults to original filename).
        mime_type: MIME type of the file (optional).
        folder_id: ID of parent folder (optional).
    
    Returns:
        Dictionary with file metadata or None if upload fails.
    """
    try:
        # Use original filename if not provided
        if not file_name:
            file_name = os.path.basename(file_path)
        
        # File metadata
        file_metadata = {'name': file_name}
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Create media upload
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        
        # Upload file
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, mimeType, size, webViewLink'
        ).execute()
        
        return file
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def download_file(service, file_id):
    """
    Download a file from Google Drive.
    
    Args:
        service: Google Drive service object.
        file_id: ID of the file to download.
    
    Returns:
        tuple: (file_content as bytes, file_metadata) or (None, None) if download fails.
    """
    try:
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        
        # Download file content
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_buffer.seek(0)
        return file_buffer.getvalue(), file_metadata
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None, None


def delete_file(service, file_id):
    """
    Delete a file from Google Drive.
    
    Args:
        service: Google Drive service object.
        file_id: ID of the file to delete.
    
    Returns:
        Boolean indicating success.
    """
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


def search_files(service, query):
    """
    Search for files matching a query.
    
    Args:
        service: Google Drive service object.
        query: Search query (e.g., "name contains 'report'").
    
    Returns:
        List of file metadata dictionaries.
    """
    return list_files(service, page_size=100, query=query)


def sync_db_to_drive(service, local_db_path, drive_filename="events_db_persistence.db"):
    """
    Upload or update the local database file to Google Drive.
    """
    try:
        # Search for existing file
        query = f"name = '{drive_filename}' and trashed = false"
        results = search_files(service, query)
        
        media = MediaFileUpload(local_db_path, mimetype='application/x-sqlite3', resumable=True)
        
        if results:
            # Update existing file
            file_id = results[0]['id']
            service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            print(f"DEBUG: Updated existing DB on Drive (ID: {file_id})")
            return file_id
        else:
            # Create new file
            file_metadata = {'name': drive_filename}
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print(f"DEBUG: Created new DB on Drive (ID: {file['id']})")
            return file['id']
    except Exception as e:
        print(f"Error syncing DB to Drive: {e}")
        return None


def sync_db_from_drive(service, local_db_path, drive_filename="events_db_persistence.db"):
    """
    Download the database file from Google Drive if it exists.
    """
    try:
        query = f"name = '{drive_filename}' and trashed = false"
        results = search_files(service, query)
        
        if not results:
            print("DEBUG: No persistence DB found on Drive.")
            return False
            
        file_id = results[0]['id']
        request = service.files().get_media(fileId=file_id)
        
        with io.FileIO(local_db_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        
        print(f"DEBUG: Successfully downloaded DB from Drive (ID: {file_id})")
        return True
    except Exception as e:
        print(f"Error syncing DB from Drive: {e}")
        return False


def get_or_create_folder(service, folder_name, parent_id=None):
    """
    Find or create a folder in Google Drive.
    """
    try:
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        results = search_files(service, query)
        if results:
            return results[0]['id']
            
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        file = service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')
    except Exception as e:
        print(f"Error getting/creating folder {folder_name}: {e}")
        return None


def sync_photo_to_drive(service, file_path, event_id):
    """
    Upload a photo to Drive under a specific event folder.
    """
    try:
        # 1. Get/Create "Event Photos" root folder
        root_folder_id = get_or_create_folder(service, "Event Photos Persistence")
        if not root_folder_id:
            return None
            
        # 2. Get/Create folder for this specific event
        event_folder_id = get_or_create_folder(service, f"Event_{event_id}", parent_id=root_folder_id)
        if not event_folder_id:
            return None
            
        # 3. Upload the photo
        file_name = os.path.basename(file_path)
        # Check if already exists to avoid duplicates
        query = f"name = '{file_name}' and '{event_folder_id}' in parents and trashed = false"
        results = search_files(service, query)
        
        if results:
            return results[0]['id']
            
        result = upload_file(service, file_path, file_name=file_name, folder_id=event_folder_id)
        return result.get('id') if result else None
    except Exception as e:
        print(f"Error syncing photo {file_path} to Drive: {e}")
        return None


def download_photo_from_drive(service, filename, event_id, target_path):
    """
    Find and download a photo from its event folder on Drive.
    """
    try:
        root_folder_id = get_or_create_folder(service, "Event Photos Persistence")
        if not root_folder_id:
            return False
            
        event_folder_id = get_or_create_folder(service, f"Event_{event_id}", parent_id=root_folder_id)
        if not event_folder_id:
            return False
            
        query = f"name = '{filename}' and '{event_folder_id}' in parents and trashed = false"
        results = search_files(service, query)
        
        if not results:
            return False
            
        file_id = results[0]['id']
        request = service.files().get_media(fileId=file_id)
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with io.FileIO(target_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        return True
    except Exception as e:
        print(f"Error downloading photo {filename} from Drive: {e}")
        return False
