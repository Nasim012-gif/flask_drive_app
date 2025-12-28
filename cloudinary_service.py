"""
Cloudinary service for photo storage.
Provides upload, delete, and storage tracking functionality.
"""

import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)


def is_configured():
    """Check if Cloudinary is configured."""
    return all([
        os.environ.get('CLOUDINARY_CLOUD_NAME'),
        os.environ.get('CLOUDINARY_API_KEY'),
        os.environ.get('CLOUDINARY_API_SECRET')
    ])


def upload_photo(file_path, user_id, event_id, filename=None):
    """
    Upload a photo to Cloudinary.
    
    Args:
        file_path: Path to the local file
        user_id: User ID for folder organization
        event_id: Event ID for folder organization
        filename: Optional custom filename
        
    Returns:
        dict with url, public_id, bytes, or None if failed
    """
    if not is_configured():
        print("DEBUG: Cloudinary not configured, skipping upload")
        return None
        
    try:
        # Organize by user/event folders
        folder = f"getphotos/user_{user_id}/event_{event_id}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_path,
            folder=folder,
            resource_type="image",
            use_filename=True,
            unique_filename=True
        )
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'bytes': result['bytes'],
            'format': result['format'],
            'width': result.get('width'),
            'height': result.get('height')
        }
        
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


def delete_photo(public_id):
    """Delete a photo from Cloudinary."""
    if not is_configured():
        return False
        
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"Cloudinary delete error: {e}")
        return False


def get_user_usage(user_id):
    """
    Get storage usage for a user from Cloudinary.
    Note: This requires iterating through resources, which can be slow.
    For performance, we track storage in our database instead.
    """
    if not is_configured():
        return 0
        
    try:
        folder = f"getphotos/user_{user_id}"
        total_bytes = 0
        
        # Get all resources in user folder
        result = cloudinary.api.resources(
            type="upload",
            prefix=folder,
            max_results=500
        )
        
        for resource in result.get('resources', []):
            total_bytes += resource.get('bytes', 0)
            
        return total_bytes
        
    except Exception as e:
        print(f"Cloudinary usage check error: {e}")
        return 0


def delete_user_folder(user_id):
    """Delete all photos for a user."""
    if not is_configured():
        return False
        
    try:
        folder = f"getphotos/user_{user_id}"
        cloudinary.api.delete_resources_by_prefix(folder)
        return True
    except Exception as e:
        print(f"Cloudinary folder delete error: {e}")
        return False
