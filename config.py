"""
Configuration settings for the Flask Google Drive application.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Google Drive API settings
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # OAuth settings
    REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/auth/callback')
    
    # File paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Render specific persistent data path
    DATA_DIR = os.environ.get('RENDER_DATA_DIR', '/data') if os.environ.get('RENDER') else BASE_DIR
    
    CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
    TOKEN_FILE = os.path.join(DATA_DIR, 'token.json') # Token should survive redeploys
    DB_PATH = os.path.join(DATA_DIR, 'events.db')
    
    # Asset paths
    QR_CODES_DIR = os.path.join(BASE_DIR, 'static/qr_codes')
    EVENT_PHOTOS_DIR = os.path.join(BASE_DIR, 'static/event_photos')
    
    # Upload settings
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB max file size

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # In production, ensure SECRET_KEY is set via environment variable
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get the appropriate configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
