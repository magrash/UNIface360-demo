import face_recognition
import cv2
import numpy as np
import pickle
import os
import time

# Load the face encodings
def load_encodings():
    try:
        with open("face_encodings.pkl", "rb") as f:
            data = pickle.load(f)
        print(f"Loaded {len(data)} known faces.")
        print(f"Known names: {list(data.keys())}")
        return data
    except FileNotFoundError:
        print("Error: Encodings file not found.")
        exit(1)

known_faces = load_encodings()

# Test with a static image first
print("\nTesting face recognition on static images in test_images folder...")

# Check if the folder exists
test_folder = "test_images"
if os.path.exists(test_folder):
    for img_file in os.listdir(test_folder):
        if img_file.endswith(('.jpg', '.jpeg', '.png')):
            print(f"\nTesting image: {img_file}")
            img_path = os.path.join(test_folder, img_file)
            image = cv2.imread(img_path)
            
            # Convert to RGB (face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Find faces in the image
            face_locations = face_recognition.face_locations(rgb_image)
            print(f"Found {len(face_locations)} faces in the image")
            
            if len(face_locations) > 0:
                # Get face encodings
                face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
                
                # Check against known faces
                for face_encoding, face_location in zip(face_encodings, face_locations):
                    if len(known_faces) > 0:
                        distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                        min_distance = min(distances) if len(distances) > 0 else 1.0
                        matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                        name = "Unknown"
                        if True in matches:
                            index = matches.index(True)
                            name = list(known_faces.keys())[index]
                        
                        print(f"Match: {name}, Distance: {min_distance:.3f}")
                        
                        # Draw rectangle and name
                        top, right, bottom, left = face_location
                        cv2.rectangle(image, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.putText(image, f"{name} ({min_distance:.2f})", (left, top - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Display the result
            cv2.imshow(f"Test: {img_file}", cv2.resize(image, (800, 600)))
            cv2.waitKey(0)
            cv2.destroyAllWindows()
else:
    print(f"Folder {test_folder} not found. Skipping static image tests.")

# Now test with webcam (useful to verify face_recognition is working)
print("\nTesting face recognition with webcam...")
print("Press 'q' to exit.")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit(1)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame from webcam.")
        break
    
    # Resize frame for faster processing (optional)
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    
    # Convert to RGB (face_recognition uses RGB)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    # Find faces
    face_locations = face_recognition.face_locations(rgb_small_frame)
    if face_locations:
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        for face_encoding, face_location in zip(face_encodings, face_locations):
            if len(known_faces) > 0:
                distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                min_distance = min(distances) if len(distances) > 0 else 1.0
                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                name = "Unknown"
                if True in matches:
                    index = matches.index(True)
                    name = list(known_faces.keys())[index]
                
                # Scale back the face location
                top, right, bottom, left = [coord * 4 for coord in face_location]
                
                # Draw rectangle and name
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, f"{name} ({min_distance:.2f})", (left, top - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # Display the result
    cv2.imshow("Webcam Face Recognition Test", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Checking database
print("\nChecking for recent entries in the tracking database...")
try:
    import sqlite3
    from datetime import datetime, timedelta
    
    conn = sqlite3.connect("tracking.db")
    cursor = conn.cursor()
    
    # Get the last 10 entries
    cursor.execute("SELECT name, time, floor, confidence FROM logs ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    
    if rows:
        print("\nRecent database entries:")
        print("Name | Time | Floor | Confidence")
        print("-" * 50)
        for row in rows:
            print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]:.2f}")
    else:
        print("No recent entries found in the database.")
    
    conn.close()
except Exception as e:
    print(f"Error accessing database: {str(e)}")

print("\nDebugging complete.")
