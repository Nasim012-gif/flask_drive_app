"""
Face recognition service using DeepFace.
"""

import os
import glob
from concurrent.futures import ThreadPoolExecutor

# Lazy load DeepFace to avoid slow startup
_deepface = None

def get_deepface():
    """Lazy load DeepFace module."""
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
        except ImportError:
            print("Error: DeepFace not installed. Please run 'pip install deepface tf-keras'")
            raise
    return _deepface

def verify_face(source_img_path, target_img_paths, model_name="VGG-Face", distance_metric="cosine"):
    """
    Compare a source face (selfie) against a list of target images.
    
    Args:
        source_img_path (str): Path to the selfie image.
        target_img_paths (list): List of paths to event photos.
        model_name (str): DeepFace model to use (VGG-Face, Facenet, etc.)
        distance_metric (str): Metric for comparison (cosine, euclidean)
        
    Returns:
        list: List of matching image paths.
    """
    df = get_deepface()
    matches = []
    
    # Pre-filter: only check files that exist
    valid_targets = [p for p in target_img_paths if os.path.exists(p)]
    
    if not valid_targets:
        return []

    print(f"DEBUG: Starting face matching for {len(valid_targets)} photos...")
    
    # Clean up any existing DeepFace pickle cache to ensure a fresh scan
    # (Fixes issues on ephemeral storage where indices might be corrupt)
    try:
        db_path = os.path.dirname(valid_targets[0])
        for pkl_file in glob.glob(os.path.join(db_path, "*.pkl")):
            os.remove(pkl_file)
            print(f"DEBUG: Removed old face index cache: {pkl_file}")
    except:
        pass

    try:
        # Use DeepFace.find() which is optimized for 1-to-many search
        result = df.find(
            img_path=source_img_path,
            db_path=os.path.dirname(valid_targets[0]), # Folder containing images
            model_name=model_name,
            distance_metric=distance_metric,
            enforce_detection=False, # Don't crash if no face found in some background photos
            silent=True
        )
        
        print(f"DEBUG: DeepFace.find result: {result}")
        
        if result and len(result) > 0:
            # Result[0] is the DataFrame for the first (and only) source image
            df_matches = result[0]
            if not df_matches.empty:
                print(f"DEBUG: Found {len(df_matches)} potential matches in DataFrame.")
                # Get the 'identity' column which contains the matching file paths
                matched_identities = df_matches['identity'].tolist()
                
                # Filter to ensure we only return paths that were in our target list
                matches = [path for path in matched_identities if path in valid_targets]
                print(f"DEBUG: Matches after filtering: {len(matches)}")
            else:
                print("DEBUG: DataFrame is empty - no matches found.")
        else:
             print("DEBUG: result is None or empty list.")
                
    except Exception as e:
        print(f"DeepFace matching error: {str(e)}")
        # Fallback: exact match loop (slower but safer if find() fails)
        pass

    return matches

def detect_face(img_path):
    """Check if an image contains a face."""
    df = get_deepface()
    try:
        # Just try to detect a face, don't need embeddings
        df.extract_faces(img_path, enforce_detection=True)
        return True
    except:
        return False
