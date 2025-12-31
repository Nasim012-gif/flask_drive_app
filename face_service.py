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

def enhance_photo(img_path):
    """
    Enhance a photo using OpenCV DNN Super Resolution (FSRCNN).
    Used for upscaling group photos where faces are small.
    """
    try:
        import cv2
        from cv2 import dnn_superres
        
        print(f"DEBUG: Enhancing photo {os.path.basename(img_path)}...")
        
        # Load image
        img = cv2.imread(img_path)
        if img is None:
            return None
            
        # Initialize super resolution object
        sr = dnn_superres.DnnSuperResImpl_create()
        
        # Read the model
        model_path = os.path.join(os.getcwd(), 'fsrcnn_x3.pb')
        if not os.path.exists(model_path):
            print("DEBUG: Super resolution model not found. Skipping enhancement.")
            return None
            
        sr.readModel(model_path)
        
        # Set the model (FSRCNN, scale 3)
        sr.setModel("fsrcnn", 3)
        
        # Upscale
        result = sr.upsample(img)
        
        # Save enhanced image to temp file
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
        os.close(temp_fd)
        cv2.imwrite(temp_path, result)
        
        print(f"DEBUG: Enhanced photo saved to {temp_path}")
        return temp_path
        
    except Exception as e:
        print(f"DEBUG: Enhancement failed: {e}")
        return None

def verify_face(source_img_path, target_img_paths, model_name="VGG-Face", distance_metric="cosine", db_path=None):
    """
    Compare a source face (selfie) against a list of target images.
    
    Args:
        source_img_path (str): Path to the selfie image.
        target_img_paths (list): List of paths to event photos.
        model_name (str): DeepFace model to use (VGG-Face, Facenet, etc.)
        distance_metric (str): Metric for comparison (cosine, euclidean)
        db_path (str): Optional. Explicit path to the photo database folder.
        
    Returns:
        list: List of matching image paths.
    """
    df = get_deepface()
    matches = []
    
    # Pre-filter: only check files that exist
    valid_targets = [p for p in target_img_paths if os.path.exists(p)]
    
    if not valid_targets and not db_path:
        return []

    print(f"DEBUG: Starting face matching for {len(valid_targets)} photos...")
    
    search_path = db_path
    if not search_path and valid_targets:
        search_path = os.path.dirname(valid_targets[0])
        
    if not search_path:
        return []
    # (Fixes issues on ephemeral storage where indices might be corrupt)
    # OPTIMIZATION: Removed forced deletion to allow caching.
    # try:
    #     db_path = os.path.dirname(valid_targets[0])
    #     for pkl_file in glob.glob(os.path.join(db_path, "*.pkl")):
    #         os.remove(pkl_file)
    #         print(f"DEBUG: Removed old face index cache: {pkl_file}")
    # except:
    #     pass

    try:
        result = df.find(
            img_path=source_img_path,
            db_path=search_path, # Folder containing images
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

def count_faces(img_path):
    """Estimate number of faces in an image to detect group photos."""
    df = get_deepface()
    try:
        faces = df.extract_faces(img_path, enforce_detection=True, align=False)
        return len(faces)
    except:
        return 0

def smart_verify_face(source_img_path, target_img_paths, db_path=None):
    """
    Enhanced verification with super-resolution for group photos.
    1. Run standard matching first (fast).
    2. Identify photos with multiple faces (group photos) that weren't matched.
    3. Enhance those specific photos using GAN/SuperRes.
    4. Run matching again on enhanced versions.
    """
    # 1. Standard fast scan
    matches = verify_face(source_img_path, target_img_paths, db_path=db_path)
    
    # 2. Find potental group photos that were missed
    # (Photos that are NOT in matches, but might contain our person if enhanced)
    # We select a subset to enhance to save performance
    potential_misses = [p for p in target_img_paths if p not in matches]
    
    if not potential_misses:
        return matches
    
    print(f"DEBUG: Checking {len(potential_misses)} non-matched photos for group enhancement...")
    enhanced_map = {} # Map temp_path -> original_path
    
    for img_path in potential_misses:
        # Heuristic: If image has > 2 faces, it's a group photo
        # Upscaling helps small faces in groups
        if count_faces(img_path) > 2:
            print(f"DEBUG: Detected group photo {os.path.basename(img_path)}, enhancing...")
            enhanced_path = enhance_photo(img_path)
            if enhanced_path:
                enhanced_map[enhanced_path] = img_path
    
    # 3. Re-run matching on enhanced photos
    if enhanced_map:
        enhanced_targets = list(enhanced_map.keys())
        print(f"DEBUG: Re-scanning {len(enhanced_targets)} enhanced group photos...")
        
        # DeepFace returns the paths of matched images from the target list
        enhanced_matches = verify_face(source_img_path, enhanced_targets) # No db_path for temp files
        
        for em in enhanced_matches:
            if em in enhanced_map:
                original_path = enhanced_map[em]
                if original_path not in matches:
                    matches.append(original_path)
                    print(f"DEBUG: Found NEW match in group photo after enhancement: {os.path.basename(original_path)}")
        
        # Cleanup temp files
        for temp_path in enhanced_targets:
            try:
                os.remove(temp_path)
            except:
                pass
        
    return matches
