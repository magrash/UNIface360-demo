import cv2
import face_recognition
import sqlite3
import pickle
import os
import yaml
import time
from datetime import datetime

# Load config
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()

ENCODINGS_FILE = config["encodings_file"]
DB_FILE = config["database"]
DEBOUNCE_SECONDS = config["debounce_seconds"]
EVIDENCE_DIR = config["evidence_dir"]

# Load known encodings
def load_encodings():
    try:
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
        print(f"Loaded {len(data)} known face encodings.")
        return data
    except FileNotFoundError:
        print("Error: Encodings file not found.")
        exit(1)

known_faces = load_encodings()

# Setup evidence directory
if not os.path.exists(EVIDENCE_DIR):
    os.makedirs(EVIDENCE_DIR)

# Setup database
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Create a simple webcam test function
def test_webcam_recognition():
    print("\nTesting face recognition with webcam...")
    print("Press 'q' to quit.")
    
    # Initialize the webcam (use 0 for default camera)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    print("Webcam opened successfully.")
    
    # Dict to track last detection time for debouncing
    last_detection = {}
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
            
        # Process every 5 frames to reduce CPU usage
        frame_count += 1
        if frame_count % 5 != 0:
            # Just display the frame
            cv2.imshow("Webcam Test", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue
            
        # Convert to RGB for face_recognition library
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)
        
        # Draw rectangles around faces and process recognition
        for face_location in face_locations:
            top, right, bottom, left = face_location
            
            # Draw rectangle
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Get face encoding
            face_encoding = face_recognition.face_encodings(rgb_frame, [face_location])[0]
            
            # Compare with known faces
            if len(known_faces) > 0:
                distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                min_distance = min(distances) if len(distances) > 0 else 1.0
                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                name = "Unknown"
                if True in matches:
                    index = matches.index(True)
                    name = list(known_faces.keys())[index]
                    confidence = 1.0 - min_distance
                    
                    # Display name and confidence
                    text = f"{name} ({confidence:.2f})"
                    cv2.putText(frame, text, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    # Check if we should log this detection (debounce)
                    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
                    last_time = last_detection.get(name)
                    
                    if last_time is None or (current_time - datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")).total_seconds() >= DEBOUNCE_SECONDS:
                        print(f"Detected {name} with confidence {confidence:.2f}")
                        
                        # Save face image as evidence
                        face_image = frame[top:bottom, left:right]
                        filename = f"{name}_{time_now.replace(':', '-')}_webcam.jpg"
                        image_path = os.path.join(EVIDENCE_DIR, filename)
                        cv2.imwrite(image_path, face_image)
                        
                        # Log to database
                        cursor.execute(
                            "INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
                            (name, time_now, "Webcam Test", image_path, confidence)
                        )
                        conn.commit()
                        
                        # Update last detection time
                        last_detection[name] = time_now
                        print(f"Logged to database: {name} at {time_now}")
                else:
                    cv2.putText(frame, "Unknown", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Display the frame
        cv2.imshow("Webcam Test", frame)
        
        # Break the loop when 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release the camera and close windows
    cap.release()
    cv2.destroyAllWindows()

# Run the test
test_webcam_recognition()
conn.close()
print("Test completed.")
