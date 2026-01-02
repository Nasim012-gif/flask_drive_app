"""
Face Detection and Matching Service using DeepFace

This service handles:
- Downloading photos from Cloudinary
- Detecting faces using DeepFace
- Storing face embeddings in database
- Matching guest selfies against event photos
"""

import os
import numpy as np
import requests
from io import BytesIO
from PIL import Image
from deepface import DeepFace
import tempfile

class FaceDetectionService:
    
    def __init__(self, model_name='Facenet512'):
        """
        Initialize face detection service
        
        Args:
            model_name: DeepFace model to use
                - 'VGG-Face': Accurate, slower
                - 'Facenet': Fast, good accuracy
                - 'Facenet512': Best accuracy, moderate speed
                - 'ArcFace': State-of-the-art, slower
        """
        self.model_name = model_name
        print(f"[FaceDetection] Initialized with model: {model_name}")
    
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
            
            # Save to temp file (DeepFace requires file path)
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                image.save(tmp.name)
                temp_path = tmp.name
            
            try:
                # Detect and extract faces
                faces = DeepFace.extract_faces(
                    img_path=temp_path,
                    detector_backend='opencv',
                    enforce_detection=False
                )
                
                if not faces:
                    print(f"[FaceDetection] No faces detected")
                    return []
                
                # Generate embeddings for each face
                results = []
                for i, face_obj in enumerate(faces):
                    try:
                        # Get face region
                        facial_area = face_obj.get('facial_area', {})
                        
                        # Generate embedding
                        embedding_obj = DeepFace.represent(
                            img_path=temp_path,
                            model_name=self.model_name,
                            detector_backend='skip',  # Already detected
                            enforce_detection=False
                        )
                        
                        if embedding_obj and len(embedding_obj) > i:
                            embedding = embedding_obj[i]['embedding']
                            
                            results.append({
                                'embedding': embedding,
                                'location': {
                                    'x': facial_area.get('x', 0),
                                    'y': facial_area.get('y', 0),
                                    'w': facial_area.get('w', 0),
                                    'h': facial_area.get('h', 0)
                                },
                                'confidence': face_obj.get('confidence', 0)
                            })
                            print(f"[FaceDetection] Face {i+1} processed")
                    except Exception as e:
                        print(f"[FaceDetection] Error processing face {i}: {e}")
                        continue
                
                return results
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            print(f"[FaceDetection] Error in detect_faces: {e}")
            return []
    
    def compare_faces(self, embedding1, embedding2):
        """
        Compare two face embeddings
        
        Returns:
            distance (float): Lower is more similar (0.0 = identical)
        """
        try:
            # Convert to numpy arrays
            emb1 = np.array(embedding1)
            emb2 = np.array(embedding2)
            
            # Calculate cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            
            # Convert to distance (0 = identical, 1 = completely different)
            distance = 1 - similarity
            
            return float(distance)
        except Exception as e:
            print(f"[FaceDetection] Error comparing faces: {e}")
            return 1.0  # Return max distance on error
    
    def find_matches(self, guest_embedding, event_embeddings, threshold=0.6):
        """
        Find matching photos for a guest selfie
        
        Args:
            guest_embedding: Guest's face embedding
            event_embeddings: List of (photo_id, embedding) tuples
            threshold: Maximum distance for a match (default 0.6)
        
        Returns:
            List of matches with similarity scores
        """
        matches = []
        
        for photo_id, embedding, face_location in event_embeddings:
            distance = self.compare_faces(guest_embedding, embedding)
            
            if distance < threshold:
                similarity = 1 - distance
                confidence = 'high' if distance < 0.4 else 'medium'
                
                matches.append({
                    'photo_id': photo_id,
                    'distance': distance,
                    'similarity': similarity,
                    'confidence': confidence,
                    'face_location': face_location
                })
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"[FaceDetection] Found {len(matches)} matches (threshold: {threshold})")
        return matches


# Global instance
face_service = FaceDetectionService(model_name='Facenet512')


def is_configured():
    """Check if face detection is available"""
    try:
        import deepface
        return True
    except ImportError:
        return False
