"""
Face Matching API Endpoint - Updated for face-recognition library
"""

from flask import jsonify, request
import tempfile
import os
import numpy as np


def create_face_match_endpoint(app, events_db):
    """Create face matching endpoint"""
    
    @app.route('/api/events/<int:event_id>/match', methods=['POST'])
    def match_face(event_id):
        """
        Match a guest selfie against event photos
        
        Expects:
            - selfie image file in request
        
        Returns:
            - List of matching photos with similarity scores
        """
        try:
            print(f"=== FACE MATCH REQUEST for Event {event_id} ===")
            
            # Import services
            import face_detection_service
            import face_db
            import face_recognition
            from PIL import Image
            
            # Check if face detection is available
            if not face_detection_service.is_configured():
                return jsonify({'error': 'Face detection not available'}), 503
            
            # Get selfie image
            if 'selfie' not in request.files:
                return jsonify({'error': 'No selfie provided'}), 400
            
            selfie = request.files['selfie']
            
            # Save temporarily
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                selfie.save(tmp.name)
                temp_path = tmp.name
            
            try:
                # Detect face in selfie
                print("[Match] Detecting face in selfie...")
                
                # Load image
                image = Image.open(temp_path)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image_np = np.array(image)
                
                # Extract face embedding from selfie
                try:
                    face_encodings = face_recognition.face_encodings(image_np)
                    
                    if not face_encodings or len(face_encodings) == 0:
                        return jsonify({
                            'status': 'no_face',
                            'message': 'No face detected in selfie. Please try again with better lighting.'
                        }), 200
                    
                    guest_embedding = face_encodings[0].tolist()
                    print("[Match] Guest face detected")
                    
                except Exception as e:
                    print(f"[Match] Face detection failed: {e}")
                    return jsonify({
                        'status': 'no_face',
                        'message': 'Could not detect face in selfie. Please try again.'
                    }), 200
                
                # Get all face embeddings for this event
                event_embeddings = face_db.get_event_face_embeddings(event_id)
                
                if not event_embeddings:
                    return jsonify({
                        'status': 'no_faces_in_event',
                        'message': 'No faces detected in event photos yet. Please wait while photos are being processed.'
                    }), 200
                
                print(f"[Match] Comparing against {len(event_embeddings)} faces in event")
                
                # Find matches
                matches = face_detection_service.face_service.find_matches(
                    guest_embedding,
                    event_embeddings,
                    threshold=0.6  # Adjust for sensitivity
                )
                
                print(f"[Match] Found {len(matches)} potential matches")
                
                if not matches:
                    return jsonify({
                        'status': 'no_match',
                        'message': 'No matching photos found. Try with a clearer selfie or different angle.'
                    }), 200
                
                # Get photo details for matches
                matched_photos = []
                for match in matches:
                    photo = events_db.get_photo(match['photo_id'])
                    if photo:
                        matched_photos.append({
                            'photo_id': match['photo_id'],
                            'url': photo.get('cloudinary_url'),
                            'similarity': round(match['similarity'] * 100, 1),
                            'confidence': match['confidence']
                        })
                
                print(f"[Match] Returning {len(matched_photos)} matching photos")
                
                return jsonify({
                    'status': 'success',
                    'matches': matched_photos,
                    'count': len(matched_photos)
                }), 200
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            print(f"=== FACE MATCH ERROR ===")
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    return match_face

