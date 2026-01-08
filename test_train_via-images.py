import face_recognition
import os
import pickle
import numpy as np

# Load the precomputed face encodings
ENCODINGS_FILE = "face_encodings.pkl"
if not os.path.exists(ENCODINGS_FILE):
    print(f"Error: {ENCODINGS_FILE} not found. Please train the model first.")
    exit()

with open(ENCODINGS_FILE, "rb") as f:
    known_faces = pickle.load(f)
print(f"Loaded encodings for {len(known_faces)} known individuals.")

# Function to identify faces in a test image
def identify_faces(image_path, known_faces):
    # Load the test image
    test_image = face_recognition.load_image_file(image_path)
    
    # Find face locations and encodings in the test image
    face_locations = face_recognition.face_locations(test_image)
    test_encodings = face_recognition.face_encodings(test_image, face_locations)
    
    if not test_encodings:
        print(f"No faces detected in {os.path.basename(image_path)}")
        return
    
    # Compare each detected face against known encodings
    for i, test_encoding in enumerate(test_encodings):
        print(f"\nProcessing face {i+1} in {os.path.basename(image_path)}")
        # Compare with known faces
        matches = []
        for name, known_encoding in known_faces.items():
            # Calculate distance between test encoding and known encoding
            distance = face_recognition.face_distance([known_encoding], test_encoding)[0]
            # Threshold for a match (0.6 is a common default, adjust as needed)
            if distance < 0.6:
                matches.append((name, distance))
        
        # Sort matches by distance (closest first)
        matches.sort(key=lambda x: x[1])
        
        if matches:
            # Best match
            best_match_name, best_match_distance = matches[0]
            print(f"Identified as {best_match_name} (distance: {best_match_distance:.4f})")
            # Report other close matches, if any
            if len(matches) > 1:
                print("Other possible matches:")
                for name, dist in matches[1:]:
                    print(f"  {name} (distance: {dist:.4f})")
        else:
            print("No match found. Unknown person.")

# Settings
TEST_FOLDER = "test_images"

# Test the model on all images in the test folder
if not os.path.exists(TEST_FOLDER):
    print(f"Error: {TEST_FOLDER} folder not found.")
    exit()

print(f"\nTesting images in '{TEST_FOLDER}' folder:")
for filename in os.listdir(TEST_FOLDER):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):  # Check for image files
        image_path = os.path.join(TEST_FOLDER, filename)
        print(f"\nAnalyzing {filename}...")
        identify_faces(image_path, known_faces)

print("\nTesting complete!")