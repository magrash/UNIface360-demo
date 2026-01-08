import os
import cv2
import face_recognition
import numpy as np
from PIL import Image, ImageEnhance

# Path to the temporary faces directory
TEMP_DIR = "temp_faces"
OUTPUT_DIR = "debug_faces"

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"Created debug faces directory: {OUTPUT_DIR}")

# Get list of face images in the temp directory
face_files = sorted(os.listdir(TEMP_DIR)) if os.path.exists(TEMP_DIR) else []

print(f"Found {len(face_files)} face images to analyze")

# Stats
success_count = 0
fail_count = 0
improved_count = 0

for i, face_file in enumerate(face_files):
    face_path = os.path.join(TEMP_DIR, face_file)
    print(f"\nAnalyzing face {i+1}/{len(face_files)}: {face_file}")
    
    # Load the image
    try:
        face_img = cv2.imread(face_path)
        if face_img is None:
            print(f"Error: Could not load image file {face_path}")
            fail_count += 1
            continue
            
        # Create a diagnostic image for this face
        h, w = face_img.shape[:2]
        debug_img = np.zeros((h, w*2, 3), dtype=np.uint8)
        debug_img[:h, :w] = face_img  # Original image on left side
        
        # Convert to RGB for face_recognition library
        rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        
        # Try to get face encodings with default settings
        original_encodings = face_recognition.face_encodings(rgb_face)
        
        if len(original_encodings) > 0:
            cv2.putText(debug_img, "ORIGINAL: ENCODING SUCCESS", (10, 20), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            success_count += 1
        else:
            cv2.putText(debug_img, "ORIGINAL: ENCODING FAILED", (10, 20), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Try enhancements if original encoding failed
        if len(original_encodings) == 0:
            print(f"Original face encoding failed, trying enhancements...")
            
            # Convert to PIL for easier image processing
            pil_img = Image.fromarray(cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB))
            
            # Try enhancement techniques
            # 1. Adjust contrast and brightness
            enhancer = ImageEnhance.Contrast(pil_img)
            enhanced_img = enhancer.enhance(1.5)  # Increase contrast
            
            enhancer = ImageEnhance.Brightness(enhanced_img)
            enhanced_img = enhancer.enhance(1.2)  # Increase brightness
            
            # Convert back to OpenCV format
            enhanced_cv = cv2.cvtColor(np.array(enhanced_img), cv2.COLOR_RGB2BGR)
            
            # Copy enhanced image to right side of debug image
            debug_img[:h, w:w*2] = enhanced_cv
            
            # Try encoding again with enhanced image
            rgb_enhanced = cv2.cvtColor(enhanced_cv, cv2.COLOR_BGR2RGB)
            enhanced_encodings = face_recognition.face_encodings(rgb_enhanced)
            
            if len(enhanced_encodings) > 0:
                cv2.putText(debug_img, "ENHANCED: ENCODING SUCCESS", (w+10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                print(f"✓ Enhancement successful!")
                improved_count += 1
            else:
                cv2.putText(debug_img, "ENHANCED: ENCODING FAILED", (w+10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                
                # Try again with more aggressive face detection
                # Detect faces with HOG model first
                face_locations = face_recognition.face_locations(rgb_enhanced, model="hog")
                if len(face_locations) == 0:
                    face_locations = face_recognition.face_locations(rgb_enhanced, model="cnn")
                
                if len(face_locations) > 0:
                    print(f"Found face with explicit detection, but encoding still failed")
                    # Draw the face bounding box
                    for top, right, bottom, left in face_locations:
                        cv2.rectangle(debug_img[:h, w:w*2], (left, top), (right, bottom), (0, 255, 255), 2)
                else:
                    print(f"No face detected in enhanced image")
                
                fail_count += 1
        
        # Save the diagnostic image
        debug_path = os.path.join(OUTPUT_DIR, f"debug_{face_file}")
        cv2.imwrite(debug_path, debug_img)
        
    except Exception as e:
        print(f"Error processing {face_file}: {str(e)}")
        fail_count += 1

print("\n--- SUMMARY ---")
print(f"Total face images analyzed: {len(face_files)}")
print(f"Successfully encoded: {success_count} ({success_count/len(face_files)*100:.1f}%)")
print(f"Failed to encode: {fail_count} ({fail_count/len(face_files)*100:.1f}%)")
print(f"Improved with enhancement: {improved_count}")
print("\nDiagnostic images saved to:", OUTPUT_DIR)
print("\nRecommendations:")
if fail_count > 0:
    print("1. Check lighting conditions in camera feed")
    print("2. Increase minimum face size in detection")
    print("3. Consider preprocessing images before encoding")
    print("4. Check camera focus and quality settings")
