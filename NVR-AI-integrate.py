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
# import numpy as np
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

# # Load known encodings
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

# # Watch for changes to encodings
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

# # Ensure all required columns exist
# cursor.execute("PRAGMA table_info(logs)")
# existing_columns = [col[1] for col in cursor.fetchall()]
# required_columns = ["name", "time", "floor", "image_path", "confidence"]

# for col in required_columns:
#     if col not in existing_columns:
#         if col == "confidence":
#             cursor.execute("ALTER TABLE logs ADD COLUMN confidence REAL")
#         else:
#             cursor.execute(f"ALTER TABLE logs ADD COLUMN {col} TEXT")
#         print(f"Added missing column: {col}")
# conn.commit()

# # Setup evidence directory
# if not os.path.exists(EVIDENCE_DIR):
#     os.makedirs(EVIDENCE_DIR)

# # Detection and debounce management
# detection_queue = queue.Queue()
# last_detection = {}
# shutdown_event = threading.Event()

# # IP cameras and their names
# rtsp_urls = list(CAMERA_FLOORS.keys())
# floor_names = list(CAMERA_FLOORS.values())

# # Shared frames dictionary
# frames_dict = {}
# lock = threading.Lock()

# # Camera thread to capture frames
# def camera_thread(rtsp_url, cam_idx):
#     global frames_dict
#     cap = cv2.VideoCapture(rtsp_url)
#     if not cap.isOpened():
#         print(f"[!] Failed to open stream for {floor_names[cam_idx]}")
#         return

#     while not shutdown_event.is_set():
#         ret, frame = cap.read()
#         if not ret:
#             frame = np.zeros((240, 320, 3), dtype=np.uint8)
#             cv2.putText(frame, f"{floor_names[cam_idx]} - No Signal", (10, 120),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
#         else:
#             frame = cv2.resize(frame, (320, 240))

#         with lock:
#             frames_dict[cam_idx] = frame

#     cap.release()

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

# # Face recognition processor
# def face_recognition_processor():
#     frame_count = 0
#     while not shutdown_event.is_set():
#         with lock:
#             local_frames = frames_dict.copy()

#         for cam_idx, frame in local_frames.items():
#             floor = floor_names[cam_idx]
#             frame_count += 1
#             if frame_count % PROCESS_EVERY_N_FRAMES != 0:
#                 continue

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

#         time.sleep(0.1)

# # Start camera threads
# for idx, url in enumerate(rtsp_urls):
#     t = threading.Thread(target=camera_thread, args=(url, idx))
#     t.daemon = True
#     t.start()

# # Start writer & recognition threads
# writer_thread = threading.Thread(target=database_writer)
# writer_thread.start()

# recognition_thread = threading.Thread(target=face_recognition_processor)
# recognition_thread.start()

# # Mosaic display loop
# try:
#     while not shutdown_event.is_set():
#         # Prepare frames list with black placeholders initially
#         frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(9)]

#         with lock:
#             for idx, frame in frames_dict.items():
#                 frames[idx] = frame

#         # Arrange frames into a 3x3 grid
#         row1 = np.hstack(frames[0:3])
#         row2 = np.hstack(frames[3:6])
#         row3 = np.hstack([frames[6], frames[7] if len(frames) > 7 else np.zeros_like(frames[0]), frames[8] if len(frames) > 8 else np.zeros_like(frames[0])])
#         mosaic = np.vstack([row1, row2, row3])

#         cv2.imshow("IP Camera Mosaic with Face Recognition", mosaic)

#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             shutdown_event.set()
#             break

# except KeyboardInterrupt:
#     shutdown_event.set()

# # Cleanup
# writer_thread.join()
# recognition_thread.join()
# detection_queue.join()
# observer.stop()
# observer.join()
# conn.close()
# cv2.destroyAllWindows()
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
import numpy as np
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

# Load known encodings
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

# Watch for changes to encodings
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

# Setup evidence directory
if not os.path.exists(EVIDENCE_DIR):
    os.makedirs(EVIDENCE_DIR)

# Detection and debounce management
detection_queue = queue.Queue()
last_detection = {}  # Reintroducing the debounce dictionary
shutdown_event = threading.Event()

# IP cameras and their names
rtsp_urls = list(CAMERA_FLOORS.keys())
floor_names = list(CAMERA_FLOORS.values())

# Shared frames dictionary
frames_dict = {}
lock = threading.Lock()

# Camera thread to capture frames
def camera_thread(rtsp_url, cam_idx):
    global frames_dict
    print(f"Starting camera thread for {floor_names[cam_idx]} - {rtsp_url}")
    
    # Try to open the camera with retries
    max_retries = 3
    retry_count = 0
    cap = None
    
    while retry_count < max_retries and not shutdown_event.is_set():
        try:
            cap = cv2.VideoCapture(rtsp_url)
            if cap.isOpened():
                print(f"✓ Successfully connected to {floor_names[cam_idx]}")
                break
            else:
                print(f"✗ Failed to open {floor_names[cam_idx]} - Retry {retry_count+1}/{max_retries}")
                retry_count += 1
                time.sleep(2)
        except Exception as e:
            print(f"Error opening {floor_names[cam_idx]}: {str(e)}")
            retry_count += 1
            time.sleep(2)
    
    if cap is None or not cap.isOpened():
        print(f"[!] Failed to open stream for {floor_names[cam_idx]} after {max_retries} attempts")
        # Still create a placeholder frame
        with lock:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"{floor_names[cam_idx]} - Connection Failed", (10, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            frames_dict[cam_idx] = frame
        return

    frame_count = 0
    while not shutdown_event.is_set():
        try:
            ret, frame = cap.read()
            frame_count += 1
            
            if not ret:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"{floor_names[cam_idx]} - No Signal", (10, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                # Try to reconnect every 100 frames
                if frame_count % 100 == 0:
                    print(f"Attempting to reconnect to {floor_names[cam_idx]}")
                    cap.release()
                    cap = cv2.VideoCapture(rtsp_url)
            else:
                frame = cv2.resize(frame, (640, 480))

            with lock:
                frames_dict[cam_idx] = frame
                
        except Exception as e:
            print(f"Error in camera thread for {floor_names[cam_idx]}: {str(e)}")
            with lock:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"{floor_names[cam_idx]} - Error", (10, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                frames_dict[cam_idx] = frame
                
            # Try to reconnect
            try:
                cap.release()
                time.sleep(2)
                cap = cv2.VideoCapture(rtsp_url)
            except:
                pass
                
        time.sleep(0.03)  # ~30 fps max

    if cap is not None:
        cap.release()

# Database writer
def database_writer():
    while not shutdown_event.is_set():
        try:
            name, time_now, floor, image_path, confidence = detection_queue.get(timeout=1)
            
            # Implement debounce logic
            last_time = last_detection.get(name)
            current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
            
            if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
                conn.execute("INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
                             (name, time_now, floor, image_path, confidence))
                conn.commit()
                last_detection[name] = current_time
                print(f"LOGGED to DB: {name} at {floor} ({confidence:.2f}) on {time_now}")
            else:
                print(f"Debounced: {name} at {floor} (too soon after last detection)")
            
            detection_queue.task_done()
        except queue.Empty:
            continue

# Face recognition processor (on full-size frames!)
def face_recognition_processor():
    frame_count = 0
    detection_count = 0
    last_status_time = time.time()
    
    print(f"\n[INFO] Starting face recognition processor")
    print(f"[CONFIG] Processing every {PROCESS_EVERY_N_FRAMES} frames")
    print(f"[CONFIG] Recognition tolerance: 0.6")
    print(f"[CONFIG] Known faces: {len(known_faces)} ({', '.join(list(known_faces.keys()))})\n")
    
    while not shutdown_event.is_set():
        try:
            # Print status every 30 seconds
            current_time = time.time()
            if current_time - last_status_time > 30:
                print(f"[STATUS] Face recognition processor running. Processed {frame_count} frames, detected {detection_count} faces so far.")
                last_status_time = current_time
                
            with lock:
                local_frames = frames_dict.copy()
                
            if not local_frames:
                print("[WARN] No frames available. Waiting for camera connections...")
                time.sleep(1)
                continue

            for cam_idx, frame in local_frames.items():
                floor = floor_names[cam_idx]
                frame_count += 1
                
                # Skip frames based on configuration
                if frame_count % PROCESS_EVERY_N_FRAMES != 0:
                    continue
                
                # Skip empty frames or error frames
                if frame.size == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
                    print(f"[ERROR] Invalid frame from {floor}")
                    continue
                
                try:
                    # Convert to RGB for face_recognition library
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Draw text showing this frame is being processed (for debugging)
                    debug_frame = frame.copy()
                    cv2.putText(debug_frame, "PROCESSING", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    with lock:
                        frames_dict[cam_idx] = debug_frame
                    
                    # Detect faces in the frame
                    face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=1)
                    
                    # Draw rectangle around detected face locations (for debugging)
                    debug_frame = frame.copy()
                    for face_location in face_locations:
                        top, right, bottom, left = face_location
                        cv2.rectangle(debug_frame, (left, top), (right, bottom), (255, 0, 0), 2)
                    with lock:
                        frames_dict[cam_idx] = debug_frame
                        
                    if len(face_locations) > 0:
                        print(f"[DETECT] Found {len(face_locations)} faces in {floor}")
                        detection_count += len(face_locations)
                        
                        # Get face encodings for each face
                        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                        
                        for face_encoding, face_location in zip(face_encodings, face_locations):
                            # Check if there are any known faces to compare with
                            if len(known_faces) > 0:
                                distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                                min_distance = min(distances) if len(distances) > 0 else 1.0
                                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                                name = "Unknown"
                                if True in matches:
                                    index = matches.index(True)
                                    name = list(known_faces.keys())[index]
                            else:
                                name = "Unknown"
                                min_distance = 1.0

                            print(f"[MATCH] Detected: {name} (distance={min_distance:.3f}) in {floor}")# Save evidence image
                    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    top, right, bottom, left = face_location
                    face_image = frame[top:bottom, left:right]
                    filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
                    image_path = os.path.join(EVIDENCE_DIR, filename)
                    cv2.imwrite(image_path, face_image)
                    
                    # Add to detection queue
                    confidence = 1.0 - min_distance if min_distance <= 1.0 else 0.0
                    detection_queue.put((name, time_now, floor, image_path, confidence))
        
        # Add a small sleep to avoid high CPU usage
        time.sleep(0.1)

# Start camera threads
for idx, url in enumerate(rtsp_urls):
    t = threading.Thread(target=camera_thread, args=(url, idx))
    t.daemon = True
    t.start()

# Start writer & recognition threads
writer_thread = threading.Thread(target=database_writer)
writer_thread.start()

recognition_thread = threading.Thread(target=face_recognition_processor)
recognition_thread.start()

# Mosaic display loop
try:
    while not shutdown_event.is_set():
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(9)]

        with lock:
            for idx, frame in frames_dict.items():
                small_frame = cv2.resize(frame, (320, 240))
                frames[idx] = small_frame

        row1 = np.hstack(frames[0:3])
        row2 = np.hstack(frames[3:6])
        row3 = np.hstack([frames[6], frames[7] if len(frames) > 7 else np.zeros_like(frames[0]), frames[8] if len(frames) > 8 else np.zeros_like(frames[0])])
        mosaic = np.vstack([row1, row2, row3])

        cv2.imshow("IP Camera Mosaic (Full-Frame Recognition)", mosaic)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            shutdown_event.set()
            break

except KeyboardInterrupt:
    shutdown_event.set()

# Cleanup
writer_thread.join()
recognition_thread.join()
detection_queue.join()
observer.stop()
observer.join()
conn.close()
cv2.destroyAllWindows()
print("Shutdown complete.")