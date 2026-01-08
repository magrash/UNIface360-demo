# # main_app.py

# import cv2
# import face_recognition
# import sqlite3
# import pickle
# import threading
# import queue
# import os
# import signal
# import sys
# import time
# from datetime import datetime
# import numpy as np

# # Import settings from the configuration file
# import config

# # --- Global Control ---
# shutdown_event = threading.Event()
# frame_queue = queue.Queue(maxsize=100)  # Queue for frames from all cameras
# db_queue = queue.Queue()             # Queue for detections to be written to DB

# # --- Load Known Faces ---
# def load_known_faces():
#     """Loads face encodings from the pickle file."""
#     try:
#         with open(config.ENCODINGS_FILE, "rb") as f:
#             return pickle.load(f)
#     except FileNotFoundError:
#         print(f"[ERROR] Encodings file not found: {config.ENCODINGS_FILE}")
#         sys.exit(1)
#     except Exception as e:
#         print(f"[ERROR] Could not load face encodings: {e}")
#         sys.exit(1)

# # --- Camera Streaming Thread ---
# class CameraStreamer(threading.Thread):
#     """A thread that continuously reads frames from an RTSP stream."""
#     def __init__(self, rtsp_url, location):
#         super().__init__()
#         self.rtsp_url = rtsp_url
#         self.location = location
#         self.daemon = True # Allows main thread to exit even if this thread is running

#     def run(self):
#         print(f"[INFO] Starting camera: {self.location}")
#         while not shutdown_event.is_set():
#             cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
#             if not cap.isOpened():
#                 print(f"[ERROR] Cannot open stream: {self.location}. Retrying in {config.RECONNECT_DELAY_SECONDS}s...")
#                 time.sleep(config.RECONNECT_DELAY_SECONDS)
#                 continue

#             while not shutdown_event.is_set():
#                 ret, frame = cap.read()
#                 if not ret:
#                     print(f"[WARN] Lost connection to {self.location}. Reconnecting...")
#                     break # Break inner loop to trigger reconnect
                
#                 # Put the frame and its source location into the shared queue
#                 if not frame_queue.full():
#                     frame_queue.put((frame, self.location))
                
#                 # Optional: display the raw feed
#                 if config.SHOW_WINDOWS:
#                     display_frame = frame.copy()
#                     cv2.putText(display_frame, self.location, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#                     cv2.imshow(self.location, display_frame)
#                     if cv2.waitKey(1) & 0xFF == ord('q'):
#                         shutdown_event.set()

#             cap.release()
#             if config.SHOW_WINDOWS:
#                 cv2.destroyWindow(self.location)
#         print(f"[INFO] Camera thread stopped: {self.location}")

# # --- Face Processing Thread ---
# class FaceProcessor(threading.Thread):
#     """A thread that processes frames from the queue for face recognition."""
#     def __init__(self, known_faces):
#         super().__init__()
#         self.known_faces = known_faces
#         self.frame_count = 0
#         self.daemon = True

#     def run(self):
#         print("[INFO] Starting face processor thread.")
#         while not shutdown_event.is_set():
#             try:
#                 frame, location = frame_queue.get(timeout=1)
#                 self.frame_count += 1

#                 if self.frame_count % config.PROCESS_EVERY_N_FRAMES != 0:
#                     continue

#                 # Resize for faster processing
#                 small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
#                 rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

#                 face_locations = face_recognition.face_locations(rgb_frame, model=config.FACE_DETECTION_MODEL)
#                 face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

#                 for encoding in face_encodings:
#                     distances = face_recognition.face_distance(list(self.known_faces.values()), encoding)
#                     if len(distances) == 0:
#                         continue
                    
#                     best_match_index = np.argmin(distances)
#                     if distances[best_match_index] < 0.5: # Tolerance
#                         name = list(self.known_faces.keys())[best_match_index]
                        
#                         # Prepare data for the database
#                         timestamp = datetime.now()
#                         safe_time = timestamp.strftime("%Y%m%d_%H%M%S")
#                         filename = f"{name}_{location.replace(' ', '_')}_{safe_time}.jpg"
#                         filepath = os.path.join(config.EVIDENCE_DIR, filename)
                        
#                         # Save the original, full-resolution frame as evidence
#                         cv2.imwrite(filepath, frame)
                        
#                         # Put recognition result into the database queue
#                         db_queue.put((name, timestamp, location, filepath))

#                 frame_queue.task_done()
#             except queue.Empty:
#                 continue # If queue is empty, just loop again
#         print("[INFO] Face processor thread stopped.")

# # --- Database Writer Thread ---
# class DatabaseWriter(threading.Thread):
#     """A thread that writes detection logs to the SQLite database."""
#     def __init__(self):
#         super().__init__()
#         self.last_detection = {}
#         self.daemon = True

#     def run(self):
#         print("[INFO] Starting database writer thread.")
#         conn = sqlite3.connect(config.DB_FILE)
#         cursor = conn.cursor()
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS logs (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT,
#                 time TEXT,
#                 location TEXT,
#                 image_path TEXT
#             )""")
#         conn.commit()

#         while not shutdown_event.is_set() or not db_queue.empty():
#             try:
#                 name, timestamp, location, image_path = db_queue.get(timeout=1)
                
#                 # Debounce: check if we logged this person recently
#                 last_time = self.last_detection.get((name, location))
#                 if last_time and (timestamp - last_time).total_seconds() < config.DEBOUNCE_SECONDS:
#                     db_queue.task_done()
#                     continue

#                 # Log the new detection
#                 self.last_detection[(name, location)] = timestamp
#                 time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
#                 cursor.execute("INSERT INTO logs (name, time, location, image_path) VALUES (?, ?, ?, ?)",
#                                (name, time_str, location, image_path))
#                 conn.commit()
#                 print(f"✅ [LOGGED] Found {name} at {location}")
#                 db_queue.task_done()

#             except queue.Empty:
#                 continue

#         conn.close()
#         print("[INFO] Database writer thread stopped and connection closed.")


# # --- Main Application Logic ---
# def main():
#     """Main function to start and manage all threads."""
#     # Graceful shutdown handler
#     def handle_exit(sig, frame):
#         print("\n[INFO] Shutdown signal received. Closing all threads...")
#         shutdown_event.set()
    
#     signal.signal(signal.SIGINT, handle_exit)
#     signal.signal(signal.SIGTERM, handle_exit)

#     # Prepare environment
#     os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
#     known_faces = load_known_faces()
#     print(f"[INFO] Loaded {len(known_faces)} known faces.")

#     # Start all threads
#     threads = [
#         FaceProcessor(known_faces),
#         DatabaseWriter()
#     ]
#     for url, loc in config.CAMERA_STREAMS.items():
#         threads.append(CameraStreamer(url, loc))

#     for t in threads:
#         t.start()

#     print("\n[INFO] Application running. Press Ctrl+C to exit.")
    
#     # Keep the main thread alive to handle signals
#     while not shutdown_event.is_set():
#         try:
#             time.sleep(1)
#         except KeyboardInterrupt:
#             handle_exit(None, None)

#     # Wait for all threads to complete
#     for t in threads:
#         t.join()

#     # Final cleanup
#     if config.SHOW_WINDOWS:
#         cv2.destroyAllWindows()
        
#     print("[INFO] Application shut down gracefully.")


# if __name__ == "__main__":
#     main()




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
# New: Queue for face detection results to display bounding boxes
face_results_queue = queue.Queue(maxsize=100)

# --- Load Known Faces (No Changes) ---
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

# # --- Camera Streaming Thread (No Changes) ---
# class CameraStreamer(threading.Thread):
#     """A thread that continuously reads frames from an RTSP stream."""
#     def __init__(self, rtsp_url, location):
#         super().__init__()
#         self.rtsp_url = rtsp_url
#         self.location = location
#         self.daemon = True

#     def run(self):
#         print(f"[INFO] Starting camera: {self.location}")
#         while not shutdown_event.is_set():
#             cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
#             if not cap.isOpened():
#                 print(f"[ERROR] Cannot open stream: {self.location}. Retrying in {config.RECONNECT_DELAY_SECONDS}s...")
#                 time.sleep(config.RECONNECT_DELAY_SECONDS)
#                 continue

#             while not shutdown_event.is_set():
#                 ret, frame = cap.read()
#                 if not ret:
#                     print(f"[WARN] Lost connection to {self.location}. Reconnecting...")
#                     break 
                
#                 if not frame_queue.full():
#                     frame_queue.put((frame, self.location))
                
#                 if config.SHOW_WINDOWS:
#                     display_frame = frame.copy()
#                     cv2.putText(display_frame, self.location, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#                     cv2.imshow(self.location, display_frame)
#                     if cv2.waitKey(1) & 0xFF == ord('q'):
#                         shutdown_event.set()

#             cap.release()
#             if config.SHOW_WINDOWS:
#                 cv2.destroyWindow(self.location)
#         print(f"[INFO] Camera thread stopped: {self.location}")


# --- Camera Streaming Thread (OPTIMIZED FOR GRID DISPLAY) ---
class CameraStreamer(threading.Thread):
    """A thread that continuously reads frames from an RTSP stream."""
    def __init__(self, rtsp_url, location, grid_display):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.location = location
        self.grid_display = grid_display
        self.daemon = True
        self.frame_skip_count = 0

    def run(self):
        print(f"[INFO] Starting camera: {self.location}")
        cap = None
        
        try:
            # The main loop continues as long as the application is running. It handles reconnects.
            while not shutdown_event.is_set():
                # Handle both RTSP URLs and webcam indexes
                if isinstance(self.rtsp_url, int):
                    # Webcam
                    cap = cv2.VideoCapture(self.rtsp_url)
                    print(f"[INFO] Connecting to webcam {self.rtsp_url}")
                else:
                    # RTSP stream
                    cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                    print(f"[INFO] Connecting to RTSP stream: {self.rtsp_url}")
                
                # Optimize capture settings
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer size for real-time
                if not isinstance(self.rtsp_url, int):  # Only for RTSP, not webcam
                    cap.set(cv2.CAP_PROP_FPS, 10)  # Limit FPS to reduce load
                
                if not cap.isOpened():
                    camera_type = "webcam" if isinstance(self.rtsp_url, int) else "RTSP stream"
                    print(f"[ERROR] Cannot open {camera_type}: {self.location}. Retrying in {config.RECONNECT_DELAY_SECONDS}s...")
                    # Check shutdown event during sleep
                    for _ in range(int(config.RECONNECT_DELAY_SECONDS * 10)):
                        if shutdown_event.is_set():
                            break
                        time.sleep(0.1)
                    continue # Retry connection

                print(f"[INFO] Connected to {self.location}")
                frame_count = 0
                
                # Inner loop processes frames from the active connection.
                while not shutdown_event.is_set():
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        print(f"[WARN] Lost connection to {self.location}. Reconnecting...")
                        break # Break inner loop to trigger cleanup and reconnect

                    frame_count += 1
                    
                    # Skip frames for display to reduce lag (display every 3rd frame)
                    if frame_count % 3 == 0:
                        # Put frames in queue, but not too many to avoid lag
                        if frame_queue.qsize() < 50:  # Limit queue size
                            # Resize frame before putting in queue to reduce memory usage
                            small_frame = cv2.resize(frame, (640, 480))  # Much smaller for processing
                            frame_queue.put((small_frame, self.location, frame))  # Include original for evidence
                    
                    # Send frame to grid display (every 2nd frame to reduce load)
                    if config.SHOW_WINDOWS and frame_count % 2 == 0:
                        display_frame = cv2.resize(frame, (400, 300))  # Grid cell size
                        
                        # Check for face detection results for this camera
                        current_face_results = self.get_face_results()
                        
                        # Draw bounding boxes if we have face results
                        if current_face_results:
                            for face_result in current_face_results:
                                left, top, right, bottom = face_result['location']
                                name = face_result['name']
                                confidence = face_result['confidence']
                                color = face_result['color']
                                
                                # Scale coordinates to display frame size
                                scale_x = 400 / 640  # display_width / processing_width
                                scale_y = 300 / 480  # display_height / processing_height
                                
                                left = int(left * scale_x)
                                top = int(top * scale_y)
                                right = int(right * scale_x)
                                bottom = int(bottom * scale_y)
                                
                                # Draw bounding box
                                cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
                                
                                # Draw label
                                label = f"{name} ({confidence:.2f})"
                                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                                cv2.rectangle(display_frame, (left, top - label_size[1] - 5), 
                                            (left + label_size[0], top), color, -1)
                                cv2.putText(display_frame, label, (left, top - 3), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                        # Draw location label
                        cv2.putText(display_frame, self.location, (5, 20), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Update grid display
                        self.grid_display.update_camera(self.location, display_frame)

                # Cleanup for THIS thread's connection
                if cap is not None:
                    cap.release()
        
        except Exception as e:
            print(f"[ERROR] Camera thread {self.location} error: {e}")
        finally:
            # Final cleanup
            if cap is not None:
                cap.release()
        
        print(f"[INFO] Camera thread stopped: {self.location}")

    def get_face_results(self):
        """Get face detection results for this camera from the queue."""
        current_face_results = None
        temp_queue = []
        
        # Look for recent face results for this camera
        while not face_results_queue.empty():
            try:
                result_location, face_results, _ = face_results_queue.get_nowait()
                if result_location == self.location:
                    current_face_results = face_results
                else:
                    temp_queue.append((result_location, face_results, _))
            except queue.Empty:
                break
        
        # Put back results for other cameras
        for item in temp_queue:
            if not face_results_queue.full():
                face_results_queue.put(item)
        
        return current_face_results


# --- Grid Display Manager ---
class GridDisplay:
    """Manages a grid display of multiple camera feeds."""
    def __init__(self):
        self.camera_frames = {}
        self.cell_width = 400
        self.cell_height = 300
        
        # Calculate optimal grid layout based on number of cameras
        num_cameras = len(config.CAMERA_STREAMS)
        self.grid_cols, self.grid_rows = self.calculate_optimal_grid(num_cameras)
        
        self.grid_width = self.grid_cols * self.cell_width
        self.grid_height = self.grid_rows * self.cell_height
        
        # Create position mapping for cameras
        self.camera_positions = {}
        camera_list = list(config.CAMERA_STREAMS.values())
        for i, location in enumerate(camera_list):
            row = i // self.grid_cols
            col = i % self.grid_cols
            self.camera_positions[location] = (row, col)
        
        print(f"[INFO] Grid Display initialized: {self.grid_rows}x{self.grid_cols} grid for {num_cameras} cameras")
        print(f"[INFO] Camera positions: {self.camera_positions}")
    
    def calculate_optimal_grid(self, num_cameras):
        """Calculate optimal grid dimensions based on number of cameras."""
        if num_cameras <= 0:
            return 1, 1
        elif num_cameras == 1:
            return 1, 1
        elif num_cameras <= 4:
            return 2, 2
        elif num_cameras <= 6:
            return 3, 2
        elif num_cameras <= 9:
            return 3, 3
        elif num_cameras <= 12:
            return 4, 3
        elif num_cameras <= 16:
            return 4, 4
        elif num_cameras <= 20:
            return 5, 4
        elif num_cameras <= 25:
            return 5, 5
        else:
            # For more than 25 cameras, use a 6x grid and expand rows as needed
            cols = 6
            rows = (num_cameras + cols - 1) // cols  # Ceiling division
            return cols, rows

    def update_camera(self, location, frame):
        """Update a specific camera's frame in the grid."""
        self.camera_frames[location] = frame
        
        # Update the grid display
        if config.SHOW_WINDOWS:
            self.display_grid()

    def display_grid(self):
        """Display all cameras in a grid layout."""
        # Create empty grid
        grid_image = np.zeros((self.grid_height, self.grid_width, 3), dtype=np.uint8)
        
        # Place each camera frame in its position
        for location, frame in self.camera_frames.items():
            if location in self.camera_positions:
                row, col = self.camera_positions[location]
                y_start = row * self.cell_height
                y_end = y_start + self.cell_height
                x_start = col * self.cell_width
                x_end = x_start + self.cell_width
                
                # Ensure frame is the right size
                if frame.shape[:2] != (self.cell_height, self.cell_width):
                    frame = cv2.resize(frame, (self.cell_width, self.cell_height))
                
                grid_image[y_start:y_end, x_start:x_end] = frame
        
        # Fill empty cells with placeholder and show camera status
        active_cameras = set(self.camera_frames.keys())
        all_cameras = set(config.CAMERA_STREAMS.values())
        
        for location in all_cameras:
            if location in self.camera_positions and location not in active_cameras:
                # Show placeholder for inactive cameras
                row, col = self.camera_positions[location]
                y_start = row * self.cell_height
                y_end = y_start + self.cell_height
                x_start = col * self.cell_width
                x_end = x_start + self.cell_width
                
                # Create placeholder frame (dark gray)
                placeholder = np.full((self.cell_height, self.cell_width, 3), 30, dtype=np.uint8)
                
                # Add status text
                status_text = f"{location}"
                text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                text_x = x_start + (self.cell_width - text_size[0]) // 2
                text_y = y_start + (self.cell_height + text_size[1]) // 2
                
                cv2.putText(placeholder, status_text, (self.cell_width//2 - text_size[0]//2, self.cell_height//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2)
                cv2.putText(placeholder, "CONNECTING...", (self.cell_width//2 - 60, self.cell_height//2 + 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 200), 1)
                
                grid_image[y_start:y_end, x_start:x_end] = placeholder
        
        # Draw grid lines
        for i in range(1, self.grid_rows):
            y = i * self.cell_height
            cv2.line(grid_image, (0, y), (self.grid_width, y), (128, 128, 128), 2)
        
        for i in range(1, self.grid_cols):
            x = i * self.cell_width
            cv2.line(grid_image, (x, 0), (x, self.grid_height), (128, 128, 128), 2)
        
        # Add comprehensive status information
        total_cameras = len(config.CAMERA_STREAMS)
        active_count = len(self.camera_frames)
        status_text = f"Cameras: {active_count}/{total_cameras} | Press 'q' to quit"
        cv2.putText(grid_image, status_text, (10, self.grid_height - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add grid layout info
        layout_text = f"Grid: {self.grid_rows}x{self.grid_cols}"
        cv2.putText(grid_image, layout_text, (10, self.grid_height - 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.imshow("Camera Grid - Multi-Camera Face Recognition System", grid_image)
        
        # Check for key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[INFO] 'q' key pressed. Initiating shutdown...")
            shutdown_event.set()




# --- Face Processing Thread (OPTIMIZED FOR RTSP WITH VISUALIZATION) ---
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
                    # Get frame data (small_frame for processing, location, original_frame for evidence)
                    frame_data = frame_queue.get(timeout=0.5)
                    
                    # Handle both 2-tuple (webcam) and 3-tuple (RTSP) formats
                    if len(frame_data) == 3:
                        small_frame, location, original_frame = frame_data
                    else:
                        small_frame, location = frame_data
                        original_frame = small_frame  # Use same frame for evidence
                    
                    self.frame_count += 1

                    if self.frame_count % config.PROCESS_EVERY_N_FRAMES != 0:
                        frame_queue.task_done()
                        continue

                    # Check shutdown again before processing
                    if shutdown_event.is_set():
                        frame_queue.task_done()
                        break

                    print(f"[DEBUG] Processing frame {self.frame_count} from {location}")

                    # Use the small frame for face recognition (already resized)
                    processing_frame = small_frame.copy()
                    original_processing_frame = processing_frame.copy()  # Keep copy for bounding boxes
                    
                    # Apply cropping if enabled
                    crop_offset_x = 0
                    if config.CROP_FRAME:
                        h, w, _ = processing_frame.shape
                        start_percent, end_percent = config.CROP_HORIZONTAL_REGION_PERCENT
                        start_col = int(w * start_percent)
                        end_col = int(w * end_percent)
                        crop_offset_x = start_col  # Remember offset for bounding box adjustment
                        processing_frame = processing_frame[:, start_col:end_col]

                    # Convert to RGB for face_recognition library
                    rgb_frame = cv2.cvtColor(processing_frame, cv2.COLOR_BGR2RGB)

                    # Find faces with reduced upsampling for speed
                    face_locations = face_recognition.face_locations(rgb_frame, 
                                                                    number_of_times_to_upsample=1,
                                                                    model=config.FACE_DETECTION_MODEL)
                    
                    face_results = []  # Store results for visualization
                    
                    if len(face_locations) > 0:
                        print(f"[DEBUG] Found {len(face_locations)} faces in {location}")
                        
                        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                        for i, (encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
                            if shutdown_event.is_set():
                                break
                                
                            distances = face_recognition.face_distance(list(self.known_faces.values()), encoding)
                            if len(distances) == 0:
                                continue
                            
                            best_match_index = np.argmin(distances)
                            confidence = 1.0 - distances[best_match_index]
                            
                            # Adjust face location for cropping offset and scale to display size
                            top, right, bottom, left = face_location
                            
                            # Adjust for crop offset
                            left += crop_offset_x
                            right += crop_offset_x
                            
                            name = "Unknown"
                            color = (0, 0, 255)  # Red for unknown
                            
                            # Lower threshold for better detection
                            if distances[best_match_index] < 0.6:  # Increased from 0.5 to 0.6
                                name = list(self.known_faces.keys())[best_match_index]
                                color = (0, 255, 0)  # Green for known
                                
                                print(f"[DETECTED] Found {name} with confidence {confidence:.2f} at {location}")
                                
                                timestamp = datetime.now()
                                safe_time = timestamp.strftime("%Y%m%d_%H%M%S")
                                filename = f"{name}_{location.replace(' ', '_')}_{safe_time}.jpg"
                                filepath = os.path.join(config.EVIDENCE_DIR, filename)
                                
                                # Save the original high-res frame as evidence
                                cv2.imwrite(filepath, original_frame)
                                
                                if not shutdown_event.is_set():
                                    db_queue.put((name, timestamp, location, filepath))
                            
                            # Store face result for visualization
                            face_results.append({
                                'location': (left, top, right, bottom),
                                'name': name,
                                'confidence': confidence,
                                'color': color
                            })
                    
                    # Send face results for visualization (non-blocking)
                    if not face_results_queue.full():
                        face_results_queue.put((location, face_results, original_processing_frame))

                    frame_queue.task_done()
                except queue.Empty:
                    continue  # Check shutdown event and try again
        except Exception as e:
            print(f"[ERROR] Face processor error: {e}")
        finally:
            print("[INFO] Face processor thread stopped.")


# --- Database Writer Thread (FIXED FOR BETTER SHUTDOWN) ---
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
                    name, timestamp, location, image_path = db_queue.get(timeout=0.5)  # Shorter timeout
                    
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
                    continue  # Check shutdown event and try again
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


# --- Main Application Logic (UPDATED FOR GRID DISPLAY) ---
def main():
    """Main function to start and manage all threads."""
    def handle_exit(sig=None, frame=None):
        print("\n[INFO] Shutdown signal received. Closing all threads...")
        shutdown_event.set()
        # Force close CV2 windows
        cv2.destroyAllWindows()
    
    # Signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
    known_faces = load_known_faces()
    print(f"[INFO] Loaded {len(known_faces)} known faces.")

    # Validate camera configuration
    num_cameras = len(config.CAMERA_STREAMS)
    if num_cameras == 0:
        print("[ERROR] No cameras configured in config.py. Please add camera streams to CAMERA_STREAMS.")
        sys.exit(1)
    
    print(f"[INFO] Configured {num_cameras} cameras:")
    for i, (url, location) in enumerate(config.CAMERA_STREAMS.items(), 1):
        print(f"  {i}. {location}: {url}")

    # Create grid display manager
    grid_display = GridDisplay()

    threads = [
        FaceProcessor(known_faces),
        DatabaseWriter()
    ]
    
    # Create camera threads with grid display reference
    for url, loc in config.CAMERA_STREAMS.items():
        threads.append(CameraStreamer(url, loc, grid_display))

    # Start all threads as non-daemon to ensure proper cleanup
    for t in threads:
        t.daemon = False  # Override daemon setting for proper shutdown
        t.start()

    print(f"\n[INFO] Application running with {num_cameras} cameras in {grid_display.grid_rows}x{grid_display.grid_cols} grid layout.")
    print("[INFO] Press 'q' in the grid window or Ctrl+C to exit.")
    
    try:
        while not shutdown_event.is_set():
            time.sleep(0.1)  # Shorter sleep for more responsive shutdown
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Shutting down...")
        handle_exit()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        handle_exit()

    # Wait for all threads to complete with timeout
    print("[INFO] Waiting for threads to finish...")
    for t in threads:
        t.join(timeout=2.0)  # 2 second timeout per thread
        if t.is_alive():
            print(f"[WARN] Thread {t.name} did not stop gracefully")

    # Final cleanup
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