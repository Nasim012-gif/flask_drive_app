
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import face_service

class TestFaceService(unittest.TestCase):
    
    @patch('face_service.get_deepface')
    def test_verify_face_passes_db_path(self, mock_get_deepface):
        # Setup mock
        mock_df = MagicMock()
        mock_get_deepface.return_value = mock_df
        
        mock_df.find.return_value = [] # Return empty list
        
        # Test data
        source = "selfie.jpg"
        targets = ["/custom/path/img1.jpg", "/custom/path/subdir/img2.jpg"]
        custom_db_path = "/custom/path"
        
        # Call the function
        # Create dummy file existence check
        with patch('os.path.exists', return_value=True):
            face_service.verify_face(source, targets, db_path=custom_db_path)
        
        # Verify DeepFace.find was called with the correct db_path
        mock_df.find.assert_called_once()
        call_args = mock_df.find.call_args
        self.assertEqual(call_args.kwargs['db_path'], custom_db_path)
        print("SUCCESS: DeepFace.find was called with db_path=" + custom_db_path)

    @patch('face_service.get_deepface')
    def test_verify_face_default_behavior(self, mock_get_deepface):
        # Setup mock
        mock_df = MagicMock()
        mock_get_deepface.return_value = mock_df
        mock_df.find.return_value = [] 
        
        targets = ["/default/path/img1.jpg"]
        
        with patch('os.path.exists', return_value=True):
            face_service.verify_face("selfie.jpg", targets)
            
        # Verify it defaults to dirname of first target
        mock_df.find.assert_called_once()
        self.assertEqual(mock_df.find.call_args.kwargs['db_path'], "/default/path")
        print("SUCCESS: DeepFace.find defaulted to /default/path")

if __name__ == '__main__':
    unittest.main()
