"""
Face Detection Service using face-recognition library (lightweight, no TensorFlow)
"""

import face_recognition
import requests
from PIL import Image
from io import BytesIO
import numpy as np


def is_configured():
    """Check if face recognition is available"""
    try:
        import face_recognition
        return True
    except ImportError:
        return False


class FaceDetectionService:
    """Face detection and matching using face-recognition library"""
    
    def __init__(self):
        """Initialize face detection service"""
        print("[FaceDetection] Initialized with face-recognition library (lightweight)")
    
    def download_image_from_url(self, url):
        """Download image from Cloudinary URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            print(f"[FaceDetection] Error downloading image: {e}")
            return None
    
    def detect_faces(self, image_url):
        """
        Detect faces in an image from Cloudinary
        
        Returns:
            List of face embeddings and locations
        """
        try:
            print(f"[FaceDetection] Processing: {image_url}")
            
            # Download image
            image = self.download_image_from_url(image_url)
            if image is None:
                return []
            
            # Convert PIL Image to numpy array
            image_np = np.array(image)
            
            # Detect face locations (top, right, bottom, left)
            face_locations = face_recognition.face_locations(image_np, model='hog')
            
            if not face_locations:
                print(f"[FaceDetection] No faces detected")
                return []
            
            # Generate face encodings (128-dimensional embeddings)
            face_encodings = face_recognition.face_encodings(image_np, face_locations)
            
            results = []
            for i, (encoding, location) in enumerate(zip(face_encodings, face_locations)):
                top, right, bottom, left = location
                
                results.append({
                    'embedding': encoding.tolist(),  # Convert numpy array to list
                    'location': {
                        'x': left,
                        'y': top,
                        'w': right - left,
                        'h': bottom - top
                    },
                    'confidence': 1.0  # face-recognition doesn't provide confidence scores
                })
                print(f"[FaceDetection] Face {i+1} detected")
            
            print(f"[FaceDetection] Found {len(results)} faces")
            return results
            
        except Exception as e:
            print(f"[FaceDetection] Error processing image: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def compare_faces(self, embedding1, embedding2, tolerance=0.6):
        """
        Compare two face embeddings
        
        Args:
            embedding1: First face embedding (list or numpy array)
            embedding2: Second face embedding (list or numpy array)
            tolerance: How much distance between faces to consider a match (default 0.6)
        
        Returns:
            distance: Distance between faces (lower = more similar)
        """
        try:
            # Convert to numpy arrays if needed
            if not isinstance(embedding1, np.ndarray):
                embedding1 = np.array(embedding1)
            if not isinstance(embedding2, np.ndarray):
                embedding2 = np.array(embedding2)
            
            # Calculate Euclidean distance
            distance = np.linalg.norm(embedding1 - embedding2)
            
            return distance
        except Exception as e:
            print(f"[FaceDetection] Error comparing faces: {e}")
            return 1.0  # Return high distance on error
    
    def find_matches(self, guest_embedding, event_embeddings, threshold=0.6):
        """
        Find matching faces in event photos
        
        Args:
            guest_embedding: Guest's face embedding
            event_embeddings: List of dict with 'embedding', 'photo_id', 'confidence'
            threshold: Distance threshold for matches (lower = stricter)
        
        Returns:
            List of matches with similarity scores
        """
        try:
            matches = []
            
            for face_data in event_embeddings:
                stored_embedding = face_data['embedding']
                
                # Compare faces
                distance = self.compare_faces(guest_embedding, stored_embedding)
                
                # Check if it's a match (lower distance = better match)
                if distance <= threshold:
                    similarity = 1.0 - distance  # Convert distance to similarity score
                    matches.append({
                        'photo_id': face_data['photo_id'],
                        'similarity': max(0, min(1, similarity)),  # Clamp to [0, 1]
                        'confidence': face_data.get('confidence', 1.0),
                        'distance': distance
                    })
            
            # Sort by similarity (highest first)
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            
            print(f"[FaceDetection] Found {len(matches)} matches out of {len(event_embeddings)} faces")
            return matches
            
        except Exception as e:
            print(f"[FaceDetection] Error finding matches: {e}")
            import traceback
            traceback.print_exc()
            return []


# Create global instance
face_service = FaceDetectionService()
