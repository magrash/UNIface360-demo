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
import shutil

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
TEMP_DIR = "temp_faces"  # Directory to store temporarily detected faces
PROCESS_EVERY_N_FRAMES = config["process_every_n_frames"]

# Create temp directory for face processing
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
    print(f"Created temporary face storage: {TEMP_DIR}")

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
face_processing_queue = queue.Queue()
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
    floor = floor_names[cam_idx] if cam_idx < len(floor_names) else f"Camera {cam_idx}"
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
                
                # Only process every Nth frame to save CPU
                if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                    # Face detection (lightweight step)
                    try:
                        # Create a copy for detection to avoid modifying the display frame
                        process_frame = frame.copy()
                        
                        # Convert to RGB for face_recognition library
                        rgb_frame = cv2.cvtColor(process_frame, cv2.COLOR_BGR2RGB)
                        
                        # Detect faces in the frame - using HOG (faster than CNN)
                        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
                        
                        # Visualize detection on the display frame
                        if len(face_locations) > 0:
                            display_frame = frame.copy()
                            print(f"[DETECT] Found {len(face_locations)} faces in {floor}")
                            
                            # Draw rectangles for detected faces
                            for face_location in face_locations:
                                top, right, bottom, left = face_location
                                cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                                
                                # Save face image for later processing
                                face_img = frame[top:bottom, left:right]
                                time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                                temp_filename = f"{floor.replace(' ', '_')}_{time_stamp}.jpg"
                                temp_path = os.path.join(TEMP_DIR, temp_filename)
                                
                                # Save the face image
                                cv2.imwrite(temp_path, face_img)
                                
                                # Add to face processing queue
                                face_processing_queue.put((temp_path, floor, face_location))
                                
                            # Update the display frame with detection boxes
                            frame = display_frame
                    except Exception as e:
                        print(f"[ERROR] Face detection error in {floor}: {str(e)}")

            # Update the frame in the shared dictionary
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

# Face recognition processor - Works on saved images from the queue 
def face_recognition_processor():
    print("Starting face recognition processor thread...")
    processed_count = 0
    detected_count = 0
    
    while not shutdown_event.is_set():
        try:
            # Get a face image from the queue
            try:
                face_path, floor, face_location = face_processing_queue.get(timeout=1)
                processed_count += 1
                
                if processed_count % 50 == 0:
                    print(f"[INFO] Processed {processed_count} faces, identified {detected_count}")
                
                # Load the face image
                face_img = cv2.imread(face_path)
                if face_img is None:
                    print(f"[ERROR] Could not read face image: {face_path}")
                    continue
                
                # Convert to RGB
                rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                
                # Get face encodings - we know there's just one face in the image
                face_encodings = face_recognition.face_encodings(rgb_face)
                
                if not face_encodings:
                    print(f"[WARN] No encodings found in face image: {face_path}")
                    continue
                
                face_encoding = face_encodings[0]
                
                # Compare with known faces
                name = "Unknown"
                min_distance = 1.0
                
                if len(known_faces) > 0:
                    distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
                    min_distance = min(distances) if len(distances) > 0 else 1.0
                    matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding, tolerance=0.6)
                    
                    if True in matches:
                        index = matches.index(True)
                        name = list(known_faces.keys())[index]
                        detected_count += 1
                
                # Only process recognized faces or include Unknown faces too
                if name != "Unknown" or True:  # Change to "if name != "Unknown":" to ignore unknown faces
                    print(f"[MATCH] {name} (distance={min_distance:.3f}) in {floor}")
                    
                    # Save to evidence directory if recognized
                    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    filename = f"{name}_{time_now.replace(':', '-')}_{floor.replace(' ', '_')}.jpg"
                    evidence_path = os.path.join(EVIDENCE_DIR, filename)
                    
                    # Add text label to the evidence image
                    cv2.putText(face_img, f"{name} ({1.0-min_distance:.2f})", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Save the labeled image to evidence folder
                    cv2.imwrite(evidence_path, face_img)
                    
                    # Add to database queue
                    confidence = 1.0 - min_distance if min_distance <= 1.0 else 0.0
                    detection_queue.put((name, time_now, floor, evidence_path, confidence))
                
                # Clean up the temporary face image
                try:
                    os.remove(face_path)
                except:
                    pass
                
                face_processing_queue.task_done()
                
            except queue.Empty:
                # This is normal, just wait for more faces
                time.sleep(0.1)
                continue
                
        except Exception as e:
            print(f"[ERROR] Error in face recognition processor: {str(e)}")
            traceback.print_exc()
            time.sleep(0.5)  # short pause on error

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

            # Show status in corner of mosaic
            status_text = f"Processing Queue: {face_processing_queue.qsize()}"
            cv2.putText(mosaic, status_text, (10, mosaic.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Show the mosaic with title
            cv2.imshow("IP Camera Mosaic with Face Detection", mosaic)
            
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
    face_processing_queue.join(timeout=3)
except:
    pass

observer.stop()
observer.join(timeout=3)
conn.close()
cv2.destroyAllWindows()

# Clear temp directory
try:
    shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
except:
    pass

print("Shutdown complete.")
