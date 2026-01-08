# import cv2
# import face_recognition
# import sqlite3
# import pickle
# import os
# import yaml
# import threading
# import queue
# import time
# from datetime import datetime
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler

# # Load config
# def load_config():
#     with open("config.yaml", "r") as f:
#         return yaml.safe_load(f)

# config = load_config()

# ENCODINGS_FILE = config["encodings_file"]
# DB_FILE = config["database"]
# CAMERA_FLOORS = config["camera_floors"]
# DEBOUNCE_SECONDS = config["debounce_seconds"]
# EVIDENCE_DIR = config["evidence_dir"]
# PROCESS_EVERY_N_FRAMES = config["process_every_n_frames"]

# # Load known faces
# def load_encodings():
#     try:
#         with open(ENCODINGS_FILE, "rb") as f:
#             data = pickle.load(f)
#         print("Loaded encodings.")
#         return data
#     except FileNotFoundError:
#         print("Error: Encodings file not found.")
#         exit(1)

# known_faces = load_encodings()

# # Watch for changes to the encodings file
# class EncodingChangeHandler(FileSystemEventHandler):
#     def on_modified(self, event):
#         global known_faces
#         if event.src_path.endswith(ENCODINGS_FILE):
#             print("Encodings file changed. Reloading...")
#             known_faces = load_encodings()

# observer = Observer()
# observer.schedule(EncodingChangeHandler(), path=".", recursive=False)
# observer.start()

# # Setup database
# conn = sqlite3.connect(DB_FILE, check_same_thread=False)
# cursor = conn.cursor()
# cursor.execute("""
#     CREATE TABLE IF NOT EXISTS logs (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT,
#         time TEXT,
#         floor TEXT,
#         image_path TEXT,
#         confidence REAL
#     )
# """)
# conn.commit()

# detection_queue = queue.Queue()
# last_detection = {}
# shutdown_event = threading.Event()

# if not os.path.exists(EVIDENCE_DIR):
#     os.makedirs(EVIDENCE_DIR)

# # Database writer
# def database_writer():
#     while not shutdown_event.is_set():
#         try:
#             name, time_now, floor, image_path, confidence = detection_queue.get(timeout=1)
#             last_time = last_detection.get(name)
#             current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
#             if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
#                 conn.execute("INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
#                              (name, time_now, floor, image_path, confidence))
#                 conn.commit()
#                 last_detection[name] = current_time
#                 print(f"Logged: {name} ({confidence:.2f}) at {floor} on {time_now}")
#             detection_queue.task_done()
#         except queue.Empty:
#             continue

# # Process camera
# def process_camera(camera_index, floor):
#     video_capture = cv2.VideoCapture(camera_index)
#     if not video_capture.isOpened():
#         print(f"Error: Cannot open camera {camera_index}")
#         return

#     window_name = f"Camera {camera_index} - {floor}"
#     frame_count = 0

#     while not shutdown_event.is_set():
#         ret, frame = video_capture.read()
#         if not ret:
#             print(f"Error: Failed to grab frame from camera {camera_index}")
#             break

#         cv2.putText(frame, f"{floor}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#         cv2.imshow(window_name, frame)

#         frame_count += 1
#         if frame_count % PROCESS_EVERY_N_FRAMES == 0:
#             small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
#             rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
#             face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=1)
#             face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#             for face_encoding, face_location in zip(face_encodings, face_locations):
#                 distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
#                 min_distance = min(distances) if len(distances) > 0 else 1.0
#                 matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.5)
#                 name = "Unknown"
#                 if True in matches:
#                     index = matches.index(True)
#                     name = list(known_faces.keys())[index]

#                 if name != "Unknown":
#                     time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                     top, right, bottom, left = [x * 2 for x in face_location]
#                     face_image = frame[top:bottom, left:right]
#                     filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
#                     image_path = os.path.join(EVIDENCE_DIR, filename)
#                     cv2.imwrite(image_path, face_image)
#                     detection_queue.put((name, time_now, floor, image_path, 1.0 - min_distance))

#         if cv2.waitKey(1) & 0xFF == ord("q"):
#             shutdown_event.set()
#             break

#     video_capture.release()
#     cv2.destroyWindow(window_name)

# # Start threads
# writer_thread = threading.Thread(target=database_writer)
# writer_thread.start()

# camera_threads = []
# for cam_index, floor in CAMERA_FLOORS.items():
#     thread = threading.Thread(target=process_camera, args=(cam_index, floor))
#     thread.start()
#     camera_threads.append(thread)

# try:
#     for thread in camera_threads:
#         thread.join()
# except KeyboardInterrupt:
#     print("Shutdown requested. Exiting...")
#     shutdown_event.set()

# # Wait for queue to empty and clean up
# writer_thread.join()
# detection_queue.join()
# observer.stop()
# observer.join()
# conn.close()
# print("Shutdown complete.")








import cv2
import face_recognition
import sqlite3
import pickle
import os
import yaml
import threading
import queue
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load config
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()

ENCODINGS_FILE = config["encodings_file"]
DB_FILE = config["database"]
CAMERA_FLOORS = config["camera_floors"]
DEBOUNCE_SECONDS = config["debounce_seconds"]
EVIDENCE_DIR = config["evidence_dir"]
PROCESS_EVERY_N_FRAMES = config["process_every_n_frames"]

# Load known faces
def load_encodings():
    try:
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
        print("Loaded encodings.")
        return data
    except FileNotFoundError:
        print("Error: Encodings file not found.")
        exit(1)

known_faces = load_encodings()

# Watch for changes to the encodings file
class EncodingChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        global known_faces
        if event.src_path.endswith(ENCODINGS_FILE):
            print("Encodings file changed. Reloading...")
            known_faces = load_encodings()

observer = Observer()
observer.schedule(EncodingChangeHandler(), path=".", recursive=False)
observer.start()

# Setup database
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        time TEXT,
        floor TEXT,
        image_path TEXT,
        confidence REAL
    )
""")
conn.commit()

# Check for missing columns and add them if needed
cursor.execute("PRAGMA table_info(logs)")
existing_columns = [col[1] for col in cursor.fetchall()]
required_columns = ["name", "time", "floor", "image_path", "confidence"]

for col in required_columns:
    if col not in existing_columns:
        if col == "confidence":
            cursor.execute("ALTER TABLE logs ADD COLUMN confidence REAL")
        else:
            cursor.execute(f"ALTER TABLE logs ADD COLUMN {col} TEXT")
        print(f"Added missing column: {col}")
conn.commit()

detection_queue = queue.Queue()
last_detection = {}
shutdown_event = threading.Event()

if not os.path.exists(EVIDENCE_DIR):
    os.makedirs(EVIDENCE_DIR)

# Database writer
def database_writer():
    while not shutdown_event.is_set():
        try:
            name, time_now, floor, image_path, confidence = detection_queue.get(timeout=1)
            last_time = last_detection.get(name)
            current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
            if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
                conn.execute("INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
                             (name, time_now, floor, image_path, confidence))
                conn.commit()
                last_detection[name] = current_time
                print(f"Logged: {name} ({confidence:.2f}) at {floor} on {time_now}")
            detection_queue.task_done()
        except queue.Empty:
            continue

# Process camera
def process_camera(camera_index, floor):
    video_capture = cv2.VideoCapture(camera_index)
    if not video_capture.isOpened():
        print(f"Error: Cannot open camera {camera_index}")
        return

    window_name = f"Camera {camera_index} - {floor}"
    frame_count = 0

    while not shutdown_event.is_set():
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

            for face_encoding, face_location in zip(face_encodings, face_locations):
                distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                min_distance = min(distances) if len(distances) > 0 else 1.0
                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.5)
                name = "Unknown"
                if True in matches:
                    index = matches.index(True)
                    name = list(known_faces.keys())[index]

                if name != "Unknown":
                    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    top, right, bottom, left = [x * 2 for x in face_location]
                    face_image = frame[top:bottom, left:right]
                    filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
                    image_path = os.path.join(EVIDENCE_DIR, filename)
                    cv2.imwrite(image_path, face_image)
                    detection_queue.put((name, time_now, floor, image_path, 1.0 - min_distance))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            shutdown_event.set()
            break

    video_capture.release()
    cv2.destroyWindow(window_name)

# Start threads
writer_thread = threading.Thread(target=database_writer)
writer_thread.start()

camera_threads = []
for cam_index, floor in CAMERA_FLOORS.items():
    thread = threading.Thread(target=process_camera, args=(cam_index, floor))
    thread.start()
    camera_threads.append(thread)

try:
    for thread in camera_threads:
        thread.join()
except KeyboardInterrupt:
    print("Shutdown requested. Exiting...")
    shutdown_event.set()

# Wait for queue to empty and clean up
writer_thread.join()
detection_queue.join()
observer.stop()
observer.join()
conn.close()
print("Shutdown complete.")