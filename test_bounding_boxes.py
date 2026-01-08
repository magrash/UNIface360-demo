#!/usr/bin/env python3
"""
Simple test to show bounding boxes on webcam for face recognition debugging
"""

import cv2
import face_recognition
import pickle
import config
import numpy as np

def load_known_faces():
    """Loads face encodings from the pickle file."""
    try:
        with open(config.ENCODINGS_FILE, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Encodings file not found: {config.ENCODINGS_FILE}")
        return {}

def main():
    print("=== Face Recognition with Bounding Boxes Test ===")
    print("Press 'q' to quit")
    
    known_faces = load_known_faces()
    print(f"[INFO] Loaded {len(known_faces)} known faces")
    
    # Start webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam")
        return
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Process every 5th frame for face recognition
        if frame_count % 5 == 0:
            # Resize for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Find faces
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            # Process each face
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                # Scale back up face locations since the frame we detected in was scaled to 1/2 size
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2
                
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                name = "Unknown"
                confidence = 0.0
                
                # Use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = list(known_faces.keys())[best_match_index]
                        confidence = 1.0 - face_distances[best_match_index]
                
                # Choose color based on recognition
                if name != "Unknown":
                    color = (0, 255, 0)  # Green for known faces
                    print(f"[DETECTED] {name} with confidence {confidence:.2f}")
                else:
                    color = (0, 0, 255)  # Red for unknown faces
                
                # Draw a box around the face
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Draw a label with a name below the face
                label = f"{name} ({confidence:.2f})" if name != "Unknown" else "Unknown"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                
                # Draw label background
                cv2.rectangle(frame, (left, bottom - 35), (left + label_size[0], bottom), color, cv2.FILLED)
                cv2.putText(frame, label, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Add frame info
        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Press 'q' to quit", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Display the resulting image
        cv2.imshow('Face Recognition Test', frame)
        
        # Hit 'q' on the keyboard to quit!
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release handle to the webcam
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Test completed")

if __name__ == '__main__':
    main()
