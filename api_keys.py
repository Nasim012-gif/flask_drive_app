"""
API Key management for camera direct uploads.
Each photographer gets a unique API key to configure in their camera.
"""

import secrets
import json
import os
from datetime import datetime

class APIKeyManager:
    def __init__(self, data_dir='data'):
        self.keys_file = os.path.join(data_dir, 'api_keys.json')
        self.keys = self._load_keys()
    
    def _load_keys(self):
        """Load API keys from file."""
        if os.path.exists(self.keys_file):
            with open(self.keys_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_keys(self):
        """Save API keys to file."""
        os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)
        with open(self.keys_file, 'w') as f:
            json.dump(self.keys, f, indent=2)
    
    def generate_key(self, photographer_name, event_id=None):
        """Generate a new API key for a photographer."""
        api_key = f"gp_{secrets.token_urlsafe(32)}"
        
        self.keys[api_key] = {
            'photographer_name': photographer_name,
            'event_id': event_id,
            'created_at': datetime.now().isoformat(),
            'active': True
        }
        
        self._save_keys()
        return api_key
    
    def validate_key(self, api_key):
        """Validate an API key and return associated data."""
        if api_key not in self.keys:
            return None
        
        key_data = self.keys[api_key]
        if not key_data.get('active', False):
            return None
        
        return key_data
    
    def revoke_key(self, api_key):
        """Revoke an API key."""
        if api_key in self.keys:
            self.keys[api_key]['active'] = False
            self._save_keys()
            return True
        return False
    
    def list_keys(self):
        """List all API keys."""
        return [
            {
                'key': key,
                'photographer': data['photographer_name'],
                'event_id': data.get('event_id'),
                'created': data['created_at'],
                'active': data['active']
            }
            for key, data in self.keys.items()
        ]
