import cv2
import face_recognition
import yaml
import time
import numpy as np
import os
import sqlite3
import pickle
from datetime import datetime, timedelta

print("=== RTSP Camera & Face Recognition Diagnostic Tool ===")

# Load configuration
print("\nLoading config...")
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    print("Config loaded successfully")
    print(f"- Database: {config['database']}")
    print(f"- Encodings file: {config['encodings_file']}")
    print(f"- Evidence directory: {config['evidence_dir']}")
    print(f"- Debounce seconds: {config['debounce_seconds']}")
except Exception as e:
    print(f"Error loading config: {str(e)}")
    config = {
        "camera_floors": {},
        "encodings_file": "face_encodings.pkl",
        "database": "tracking.db"
    }

# Test database connection
print("\nTesting database connection...")
try:
    conn = sqlite3.connect(config["database"])
    cursor = conn.cursor()
    
    # Check if logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
    if cursor.fetchone():
        print("- Logs table exists")
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM logs")
        count = cursor.fetchone()[0]
        print(f"- Found {count} log entries")
        
        # Get most recent entries
        cursor.execute("SELECT name, time, floor, confidence FROM logs ORDER BY id DESC LIMIT 5")
        recent = cursor.fetchall()
        if recent:
            print("- Most recent entries:")
            for r in recent:
                print(f"  {r[0]} at {r[2]} on {r[1]} (conf: {r[3]:.2f})")
    else:
        print("- Logs table does not exist")
    
    # Test insert and delete
    test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("- Testing DB write...")
    cursor.execute(
        "INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
        ("TEST_ENTRY", test_time, "TEST_FLOOR", "TEST_PATH", 0.99)
    )
    conn.commit()
    print("- Test entry written")
    
    # Clean up test entry
    cursor.execute("DELETE FROM logs WHERE name = 'TEST_ENTRY' AND floor = 'TEST_FLOOR'")
    conn.commit()
    print("- Test entry deleted")
    
    conn.close()
    print("Database test: SUCCESS")
except Exception as e:
    print(f"Database test error: {str(e)}")

# Test face encodings
print("\nTesting face encodings...")
try:
    with open(config["encodings_file"], "rb") as f:
        data = pickle.load(f)
    
    encoding_count = len(data)
    print(f"- Found {encoding_count} face encodings")
    print(f"- Names: {', '.join(list(data.keys()))}")
    print("Face encodings test: SUCCESS")
except Exception as e:
    print(f"Face encodings test error: {str(e)}")

# Test camera connections
print("\nTesting RTSP camera connections...")
rtsp_urls = list(config["camera_floors"].keys())
floor_names = list(config["camera_floors"].values())

if not rtsp_urls:
    print("No RTSP URLs found in config")
else:
    print(f"Found {len(rtsp_urls)} cameras in config")
    
    success_count = 0
    for idx, url in enumerate(rtsp_urls):
        print(f"\nTesting camera {idx+1}/{len(rtsp_urls)}: {floor_names[idx]} - {url}")
        
        # Open connection with timeout
        cap = cv2.VideoCapture(url)
        start_time = time.time()
        timeout = 5  # seconds
        
        connected = False
        while time.time() - start_time < timeout:
            if cap.isOpened():
                connected = True
                break
            time.sleep(0.5)
        
        if connected:
            print(f"- Connection successful")
            # Try to read a frame
            ret, frame = cap.read()
            if ret:
                print(f"- Frame read successful: {frame.shape}")
                
                # Try face detection on this frame
                print(f"- Testing face detection...")
                try:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    face_locations = face_recognition.face_locations(rgb_frame)
                    print(f"- Found {len(face_locations)} faces")
                    
                    if len(face_locations) > 0:
                        # Get face encodings
                        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                        
                        for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
                            try:
                                # Compare with known faces
                                distances = face_recognition.face_distance(list(data.values()), face_encoding)
                                min_distance = min(distances) if len(distances) > 0 else 1.0
                                matches = face_recognition.compare_faces(list(data.values()), face_encoding, tolerance=0.6)
                                
                                name = "Unknown"
                                if True in matches:
                                    index = matches.index(True)
                                    name = list(data.keys())[index]
                                
                                print(f"  - Face {i+1}: {name} (distance={min_distance:.3f})")
                                
                                # Draw on the frame
                                top, right, bottom, left = face_location
                                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                                cv2.putText(frame, f"{name} ({min_distance:.2f})", (left, top-10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                            except Exception as e:
                                print(f"  - Error processing face {i+1}: {str(e)}")
                        
                        # Show the frame with detections
                        resized = cv2.resize(frame, (800, 600))
                        cv2.imshow(f"Camera {floor_names[idx]} - Face Detection", resized)
                        print("  - Press any key to continue to next camera...")
                        cv2.waitKey(0)
                        cv2.destroyAllWindows()
                except Exception as e:
                    print(f"- Face detection error: {str(e)}")
                
                success_count += 1
            else:
                print(f"- Failed to read frame")
        else:
            print(f"- Failed to connect within {timeout} seconds")
        
        # Clean up
        cap.release()
    
    print(f"\nCamera test summary: {success_count}/{len(rtsp_urls)} cameras working")

print("\n=== Diagnostic Complete ===")
if success_count == 0 and len(rtsp_urls) > 0:
    print("\n[CRITICAL] No cameras could be accessed. Check your network connectivity and RTSP URLs.")
    print("Common issues:")
    print("1. Incorrect username/password in RTSP URL")
    print("2. Camera not on the same network or behind firewall")
    print("3. Incorrect IP address or port number")
    print("4. Camera not supporting the specific RTSP path format used")
