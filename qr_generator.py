"""
QR Code generator for events.
"""

import qrcode
import os
from PIL import Image

from config import get_config

config = get_config()
QR_CODES_DIR = config.QR_CODES_DIR

def ensure_qr_directory():
    """Ensure the QR codes directory exists."""
    if not os.path.exists(QR_CODES_DIR):
        os.makedirs(QR_CODES_DIR)


def generate_qr_code(data, filename, size=300):
    """
    Generate a QR code for the given data.
    
    Args:
        data: The data to encode (usually a URL)
        filename: Filename to save the QR code
        size: Size of the QR code image in pixels
    
    Returns:
        Path to the saved QR code image
    """
    ensure_qr_directory()
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,  # controls the size of the QR code
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Resize to desired size
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Save image
    filepath = os.path.join(QR_CODES_DIR, filename)
    img.save(filepath)
    
    return filepath


def generate_event_qr(event_id, base_url='https://192.168.1.100:5000'):
    """
    Generate a QR code for an event.
    
    Args:
        event_id: ID of the event
        base_url: Base URL for the application
    
    Returns:
        Path to the QR code image
    """
    event_url = f"{base_url}/event/{event_id}"
    filename = f"event_{event_id}.png"
    return generate_qr_code(event_url, filename)


def delete_qr_code(filepath):
    """Delete a QR code file."""
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
