"""
Face Detection Service using DeepFace with Facenet512 model
"""

from deepface import DeepFace
import requests
from PIL import Image
from io import BytesIO
import numpy as np
import tempfile
import os


def is_configured():
    """Check if face detection is available"""
    try:
        from deepface import DeepFace
        return True
    except ImportError:
        return False


class FaceDetectionService:
    """Face detection and matching using DeepFace library"""
    
    def __init__(self):
        """Initialize face detection service"""
        self.model_name = "Facenet512"
        print(f"[FaceDetection] Initialized with DeepFace model: {self.model_name}")
    
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
        Detect faces in an image from Cloudinary using DeepFace
        
        Returns:
            List of face embeddings and locations
        """
        try:
            print(f"[FaceDetection] Processing: {image_url}")
            
            # Download image
            image = self.download_image_from_url(image_url)
            if image is None:
                return []
            
            # Save to temporary file (DeepFace works with file paths)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                image.save(tmp.name)
                temp_path = tmp.name
            
            try:
                # Extract faces with DeepFace
                face_objs = DeepFace.extract_faces(
                    img_path=temp_path,
                    detector_backend='opencv',
                    enforce_detection=False,
                    align=True
                )
                
                if not face_objs:
                    print(f"[FaceDetection] No faces detected")
                    return []
                
                results = []
                for i, face_obj in enumerate(face_objs):
                    # Get face region
                    facial_area = face_obj.get('facial_area', {})
                    
                    # Generate embedding
                    embedding = DeepFace.represent(
                        img_path=temp_path,
                        model_name=self.model_name,
                        detector_backend='skip',  # Already detected
                        enforce_detection=False
                    )
                    
                    if embedding and len(embedding) > 0:
                        results.append({
                            'embedding': embedding[0]['embedding'],  # 512-dimensional vector
                            'location': {
                                'x': facial_area.get('x', 0),
                                'y': facial_area.get('y', 0),
                                'w': facial_area.get('w', 0),
                                'h': facial_area.get('h', 0)
                            },
                            'confidence': face_obj.get('confidence', 1.0)
                        })
                        print(f"[FaceDetection] Face {i+1} processed")
                
                print(f"[FaceDetection] Found {len(results)} faces")
                return results
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            print(f"[FaceDetection] Error processing image: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def compare_faces(self, embedding1, embedding2, threshold=0.6):
        """
        Compare two face embeddings using cosine similarity
        
        Args:
            embedding1: First face embedding
            embedding2: Second face embedding  
            threshold: Similarity threshold (not used, for compatibility)
        
        Returns:
            distance: Distance between faces (lower = more similar)
        """
        try:
            # Convert to numpy arrays if needed
            if not isinstance(embedding1, np.ndarray):
                embedding1 = np.array(embedding1)
            if not isinstance(embedding2, np.ndarray):
                embedding2 = np.array(embedding2)
            
            # Calculate cosine distance
            from scipy.spatial.distance import cosine
            distance = cosine(embedding1, embedding2)
            
            return distance
        except Exception as e:
            print(f"[FaceDetection] Error comparing faces: {e}")
            return 1.0  # Return high distance on error
    
    def find_matches(self, guest_embedding, event_embeddings, threshold=0.4):
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
                    similarity = 1.0 - distance  # Convert distance to similarity
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
