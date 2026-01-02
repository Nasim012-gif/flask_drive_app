"""
Face Matching API Endpoint
"""

from flask import jsonify, request
import tempfile
import os


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
                from deepface import DeepFace
                
                # Extract face embedding from selfie
                try:
                    embeddings = DeepFace.represent(
                        img_path=temp_path,
                        model_name='Facenet512',
                        enforce_detection=True
                    )
                    
                    if not embeddings or len(embeddings) == 0:
                        return jsonify({
                            'status': 'no_face',
                            'message': 'No face detected in selfie'
                        }), 200
                    
                    guest_embedding = embeddings[0]['embedding']
                    print("[Match] Guest face detected")
                    
                except Exception as e:
                    print(f"[Match] Face detection failed: {e}")
                    return jsonify({
                        'status': 'no_face',
                        'message': 'Could not detect face in selfie'
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
                
                if not matches:
                    return jsonify({
                        'status': 'no_match',
                        'message': 'No matching photos found'
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
                
                print(f"[Match] Found {len(matched_photos)} matching photos")
                
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
