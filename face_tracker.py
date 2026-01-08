# import cv2
# import face_recognition
# import sqlite3
# import os
# import pickle
# from datetime import datetime

# # Function to compute encodings for new images
# def compute_new_encodings(image_folder, existing_encodings):
#     new_encodings = existing_encodings.copy() if existing_encodings else {}
#     for filename in os.listdir(image_folder):
#         name = filename.split(".")[0]
#         if name not in new_encodings:  # Only process new images
#             image_path = os.path.join(image_folder, filename)
#             image = face_recognition.load_image_file(image_path)
#             encodings = face_recognition.face_encodings(image)
#             if encodings:
#                 new_encodings[name] = encodings[0]
#                 print(f"Trained new face: {name}")
#             else:
#                 print(f"No face detected in {filename}, skipping.")
#     return new_encodings

# # Load or compute face encodings
# ENCODINGS_FILE = "face_encodings.pkl"
# IMAGE_FOLDER = "known_faces"

# if os.path.exists(ENCODINGS_FILE):
#     with open(ENCODINGS_FILE, "rb") as f:
#         known_faces = pickle.load(f)
#     print("Loaded precomputed encodings.")
# else:
#     known_faces = compute_new_encodings(IMAGE_FOLDER, {})
#     with open(ENCODINGS_FILE, "wb") as f:
#         pickle.dump(known_faces, f)
#     print("Computed and saved initial encodings.")

# # Check for new images and update encodings if needed
# existing_files = set(known_faces.keys())
# current_files = set(f.split(".")[0] for f in os.listdir(IMAGE_FOLDER))
# new_files = current_files - existing_files

# if new_files:
#     print("New images detected, updating encodings...")
#     known_faces = compute_new_encodings(IMAGE_FOLDER, known_faces)
#     with open(ENCODINGS_FILE, "wb") as f:
#         pickle.dump(known_faces, f)
#     print("Updated encodings saved.")

# # Setup database
# conn = sqlite3.connect("tracking.db")
# conn.execute("""
#     CREATE TABLE IF NOT EXISTS logs (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT,
#         time TEXT,
#         floor TEXT
#     )
# """)
# conn.commit()

# # Start webcam
# video_capture = cv2.VideoCapture(0)
# current_floor = "Floor 1"

# while True:
#     ret, frame = video_capture.read()
#     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb_frame)
#     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#     for face_encoding in face_encodings:
#         matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding)
#         name = "Unknown"
#         if True in matches:
#             first_match_index = matches.index(True)
#             name = list(known_faces.keys())[first_match_index]
        
#         time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         conn.execute("INSERT INTO logs (name, time, floor) VALUES (?, ?, ?)", (name, time_now, current_floor))
#         conn.commit()
#         print(f"Detected: {name} on {current_floor} at {time_now}")

#     cv2.putText(frame, f"Current Floor: {current_floor}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#     cv2.imshow("Video", frame)

#     key = cv2.waitKey(1) & 0xFF
#     if key == ord("q"):
#         break
#     elif key in [ord("1"), ord("2"), ord("3"), ord("4")]:
#         current_floor = f"Floor {chr(key)}"

# video_capture.release()
# cv2.destroyAllWindows()
# conn.close()





import cv2
import face_recognition
import sqlite3
import pickle
from datetime import datetime

# Load precomputed encodings
ENCODINGS_FILE = "face_encodings.pkl"
try:
    with open(ENCODINGS_FILE, "rb") as f:
        known_faces = pickle.load(f)
    print("Loaded precomputed encodings.")
except FileNotFoundError:
    print(f"Error: {ENCODINGS_FILE} not found. Run train_faces.py first.")
    exit(1)

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