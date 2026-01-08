# import cv2
# import face_recognition
# import sqlite3
# import pickle
# from datetime import datetime
# import threading
# import queue

# # Load precomputed encodings
# ENCODINGS_FILE = "face_encodings.pkl"
# try:
#     with open(ENCODINGS_FILE, "rb") as f:
#         known_faces = pickle.load(f)
#     print("Loaded precomputed encodings.")
# except FileNotFoundError:
#     print(f"Error: {ENCODINGS_FILE} not found. Run train_faces.py first.")
#     exit(1)

# # Setup database and queue
# conn = sqlite3.connect("tracking.db", check_same_thread=False)
# conn.execute("""
#     CREATE TABLE IF NOT EXISTS logs (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT,
#         time TEXT,
#         floor TEXT
#     )
# """)
# conn.commit()
# detection_queue = queue.Queue()

# # Camera-floor mapping
# CAMERA_FLOORS = {
#     0: "Floor 1",
#     1: "Floor 2",
#     2: "Floor 3"
# }

# # Track last detection time per person to debounce
# last_detection = {}
# DEBOUNCE_SECONDS = 5  # Only log a person to a new floor after 5 seconds

# # Function to process database writes
# def database_writer():
#     while True:
#         try:
#             name, time_now, floor = detection_queue.get(timeout=1)
#             current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
#             last_time = last_detection.get(name)

#             # Debounce: only log if enough time has passed since last detection
#             if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
#                 conn.execute("INSERT INTO logs (name, time, floor) VALUES (?, ?, ?)", (name, time_now, floor))
#                 conn.commit()
#                 last_detection[name] = current_time
#                 print(f"Logged: {name} on {floor} at {time_now}")
#             detection_queue.task_done()
#         except queue.Empty:
#             if not any(thread.is_alive() for thread in threading.enumerate() if thread != threading.current_thread()):
#                 break  # Exit if all camera threads are done

# # Function to process a single camera
# def process_camera(camera_index, floor):
#     video_capture = cv2.VideoCapture(camera_index)
#     if not video_capture.isOpened():
#         print(f"Error: Could not open camera {camera_index} for {floor}")
#         return

#     window_name = f"Camera {camera_index} - {floor}"
#     while True:
#         ret, frame = video_capture.read()
#         if not ret:
#             print(f"Error: Failed to grab frame from camera {camera_index}")
#             break

#         rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         face_locations = face_recognition.face_locations(rgb_frame)
#         face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#         for face_encoding in face_encodings:
#             matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)  # Stricter threshold
#             name = "Unknown"
#             if True in matches:
#                 first_match_index = matches.index(True)
#                 name = list(known_faces.keys())[first_match_index]
            
#             time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#             detection_queue.put((name, time_now, floor))

#         cv2.putText(frame, f"{floor}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#         cv2.imshow(window_name, frame)

#         if cv2.waitKey(1) & 0xFF == ord("q"):
#             break

#     video_capture.release()
#     cv2.destroyWindow(window_name)

# # Start database writer thread
# writer_thread = threading.Thread(target=database_writer)
# writer_thread.start()

# # Start camera threads
# threads = []
# for cam_index, floor in CAMERA_FLOORS.items():
#     thread = threading.Thread(target=process_camera, args=(cam_index, floor))
#     thread.start()
#     threads.append(thread)

# # Wait for camera threads to finish
# for thread in threads:
#     thread.join()

# # Signal writer to finish
# detection_queue.join()
# conn.close()
# print("All cameras stopped.")


import cv2
import face_recognition
import sqlite3
import pickle
from datetime import datetime
import threading
import queue
import os

# Load precomputed encodings
ENCODINGS_FILE = "face_encodings.pkl"
try:
    with open(ENCODINGS_FILE, "rb") as f:
        known_faces = pickle.load(f)
    print("Loaded precomputed encodings.")
except FileNotFoundError:
    print(f"Error: {ENCODINGS_FILE} not found. Run train_faces.py first.")
    exit(1)

# Setup database and queue
conn = sqlite3.connect("tracking.db", check_same_thread=False)
cursor = conn.cursor()

# Create table if it doesn’t exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        time TEXT,
        floor TEXT
    )
""")

# Add image_path column if it doesn’t exist
cursor.execute("PRAGMA table_info(logs)")
columns = [col[1] for col in cursor.fetchall()]
if "image_path" not in columns:
    cursor.execute("ALTER TABLE logs ADD COLUMN image_path TEXT")
    print("Added image_path column to logs table.")

conn.commit()
detection_queue = queue.Queue()

# Camera-floor mapping
CAMERA_FLOORS = {
    0: "Floor 1",
    1: "Floor 2",
    2: "Floor 3"
}

# Track last detection time per person to debounce
last_detection = {}
DEBOUNCE_SECONDS = 5

# Directory for saving evidence images
EVIDENCE_DIR = "evidence"
if not os.path.exists(EVIDENCE_DIR):
    os.makedirs(EVIDENCE_DIR)

# Function to process database writes
def database_writer():
    while True:
        try:
            name, time_now, floor, image_path = detection_queue.get(timeout=1)
            current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
            last_time = last_detection.get(name)

            if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
                conn.execute("INSERT INTO logs (name, time, floor, image_path) VALUES (?, ?, ?, ?)", 
                            (name, time_now, floor, image_path))
                conn.commit()
                last_detection[name] = current_time
                print(f"Logged: {name} on {floor} at {time_now} with image {image_path}")
            detection_queue.task_done()
        except queue.Empty:
            if not any(thread.is_alive() for thread in threading.enumerate() if thread != threading.current_thread()):
                break

# Function to process a single camera
def process_camera(camera_index, floor):
    video_capture = cv2.VideoCapture(camera_index)
    if not video_capture.isOpened():
        print(f"Error: Could not open camera {camera_index} for {floor}")
        return

    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window_name = f"Camera {camera_index} - {floor}"
    frame_count = 0
    PROCESS_EVERY_N_FRAMES = 5

    while True:
        ret, frame = video_capture.read()
        if not ret:
            print(f"Error: Failed to grab frame from camera {camera_index}")
            break

        cv2.putText(frame, f"{floor}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow(window_name, frame)

        frame_count += 1
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=1)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.5)
                face_distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                name = "Unknown"
                if matches and min(face_distances) < 0.5:
                    first_match_index = matches.index(True)
                    name = list(known_faces.keys())[first_match_index]

                if name != "Unknown":
                    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    top, right, bottom, left = [x * 2 for x in face_location]
                    face_image = frame[top:bottom, left:right]
                    image_filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
                    image_path = os.path.join(EVIDENCE_DIR, image_filename)
                    cv2.imwrite(image_path, face_image)
                    detection_queue.put((name, time_now, floor, image_path))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyWindow(window_name)

# Start database writer thread
writer_thread = threading.Thread(target=database_writer)
writer_thread.start()

# Start camera threads
threads = []
for cam_index, floor in CAMERA_FLOORS.items():
    thread = threading.Thread(target=process_camera, args=(cam_index, floor))
    thread.start()
    threads.append(thread)

# Wait for camera threads to finish
for thread in threads:
    thread.join()

detection_queue.join()
conn.close()
print("All cameras stopped.")