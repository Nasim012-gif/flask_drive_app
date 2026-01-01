"""
Cleanup Service for GetPhotos
Runs hourly to check for expired events and delete photos from Google Drive.
"""

import os
import sys
import logging
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import events_db
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = get_config()


def refresh_google_access_token(refresh_token):
    """Get a new access token using refresh token."""
    try:
        from google.auth.transport.requests import Request
        
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
        )
        
        # Refresh the token
        creds.refresh(Request())
        return creds.token
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        return None


def delete_drive_folder(access_token, folder_id):
    """Delete a folder and all its contents from Google Drive."""
    try:
        creds = Credentials(token=access_token)
        service = build('drive', 'v3', credentials=creds)
        
        # List all files in the folder
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        logger.info(f"Found {len(files)} files in folder {folder_id}")
        
        # Delete each file
        for file in files:
            try:
                service.files().delete(fileId=file['id']).execute()
                logger.info(f"Deleted file: {file['name']}")
            except HttpError as e:
                logger.error(f"Failed to delete file {file['name']}: {e}")
        
        # Delete the folder itself
        service.files().delete(fileId=folder_id).execute()
        logger.info(f"Deleted folder: {folder_id}")
        
        return True
    except HttpError as e:
        logger.error(f"HTTP error deleting folder {folder_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting folder {folder_id}: {e}")
        return False


def cleanup_expired_events():
    """Main cleanup function - runs every hour."""
    logger.info("=" * 50)
    logger.info("Starting cleanup service...")
    logger.info(f"Current time: {datetime.now()}")
    
    # Initialize database
    events_db.init_db()
    
    # Get all expired events
    expired_events = events_db.get_expired_events()
    logger.info(f"Found {len(expired_events)} expired events")
    
    if not expired_events:
        logger.info("No expired events to clean up")
        return
    
    # Process each expired event
    for event in expired_events:
        event_id = event['id']
        event_name = event['name']
        folder_id = event['drive_folder_id']
        refresh_token = event['photographer_refresh_token']
        
        logger.info(f"Processing event {event_id}: {event_name}")
        
        if not folder_id:
            logger.warning(f"Event {event_id} has no Drive folder ID, skipping")
            events_db.mark_event_deleted(event_id)
            continue
        
        if not refresh_token:
            logger.warning(f"Event {event_id} has no refresh token, skipping")
            events_db.mark_event_deleted(event_id)
            continue
        
        # Get fresh access token
        access_token = refresh_google_access_token(refresh_token)
        if not access_token:
            logger.error(f"Failed to get access token for event {event_id}")
            continue
        
        # Delete the Drive folder
        success = delete_drive_folder(access_token, folder_id)
        
        if success:
            # Mark event as deleted in database
            events_db.mark_event_deleted(event_id)
            logger.info(f"✓ Successfully cleaned up event {event_id}")
        else:
            logger.error(f"✗ Failed to clean up event {event_id}")
    
    logger.info("Cleanup service completed")
    logger.info("=" * 50)


if __name__ == '__main__':
    """Run cleanup when script is executed directly."""
    try:
        cleanup_expired_events()
    except Exception as e:
        logger.error(f"Fatal error in cleanup service: {e}")
        sys.exit(1)
