import cv2
import face_recognition
import sqlite3
import os
from datetime import datetime

# Load known faces
known_faces = {}
for filename in os.listdir("known_faces"):
    image = face_recognition.load_image_file(f"known_faces/{filename}")
    encodings = face_recognition.face_encodings(image)
    if encodings:  # Check if any faces were detected
        encoding = encodings[0]
        name = filename.split(".")[0]
        known_faces[name] = encoding
        print(f"Loaded face: {name}")
    else:
        print(f"No face detected in {filename}, skipping.")

# Setup database
conn = sqlite3.connect("tracking.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        time TEXT,
        floor TEXT
    )
""")
conn.commit()

# Start webcam
video_capture = cv2.VideoCapture(0)
current_floor = "Floor 1"

while True:
    ret, frame = video_capture.read()
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding)
        name = "Unknown"
        if True in matches:
            first_match_index = matches.index(True)
            name = list(known_faces.keys())[first_match_index]
        
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO logs (name, time, floor) VALUES (?, ?, ?)", (name, time_now, current_floor))
        conn.commit()
        print(f"Detected: {name} on {current_floor} at {time_now}")

    cv2.putText(frame, f"Current Floor: {current_floor}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Video", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key in [ord("1"), ord("2"), ord("3"), ord("4")]:
        current_floor = f"Floor {chr(key)}"

video_capture.release()
cv2.destroyAllWindows()
conn.close()