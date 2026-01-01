import os
import sys
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import events_db
import cloudinary_service
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = get_config()


def delete_event_photos_from_cloudinary(event_id):
    """Delete all photos for an event from Cloudinary."""
    try:
        # Get all photos for the event
        photos = events_db.get_event_photos(event_id)
        logger.info(f"Found {len(photos)} photos for event {event_id}")
        
        # Delete each photo from Cloudinary
        for photo in photos:
            try:
                public_id = photo.get('cloudinary_public_id')
                if public_id:
                    cloudinary_service.delete_photo(public_id)
                    logger.info(f"Deleted photo: {public_id}")
            except Exception as e:
                logger.error(f"Failed to delete photo {public_id}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting photos for event {event_id}: {e}")
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
        
        logger.info(f"Processing event {event_id}: {event_name}")
        
        # Delete photos from Cloudinary
        success = delete_event_photos_from_cloudinary(event_id)
        
        if success:
            # Mark event as deleted in database
            events_db.mark_event_deleted(event_id)
            logger.info(f"✓ Successfully cleaned up event {event_id}")
        else:
            logger.error(f"✗ Failed to clean up event {event_id}")
    
    logger.info("Cleanup service completed")
    logger.info("=" * 50)


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
