#!/usr/bin/env python3
"""
Test version of main_app.py that uses webcam instead of RTSP for easy testing
"""

import cv2
import face_recognition
import sqlite3
import pickle
import threading
import queue
import os
import signal
import sys
import time
from datetime import datetime
import numpy as np

# Import settings from the configuration file
import config

# --- Global Control ---
shutdown_event = threading.Event()
frame_queue = queue.Queue(maxsize=100)
db_queue = queue.Queue()

# --- Load Known Faces ---
def load_known_faces():
    """Loads face encodings from the pickle file."""
    try:
        with open(config.ENCODINGS_FILE, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Encodings file not found: {config.ENCODINGS_FILE}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Could not load face encodings: {e}")
        sys.exit(1)

# --- Webcam Streaming Thread (for testing) ---
class WebcamStreamer(threading.Thread):
    """A thread that continuously reads frames from webcam."""
    def __init__(self, camera_id=0, location="Webcam"):
        super().__init__()
        self.camera_id = camera_id
        self.location = location
        self.daemon = True

    def run(self):
        print(f"[INFO] Starting camera: {self.location}")
        cap = None
        
        try:
            cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                print(f"[ERROR] Cannot open webcam {self.camera_id}")
                return

            while not shutdown_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    print(f"[WARN] Failed to read from webcam")
                    time.sleep(0.1)
                    continue

                if not frame_queue.full():
                    frame_queue.put((frame, self.location))
                
                if config.SHOW_WINDOWS:
                    display_frame = frame.copy()
                    cv2.putText(display_frame, self.location, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(display_frame, "Press 'q' to quit", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.imshow(self.location, display_frame)
                    
                    # Check for key press and shutdown event
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or shutdown_event.is_set():
                        print("[INFO] 'q' key pressed or shutdown requested. Initiating shutdown...")
                        shutdown_event.set()
                        break

        except Exception as e:
            print(f"[ERROR] Webcam thread error: {e}")
        finally:
            if cap is not None:
                cap.release()
            if config.SHOW_WINDOWS:
                try:
                    cv2.destroyWindow(self.location)
                except cv2.error:
                    pass
        
        print(f"[INFO] Camera thread stopped: {self.location}")

# --- Face Processing Thread ---
class FaceProcessor(threading.Thread):
    """A thread that processes frames from the queue for face recognition."""
    def __init__(self, known_faces):
        super().__init__()
        self.known_faces = known_faces
        self.frame_count = 0
        self.daemon = True

    def run(self):
        print("[INFO] Starting face processor thread.")
        try:
            while not shutdown_event.is_set():
                try:
                    frame, location = frame_queue.get(timeout=0.5)
                    self.frame_count += 1

                    if self.frame_count % config.PROCESS_EVERY_N_FRAMES != 0:
                        frame_queue.task_done()
                        continue

                    if shutdown_event.is_set():
                        frame_queue.task_done()
                        break

                    # Resize for faster processing
                    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                    face_locations = face_recognition.face_locations(rgb_frame, model=config.FACE_DETECTION_MODEL)
                    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                    for encoding in face_encodings:
                        if shutdown_event.is_set():
                            break
                            
                        distances = face_recognition.face_distance(list(self.known_faces.values()), encoding)
                        if len(distances) == 0:
                            continue
                        
                        best_match_index = np.argmin(distances)
                        if distances[best_match_index] < 0.5:
                            name = list(self.known_faces.keys())[best_match_index]
                            
                            timestamp = datetime.now()
                            safe_time = timestamp.strftime("%Y%m%d_%H%M%S")
                            filename = f"{name}_{location.replace(' ', '_')}_{safe_time}.jpg"
                            filepath = os.path.join(config.EVIDENCE_DIR, filename)
                            
                            cv2.imwrite(filepath, frame)
                            
                            if not shutdown_event.is_set():
                                db_queue.put((name, timestamp, location, filepath))

                    frame_queue.task_done()
                except queue.Empty:
                    continue
        except Exception as e:
            print(f"[ERROR] Face processor error: {e}")
        finally:
            print("[INFO] Face processor thread stopped.")

# --- Database Writer Thread ---
class DatabaseWriter(threading.Thread):
    """A thread that writes detection logs to the SQLite database."""
    def __init__(self):
        super().__init__()
        self.last_detection = {}
        self.daemon = True

    def run(self):
        print("[INFO] Starting database writer thread.")
        conn = None
        try:
            conn = sqlite3.connect(config.DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    time TEXT,
                    location TEXT,
                    image_path TEXT
                )""")
            conn.commit()

            while not shutdown_event.is_set() or not db_queue.empty():
                try:
                    name, timestamp, location, image_path = db_queue.get(timeout=0.5)
                    
                    last_time = self.last_detection.get((name, location))
                    if last_time and (timestamp - last_time).total_seconds() < config.DEBOUNCE_SECONDS:
                        db_queue.task_done()
                        continue

                    self.last_detection[(name, location)] = timestamp
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO logs (name, time, location, image_path) VALUES (?, ?, ?, ?)",
                                   (name, time_str, location, image_path))
                    conn.commit()
                    print(f"✅ [LOGGED] Found {name} at {location}")
                    db_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[ERROR] Database error: {e}")
                    try:
                        db_queue.task_done()
                    except:
                        pass

        except Exception as e:
            print(f"[ERROR] Database writer error: {e}")
        finally:
            if conn:
                conn.close()
            print("[INFO] Database writer thread stopped and connection closed.")

# --- Main Application Logic ---
def main():
    """Main function to start and manage all threads."""
    def handle_exit(sig=None, frame=None):
        print("\n[INFO] Shutdown signal received. Closing all threads...")
        shutdown_event.set()
        cv2.destroyAllWindows()
    
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
    known_faces = load_known_faces()
    print(f"[INFO] Loaded {len(known_faces)} known faces.")

    # Use webcam instead of RTSP for testing
    threads = [
        FaceProcessor(known_faces),
        DatabaseWriter(),
        WebcamStreamer(0, "Test Webcam")  # Use webcam for easy testing
    ]

    # Start all threads
    for t in threads:
        t.daemon = False
        t.start()

    print("\n[INFO] Application running. Press Ctrl+C or 'q' in the video window to exit.")
    
    try:
        while not shutdown_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Shutting down...")
        handle_exit()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        handle_exit()

    # Wait for all threads to complete with timeout
    print("[INFO] Waiting for threads to finish...")
    for t in threads:
        t.join(timeout=2.0)
        if t.is_alive():
            print(f"[WARN] Thread {t.name} did not stop gracefully")

    cv2.destroyAllWindows()
    print("[INFO] Application shut down gracefully.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Application interrupted by user")
        cv2.destroyAllWindows()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Application failed: {e}")
        cv2.destroyAllWindows()
        sys.exit(1)
