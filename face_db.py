"""
Helper functions for face embeddings database operations
"""

import json
import pickle
import events_db


def store_face_embedding(event_id, photo_id, embedding, face_location, confidence):
    """Store a face embedding in the database"""
    try:
        # Serialize embedding as pickle blob
        embedding_blob = pickle.dumps(embedding)
        
        # Serialize face location as JSON
        location_json = json.dumps(face_location)
        
        with events_db.get_db() as conn:
            conn.execute('''
                INSERT INTO face_embeddings (event_id, photo_id, embedding, face_location, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (event_id, photo_id, embedding_blob, location_json, confidence))
            conn.commit()
        
        print(f"[DB] Stored face embedding for photo {photo_id}")
        return True
    except Exception as e:
        print(f"[DB] Error storing face embedding: {e}")
        return False


def get_event_face_embeddings(event_id):
    """Get all face embeddings for an event"""
    try:
        with events_db.get_db() as conn:
            cursor = conn.execute('''
                SELECT photo_id, embedding, face_location
                FROM face_embeddings
                WHERE event_id = ?
            ''', (event_id,))
            
            results = []
            for row in cursor.fetchall():
                photo_id, embedding_blob, location_json = row
                
                # Deserialize
                embedding = pickle.loads(embedding_blob)
                face_location = json.loads(location_json) if location_json else {}
                
                # Return as dict for compatibility with face_detection_service
                results.append({
                    'photo_id': photo_id,
                    'embedding': embedding,
                    'face_location': face_location,
                    'confidence': 1.0
                })
            
            print(f"[DB] Retrieved {len(results)} face embeddings for event {event_id}")
            return results
    except Exception as e:
        print(f"[DB] Error retrieving face embeddings: {e}")
        import traceback
        traceback.print_exc()
        return []


def count_faces_in_event(event_id):
    """Count total faces detected in an event"""
    try:
        with events_db.get_db() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM face_embeddings WHERE event_id = ?
            ''', (event_id,))
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        print(f"[DB] Error counting faces: {e}")
        return 0


def delete_event_face_embeddings(event_id):
    """Delete all face embeddings for an event"""
    try:
        with events_db.get_db() as conn:
            conn.execute('DELETE FROM face_embeddings WHERE event_id = ?', (event_id,))
            conn.commit()
        print(f"[DB] Deleted face embeddings for event {event_id}")
        return True
    except Exception as e:
        print(f"[DB] Error deleting face embeddings: {e}")
        return False
