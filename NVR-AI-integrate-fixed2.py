import cv2
import face_recognition
import sqlite3
import pickle
import os
import yaml
import threading
import queue
import time
import traceback
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
        print(f"Loaded {len(data)} encodings.")
        print(f"Known faces: {', '.join(list(data.keys()))}")
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
    print(f"Created evidence directory: {EVIDENCE_DIR}")

# Detection and debounce management
detection_queue = queue.Queue()
last_detection = {}  # For debounce logic
shutdown_event = threading.Event()

# IP cameras and their names
rtsp_urls = list(CAMERA_FLOORS.keys())
floor_names = list(CAMERA_FLOORS.values())

print(f"Configured cameras:")
for url, floor in zip(rtsp_urls, floor_names):
    print(f" - {floor}: {url}")

# Shared frames dictionary
frames_dict = {}
lock = threading.Lock()

# Camera thread to capture frames
def camera_thread(rtsp_url, cam_idx):
    global frames_dict
    floor = floor_names[cam_idx]
    print(f"Starting camera thread for {floor} - {rtsp_url}")
    
    # Try to open the camera with retries
    max_retries = 3
    retry_count = 0
    cap = None
    
    while retry_count < max_retries and not shutdown_event.is_set():
        try:
            cap = cv2.VideoCapture(rtsp_url)
            if cap.isOpened():
                print(f"✓ Successfully connected to {floor}")
                break
            else:
                print(f"✗ Failed to open {floor} - Retry {retry_count+1}/{max_retries}")
                retry_count += 1
                time.sleep(2)
        except Exception as e:
            print(f"Error opening {floor}: {str(e)}")
            retry_count += 1
            time.sleep(2)
    
    if cap is None or not cap.isOpened():
        print(f"[!] Failed to open stream for {floor} after {max_retries} attempts")
        # Still create a placeholder frame
        with lock:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"{floor} - Connection Failed", (10, 240),
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
                cv2.putText(frame, f"{floor} - No Signal", (10, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                # Try to reconnect every 100 frames
                if frame_count % 100 == 0:
                    print(f"Attempting to reconnect to {floor}")
                    cap.release()
                    cap = cv2.VideoCapture(rtsp_url)
            else:
                frame = cv2.resize(frame, (640, 480))

            with lock:
                frames_dict[cam_idx] = frame
                
        except Exception as e:
            print(f"Error in camera thread for {floor}: {str(e)}")
            with lock:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"{floor} - Error", (10, 240),
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
    print("Starting database writer thread...")
    db_writes = 0
    db_skipped = 0
    
    while not shutdown_event.is_set():
        try:
            name, time_now, floor, image_path, confidence = detection_queue.get(timeout=1)
            
            # Implement debounce logic
            last_time = last_detection.get(name)
            current_time = datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
            
            if last_time is None or (current_time - last_time).total_seconds() >= DEBOUNCE_SECONDS:
                try:
                    conn.execute("INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
                                (name, time_now, floor, image_path, confidence))
                    conn.commit()
                    last_detection[name] = current_time
                    db_writes += 1
                    print(f"[DB] LOGGED: {name} at {floor} ({confidence:.2f}) on {time_now}")
                except Exception as e:
                    print(f"[DB] ERROR writing to database: {str(e)}")
            else:
                db_skipped += 1
                print(f"[DB] DEBOUNCED: {name} at {floor} (too soon after last detection)")
            
            if (db_writes + db_skipped) % 10 == 0:
                print(f"[DB] Stats: {db_writes} written, {db_skipped} debounced")
                
            detection_queue.task_done()
        except queue.Empty:
            continue

# Face recognition processor 
def face_recognition_processor():
    print("Starting face recognition processor thread...")
    frame_count = 0
    detection_count = 0
    last_status_time = time.time()
    process_count = 0
    
    while not shutdown_event.is_set():
        try:
            # Print status every 30 seconds
            current_time = time.time()
            if current_time - last_status_time > 30:
                print(f"[STATUS] Processed {process_count}/{frame_count} frames, detected {detection_count} faces")
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
                
                process_count += 1
                
                # Skip empty frames or error frames
                if frame is None or frame.size == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
                    print(f"[ERROR] Invalid frame from {floor}")
                    continue
                
                try:
                    # Draw text showing this frame is being processed (for debugging)
                    debug_frame = frame.copy()
                    cv2.putText(debug_frame, "PROCESSING", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    with lock:
                        frames_dict[cam_idx] = debug_frame
                    
                    # Convert to RGB for face_recognition library
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Detect faces in the frame
                    face_locations = face_recognition.face_locations(rgb_frame, model="hog")
                    
                    # Overlay rectangles on detected faces
                    debug_frame = frame.copy()
                    for face_location in face_locations:
                        top, right, bottom, left = face_location
                        cv2.rectangle(debug_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    with lock:
                        frames_dict[cam_idx] = debug_frame
                    
                    if len(face_locations) > 0:
                        print(f"[DETECT] Found {len(face_locations)} faces in {floor}")
                        detection_count += len(face_locations)
                        
                        # Get face encodings for each face detected
                        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                        
                        for face_encoding, face_location in zip(face_encodings, face_locations):
                            name = "Unknown"
                            min_distance = 1.0
                            
                            # Compare with known faces
                            if len(known_faces) > 0:
                                distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                                min_distance = min(distances) if len(distances) > 0 else 1.0
                                matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                                
                                if True in matches:
                                    index = matches.index(True)
                                    name = list(known_faces.keys())[index]
                            
                            # Only process recognized faces or include Unknown faces too
                            # if name != "Unknown":  # Uncomment to ignore unknown faces
                            
                            print(f"[MATCH] {name} (distance={min_distance:.3f}) in {floor}")
                            
                            # Save evidence image
                            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            top, right, bottom, left = face_location
                            face_image = frame[top:bottom, left:right]
                            filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
                            image_path = os.path.join(EVIDENCE_DIR, filename)
                            
                            try:
                                cv2.imwrite(image_path, face_image)
                                # Add to detection queue
                                confidence = 1.0 - min_distance if min_distance <= 1.0 else 0.0
                                detection_queue.put((name, time_now, floor, image_path, confidence))
                            except Exception as e:
                                print(f"[ERROR] Failed to save evidence image: {str(e)}")
                    
                except Exception as e:
                    print(f"[ERROR] Error processing frame from {floor}: {str(e)}")
                    traceback.print_exc()
            
            # Add a small sleep to avoid high CPU usage
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[ERROR] Error in face recognition processor: {str(e)}")
            traceback.print_exc()
            time.sleep(1)  # Longer sleep on error

# Start camera threads
print(f"Starting {len(rtsp_urls)} camera threads...")
for idx, url in enumerate(rtsp_urls):
    t = threading.Thread(target=camera_thread, args=(url, idx))
    t.daemon = True
    t.start()
    time.sleep(0.5)  # Stagger camera thread starts

# Start writer & recognition threads
writer_thread = threading.Thread(target=database_writer)
writer_thread.daemon = True
writer_thread.start()

recognition_thread = threading.Thread(target=face_recognition_processor)
recognition_thread.daemon = True
recognition_thread.start()

print("All threads started. Starting mosaic display...")

# Mosaic display loop
try:
    while not shutdown_event.is_set():
        # Create placeholder frames
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(9)]
        
        # Fill in available frames
        with lock:
            for idx, frame in frames_dict.items():
                if idx < len(frames):  # Ensure we don't go out of bounds
                    try:
                        small_frame = cv2.resize(frame, (320, 240))
                        frames[idx] = small_frame
                    except:
                        # If resize fails, use placeholder
                        cv2.putText(frames[idx], f"Cam {idx} - Error", (10, 120),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        try:
            # Create mosaic layout
            row1 = np.hstack(frames[0:3])
            row2 = np.hstack(frames[3:6])
            row3 = np.hstack(frames[6:9])
            mosaic = np.vstack([row1, row2, row3])

            # Show the mosaic with title
            cv2.imshow("IP Camera Mosaic with Face Recognition", mosaic)
            
            # Check for quit command
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Quit command received. Shutting down...")
                shutdown_event.set()
                break
                
        except Exception as e:
            print(f"Error in display loop: {str(e)}")
            time.sleep(0.5)

except KeyboardInterrupt:
    print("Keyboard interrupt received. Shutting down...")
    shutdown_event.set()

# Cleanup
print("Cleaning up resources...")
writer_thread.join(timeout=3)
recognition_thread.join(timeout=3)

try:
    detection_queue.join(timeout=3)
except:
    pass

observer.stop()
observer.join(timeout=3)
conn.close()
cv2.destroyAllWindows()
print("Shutdown complete.")
