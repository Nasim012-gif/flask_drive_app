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
