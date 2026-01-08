"""
UNIface360 Realtime Safety Demo
================================

Standalone Flask demo that showcases:
- Neon / futuristic landing page
- Two live camera feeds from the browser (normal + restricted area)
- Realtime notifications via Server-Sent Events (SSE)
- Four simulated detection types:
  * Smoking Detection
  * Unauthorized Person
  * Restricted Area
  * PPE (Missing Hardhat)

How to run
----------
1. Create / activate your virtual environment (optional but recommended).
2. Install dependencies (Flask is already in this project requirements):
   pip install -r requirements.txt
3. Run this demo app:
   python demo.py
4. Open the browser at:
   http://127.0.0.1:5000/

How to trigger detections
-------------------------
- Use the buttons in the "Explore the Demo" section:
  * "Simulate locally" -> triggers alerts purely on the frontend.
  * "Trigger via backend" -> sends a POST request to a /trigger/* route;
    the backend then emits an SSE event which the frontend receives.
- You can also trigger via HTTP tools, e.g.:
  curl -X POST http://127.0.0.1:5000/trigger/smoking
  curl -X POST http://127.0.0.1:5000/trigger/unauthorized
  curl -X POST http://127.0.0.1:5000/trigger/restricted
  curl -X POST http://127.0.0.1:5000/trigger/ppe
"""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime
from typing import Dict, Generator, List

import base64
import io
import os
import pickle
import sys

import numpy as np
import face_recognition
import cv2
from flask import Flask, Response, jsonify, render_template, request
from flask_mail import Mail, Message

from config import ENCODINGS_FILE


app = Flask(__name__)

# ---------------------------------------------------------------------------
# YOLO-based PPE (Hardhat) Detection
# ---------------------------------------------------------------------------

_ppe_net = None
_ppe_output_layers = None
_ppe_model_loaded = False
_ppe_model_lock = threading.Lock()
_ppe_inference_lock = threading.Lock()  # Lock for thread-safe inference

PPE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "simple ppe", "yolov3_ppe2.cfg")
PPE_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "simple ppe", "yolov3_ppe2_last.weights")


def _load_ppe_model() -> bool:
    """Load YOLO model for hardhat detection."""
    global _ppe_net, _ppe_output_layers, _ppe_model_loaded
    
    with _ppe_model_lock:
        if _ppe_model_loaded:
            print(f"[DEBUG] PPE model already loaded: net={'OK' if _ppe_net is not None else 'None'}")
            return _ppe_net is not None
        
        print(f"[DEBUG] Checking PPE model paths:")
        print(f"[DEBUG]   Config: {PPE_CONFIG_PATH} (exists: {os.path.exists(PPE_CONFIG_PATH)})")
        print(f"[DEBUG]   Weights: {PPE_WEIGHTS_PATH} (exists: {os.path.exists(PPE_WEIGHTS_PATH)})")
        
        if not os.path.exists(PPE_CONFIG_PATH) or not os.path.exists(PPE_WEIGHTS_PATH):
            print(f"[WARN] PPE model files not found!")
            _ppe_model_loaded = True
            return False
        
        try:
            print(f"[INFO] Loading PPE YOLO model from:")
            print(f"[INFO]   {PPE_CONFIG_PATH}")
            print(f"[INFO]   {PPE_WEIGHTS_PATH}")
            _ppe_net = cv2.dnn.readNetFromDarknet(PPE_CONFIG_PATH, PPE_WEIGHTS_PATH)
            layer_names = _ppe_net.getLayerNames()
            print(f"[DEBUG] Model has {len(layer_names)} layers")
            
            unconnected = _ppe_net.getUnconnectedOutLayers()
            print(f"[DEBUG] Unconnected layers shape: {unconnected.shape}")
            if len(unconnected.shape) == 1:
                _ppe_output_layers = [layer_names[i - 1] for i in unconnected]
            else:
                _ppe_output_layers = [layer_names[i[0] - 1] for i in unconnected]
            
            print(f"[DEBUG] Output layers: {_ppe_output_layers}")
            _ppe_model_loaded = True
            print(f"[INFO] PPE YOLO model loaded successfully!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load PPE model: {e}")
            import traceback
            traceback.print_exc()
            _ppe_model_loaded = True
            return False


def detect_hardhat(frame: np.ndarray, confidence_threshold: float = 0.5) -> tuple:
    """
    Detect hardhat in frame using YOLO model.
    
    Returns:
        (detected: bool, confidence: float) - True if hardhat detected, False otherwise
    """
    global _ppe_net, _ppe_output_layers
    
    if _ppe_net is None or _ppe_output_layers is None:
        if not _load_ppe_model():
            print("[DEBUG] PPE model not loaded, returning False")
            return False, 0.0
    
    if _ppe_net is None:
        print("[DEBUG] PPE net is None after load attempt")
        return False, 0.0
    
    try:
        # Debug frame info
        print(f"[DEBUG] Frame shape: {frame.shape}, dtype: {frame.dtype}")
        
        # Make a contiguous copy of the frame to avoid memory issues
        frame_copy = np.ascontiguousarray(frame)
        
        # Create blob from image
        blob = cv2.dnn.blobFromImage(frame_copy, 1/255.0, (416, 416), (0, 0, 0), swapRB=True, crop=False)
        
        # Use lock to ensure thread-safe inference (OpenCV DNN is not thread-safe)
        with _ppe_inference_lock:
            _ppe_net.setInput(blob)
            outputs = _ppe_net.forward(_ppe_output_layers)
        
        best_confidence = 0.0
        best_class_id = -1
        
        for out in outputs:
            for detection in out:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                
                # Track best detection for debugging
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_class_id = class_id
                
                # Class ID 0 is hardhat in this model
                if class_id == 0 and confidence > confidence_threshold:
                    print(f"[DEBUG] Hardhat DETECTED! class_id={class_id}, confidence={confidence:.2%}")
                    return True, float(confidence)
        
        print(f"[DEBUG] No hardhat detected. Best detection: class_id={best_class_id}, confidence={best_confidence:.2%}, threshold={confidence_threshold}")
        return False, 0.0
    except Exception as e:
        print(f"[ERROR] Hardhat detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False, 0.0


# ---------------------------------------------------------------------------
# YOLO-based Smoke/Fire Detection (using ultralytics)
# ---------------------------------------------------------------------------

_smoke_model = None
_smoke_model_loaded = False
_smoke_model_lock = threading.Lock()
_smoke_inference_lock = threading.Lock()

SMOKE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "simple smoke", "best_nano_111.pt")
SMOKE_CONF_THRESHOLD = 0.15
SMOKE_IOU_THRESHOLD = 0.4


def _load_smoke_model() -> bool:
    """Load YOLO model for smoke/fire detection using ultralytics."""
    global _smoke_model, _smoke_model_loaded
    
    with _smoke_model_lock:
        if _smoke_model_loaded:
            print(f"[DEBUG] Smoke model already loaded: model={'OK' if _smoke_model is not None else 'None'}")
            return _smoke_model is not None
        
        print(f"[DEBUG] Checking smoke model path:")
        print(f"[DEBUG]   Model: {SMOKE_MODEL_PATH} (exists: {os.path.exists(SMOKE_MODEL_PATH)})")
        
        if not os.path.exists(SMOKE_MODEL_PATH):
            print(f"[WARN] Smoke model file not found: {SMOKE_MODEL_PATH}")
            _smoke_model_loaded = True
            return False
        
        try:
            print(f"[INFO] Loading Smoke/Fire YOLO model...")
            from ultralytics import YOLO
            _smoke_model = YOLO(SMOKE_MODEL_PATH)
            _smoke_model.to("cpu")  # Use CPU for inference
            print(f"[DEBUG] Model classes: {_smoke_model.names}")
            _smoke_model_loaded = True
            print(f"[INFO] Smoke/Fire YOLO model loaded successfully!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load smoke model: {e}")
            import traceback
            traceback.print_exc()
            _smoke_model_loaded = True
            return False


def detect_smoke_fire(frame: np.ndarray, conf_threshold: float = SMOKE_CONF_THRESHOLD) -> dict:
    """
    Detect smoke and fire in frame using YOLO model.
    
    Returns:
        dict with keys:
        - smoke_detected: bool
        - fire_detected: bool
        - smoke_confidence: float
        - fire_confidence: float
    """
    global _smoke_model
    
    result = {
        "smoke_detected": False,
        "fire_detected": False,
        "smoke_confidence": 0.0,
        "fire_confidence": 0.0
    }
    
    if _smoke_model is None:
        if not _load_smoke_model():
            print("[DEBUG] Smoke model not loaded, returning empty result")
            return result
    
    if _smoke_model is None:
        print("[DEBUG] Smoke model is None after load attempt")
        return result
    
    try:
        print(f"[DEBUG] Smoke detection - Frame shape: {frame.shape}, dtype: {frame.dtype}")
        
        # Make a contiguous copy of the frame
        frame_copy = np.ascontiguousarray(frame)
        
        # Resize frame to expected size
        frame_resized = cv2.resize(frame_copy, (512, 512))
        
        # Use lock to ensure thread-safe inference
        with _smoke_inference_lock:
            results = _smoke_model(
                frame_resized,
                conf=conf_threshold,
                iou=SMOKE_IOU_THRESHOLD,
                device="cpu",
                verbose=False
            )
        
        if results and len(results) > 0:
            detection_result = results[0]
            
            if detection_result.boxes is not None:
                boxes = detection_result.boxes.data.cpu().numpy()
                
                for box in boxes:
                    cls_id = int(box[5])
                    conf = float(box[4])
                    cls_name = _smoke_model.names[cls_id].lower()
                    
                    print(f"[DEBUG] Detected: {cls_name}, confidence: {conf:.2%}")
                    
                    if "smoke" in cls_name:
                        if conf > result["smoke_confidence"]:
                            result["smoke_detected"] = True
                            result["smoke_confidence"] = conf
                    
                    if "fire" in cls_name:
                        if conf > result["fire_confidence"]:
                            result["fire_detected"] = True
                            result["fire_confidence"] = conf
        
        if result["smoke_detected"] or result["fire_detected"]:
            print(f"[DEBUG] Smoke/Fire DETECTED! smoke={result['smoke_detected']} ({result['smoke_confidence']:.2%}), fire={result['fire_detected']} ({result['fire_confidence']:.2%})")
        else:
            print(f"[DEBUG] No smoke/fire detected")
        
        return result
    except Exception as e:
        print(f"[ERROR] Smoke/fire detection failed: {e}")
        import traceback
        traceback.print_exc()
        return result


# Configure Flask-Mail for email alerts
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'petrochoiceserver@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'lbip fpbl irss wvbo'  # Replace with the generated app password

mail = Mail(app)  # Initialize Mail after configuration


# ---------------------------------------------------------------------------
# In-memory SSE event bus
# ---------------------------------------------------------------------------

_listeners_lock = threading.Lock()
_listeners: List["queue.Queue[Dict]"] = []


# ---------------------------------------------------------------------------
# Camera streaming with cv2
# ---------------------------------------------------------------------------

_camera_locks: Dict[int, threading.Lock] = {}
_camera_captures: Dict[int, cv2.VideoCapture] = {}
_camera_frames: Dict[int, np.ndarray] = {}
_camera_threads: Dict[int, threading.Thread] = {}
_init_locks: Dict[int, threading.Lock] = {}  # Locks to prevent concurrent initialization


def _detect_available_cameras(max_cameras: int = 5) -> List[int]:
    """Detect which camera indices are available."""
    available = []
    for i in range(max_cameras):
        try:
            if sys.platform == "win32" and hasattr(cv2, "CAP_DSHOW"):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(i)
            
            if cap.isOpened():
                # Just check if opened, don't test frame read (can cause matrix assertion errors)
                available.append(i)
                cap.release()
            else:
                if cap:
                    cap.release()
        except Exception:
            pass
    
    return available


def _init_camera(camera_index: int) -> bool:
    """Initialize a camera capture with cv2 using the same approach as testcams.py."""
    # Get or create initialization lock for this camera
    if camera_index not in _init_locks:
        _init_locks[camera_index] = threading.Lock()
    
    # Prevent concurrent initialization attempts
    with _init_locks[camera_index]:
        # Check again after acquiring lock (another thread might have initialized it)
        if camera_index in _camera_captures:
            cap = _camera_captures[camera_index]
            try:
                if cap.isOpened():
                    return True
            except:
                pass
            # Camera was closed, remove it and reinitialize
            try:
                cap.release()
            except:
                pass
            if camera_index in _camera_captures:
                del _camera_captures[camera_index]
        
        try:
            # Try different methods to open camera
            cap = None
        
            # Method 1: Try CAP_DSHOW on Windows first (preferred for Windows)
            if sys.platform == "win32" and hasattr(cv2, "CAP_DSHOW"):
                try:
                    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        if cap:
                            cap.release()
                        cap = None
                except Exception as e:
                    print(f"[DEBUG] CAP_DSHOW failed for camera {camera_index}: {e}")
                    if cap:
                        try:
                            cap.release()
                        except:
                            pass
                        cap = None
            
            # Method 2: Try default backend if DSHOW failed or not Windows
            if cap is None or not cap.isOpened():
                try:
                    if cap:
                        cap.release()
                    cap = cv2.VideoCapture(camera_index)
                    if not cap.isOpened():
                        if cap:
                            cap.release()
                        cap = None
                except Exception as e:
                    print(f"[DEBUG] Default backend failed for camera {camera_index}: {e}")
                    if cap:
                        try:
                            cap.release()
                        except:
                            pass
                        cap = None
            
            if cap is None or not cap.isOpened():
                # List available cameras for debugging
                available = _detect_available_cameras()
                if available:
                    print(f"[INFO] Available cameras detected: {available}")
                else:
                    print(f"[WARN] No cameras detected as available")
                print(f"[WARN] Camera {camera_index} could not be opened.")
                return False
            
            # Set camera properties (same as testcams.py) - wrap in try/except as some cameras don't support all properties
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            except Exception as e:
                print(f"[WARN] Could not set some camera properties for camera {camera_index}: {e}")
            
            _camera_captures[camera_index] = cap
            if camera_index not in _camera_locks:
                _camera_locks[camera_index] = threading.Lock()
            _camera_frames[camera_index] = None
            print(f"[INFO] Camera {camera_index} opened successfully.")
            return True
        except Exception as e:
            print(f"[ERROR] Exception opening camera {camera_index}: {e}")
            import traceback
            traceback.print_exc()
            return False


def _camera_reader_thread(camera_index: int) -> None:
    """Background thread that continuously reads frames from a camera."""
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while camera_index in _camera_captures:
        try:
            cap = _camera_captures.get(camera_index)
            if not cap:
                print(f"[WARN] Camera {camera_index} capture object not found")
                break
            
            # Check if camera is opened before attempting to read
            try:
                if not cap.isOpened():
                    print(f"[WARN] Camera {camera_index} is not opened in reader thread")
                    break
            except Exception as e:
                print(f"[WARN] Error checking if camera {camera_index} is opened: {e}")
                break
            
            lock = _camera_locks.get(camera_index)
            if lock:
                with lock:
                    try:
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            _camera_frames[camera_index] = frame
                            consecutive_errors = 0  # Reset error counter on success
                        else:
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                print(f"[WARN] Camera {camera_index} read failed {consecutive_errors} times, stopping thread")
                                try:
                                    cap.release()
                                except:
                                    pass
                                if camera_index in _camera_captures:
                                    del _camera_captures[camera_index]
                                break
                            # Camera read returned False - don't immediately reinitialize, just wait and retry
                            if consecutive_errors <= 2:  # Only log first few failures
                                print(f"[WARN] Camera {camera_index} read returned False (attempt {consecutive_errors}/{max_consecutive_errors})")
                            # Don't release and reinitialize immediately - camera might just be busy
                            # Wait before retrying read
                            time.sleep(0.1)
                            # Check if camera is still opened before continuing
                            if not cap.isOpened():
                                print(f"[WARN] Camera {camera_index} closed, attempting reinitialize...")
                                try:
                                    cap.release()
                                except:
                                    pass
                                if camera_index in _camera_captures:
                                    del _camera_captures[camera_index]
                                time.sleep(0.5)
                                if _init_camera(camera_index):
                                    cap = _camera_captures.get(camera_index)
                                else:
                                    break
                    except cv2.error as e:
                        # OpenCV C++ exception - camera is likely disconnected or unavailable
                        consecutive_errors += 1
                        error_msg = str(e)
                        # Don't spam errors for matrix assertion failures (often recoverable)
                        if "Assertion failed" not in error_msg or consecutive_errors == 1:
                            print(f"[ERROR] OpenCV error reading from camera {camera_index}: {e} (error {consecutive_errors}/{max_consecutive_errors})")
                        
                        if consecutive_errors >= max_consecutive_errors:
                            print(f"[ERROR] Too many OpenCV errors for camera {camera_index}, stopping thread")
                            try:
                                cap.release()
                            except:
                                pass
                            if camera_index in _camera_captures:
                                del _camera_captures[camera_index]
                            break
                        # Wait longer before retrying (camera might be busy)
                        time.sleep(0.5)
                    except Exception as e:
                        # Other exceptions
                        consecutive_errors += 1
                        print(f"[ERROR] Unexpected error reading from camera {camera_index}: {e} (error {consecutive_errors}/{max_consecutive_errors})")
                        if consecutive_errors >= max_consecutive_errors:
                            try:
                                cap.release()
                            except:
                                pass
                            if camera_index in _camera_captures:
                                del _camera_captures[camera_index]
                            break
                        time.sleep(0.1)
            else:
                print(f"[WARN] No lock found for camera {camera_index}")
                break
        except Exception as e:
            consecutive_errors += 1
            print(f"[ERROR] Camera {camera_index} thread error: {e} (error {consecutive_errors}/{max_consecutive_errors})")
            if consecutive_errors >= max_consecutive_errors:
                import traceback
                traceback.print_exc()
                break
            time.sleep(0.1)
        
        # Small delay to prevent CPU spinning
        time.sleep(0.033)  # ~30 FPS
    
    print(f"[INFO] Camera {camera_index} reader thread stopped")


def _get_camera_frame(camera_index: int, fallback_to_zero: bool = True) -> np.ndarray | None:
    """
    Get the latest frame from a camera.
    
    Args:
        camera_index: Index of the camera to use
        fallback_to_zero: If True, try camera 0 if the requested camera fails
    """
    # Initialize camera if not already done
    if camera_index not in _camera_captures:
        if not _init_camera(camera_index):
            print(f"[WARN] Could not initialize camera {camera_index}")
            # Try fallback to camera 0 if requested and camera_index is not 0
            if fallback_to_zero and camera_index != 0:
                print(f"[INFO] Attempting fallback to camera 0...")
                if _init_camera(0):
                    camera_index = 0  # Use camera 0 instead
                else:
                    return None
            else:
                return None
        
        # Only start reader thread if camera is actually in captures (initialization succeeded)
        if camera_index in _camera_captures:
            # Use lock to prevent race condition when starting thread
            lock = _camera_locks.get(camera_index)
            if lock:
                with lock:
                    if camera_index not in _camera_threads or not _camera_threads[camera_index].is_alive():
                        thread = threading.Thread(target=_camera_reader_thread, args=(camera_index,), daemon=True)
                        thread.start()
                        _camera_threads[camera_index] = thread
                        print(f"[INFO] Started reader thread for camera {camera_index}")
            else:
                # Lock not available, create thread without lock (shouldn't happen, but be safe)
                if camera_index not in _camera_threads or not _camera_threads[camera_index].is_alive():
                    thread = threading.Thread(target=_camera_reader_thread, args=(camera_index,), daemon=True)
                    thread.start()
                    _camera_threads[camera_index] = thread
                    print(f"[INFO] Started reader thread for camera {camera_index}")
        else:
            print(f"[WARN] Camera {camera_index} not in captures, cannot start thread")
            return None
    
    # Verify camera is still open
    cap = _camera_captures.get(camera_index)
    if not cap or not cap.isOpened():
        print(f"[WARN] Camera {camera_index} is not opened, attempting reinitialize...")
        # Clean up old capture
        if cap:
            try:
                cap.release()
            except:
                pass
            if camera_index in _camera_captures:
                del _camera_captures[camera_index]
        
        # Wait a bit before retrying (camera might be busy)
        time.sleep(0.5)
        
        if _init_camera(camera_index):
            # Restart thread with lock to prevent race condition
            lock = _camera_locks.get(camera_index)
            if lock:
                with lock:
                    if camera_index not in _camera_threads or not _camera_threads[camera_index].is_alive():
                        thread = threading.Thread(target=_camera_reader_thread, args=(camera_index,), daemon=True)
                        thread.start()
                        _camera_threads[camera_index] = thread
            else:
                if camera_index not in _camera_threads or not _camera_threads[camera_index].is_alive():
                    thread = threading.Thread(target=_camera_reader_thread, args=(camera_index,), daemon=True)
                    thread.start()
                    _camera_threads[camera_index] = thread
        else:
            # Try fallback to camera 0
            if fallback_to_zero and camera_index != 0:
                print(f"[INFO] Attempting fallback to camera 0...")
                time.sleep(0.5)  # Wait before trying fallback
                if _init_camera(0):
                    camera_index = 0
                    lock = _camera_locks.get(0)
                    if lock:
                        with lock:
                            if 0 not in _camera_threads or not _camera_threads[0].is_alive():
                                thread = threading.Thread(target=_camera_reader_thread, args=(0,), daemon=True)
                                thread.start()
                                _camera_threads[0] = thread
                    else:
                        if 0 not in _camera_threads or not _camera_threads[0].is_alive():
                            thread = threading.Thread(target=_camera_reader_thread, args=(0,), daemon=True)
                            thread.start()
                            _camera_threads[0] = thread
                else:
                    print(f"[ERROR] Both camera {camera_index} and camera 0 failed to initialize")
                    return None
            else:
                return None
    
    frame = _camera_frames.get(camera_index)
    if frame is None:
        # Frame not ready yet - check if thread is running
        thread = _camera_threads.get(camera_index)
        if thread and thread.is_alive():
            # Thread is running, frame just not captured yet
            return None
        else:
            # Thread not running, something went wrong
            print(f"[WARN] Camera {camera_index} thread not running, frame unavailable")
            return None
    
    return frame


def _generate_camera_stream(camera_index: int) -> Generator[bytes, None, None]:
    """Generate MJPEG stream from camera."""
    while True:
        frame = _get_camera_frame(camera_index)
        if frame is None:
            # Send a placeholder frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"Camera {camera_index} not available", (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        time.sleep(0.033)  # ~30 FPS


def add_listener() -> "queue.Queue[Dict]":
    """Register a new listener queue for SSE connections."""
    q: "queue.Queue[Dict]" = queue.Queue()
    with _listeners_lock:
        _listeners.append(q)
    return q


def remove_listener(q: "queue.Queue[Dict]") -> None:
    """Unregister a listener queue (called when client disconnects)."""
    with _listeners_lock:
        if q in _listeners:
            _listeners.remove(q)


def broadcast_event(event: Dict) -> None:
    """
    Push an event to all active listeners.

    The event schema is intentionally simple and documented here so that
    frontend and backend stay in sync:

    {
        "type": "smoking" | "unauthorized" | "restricted" | "ppe",
        "demo": "Smoking Detection" | "Unauthorized Person" | "Restricted Area" | "PPE (Hardhat)",
        "level": "info" | "warning" | "critical",
        "message": "<human readable description>",
        "source": "backend",
        "timestamp": "<ISO-8601 string>",
    }
    """
    with _listeners_lock:
        listeners_snapshot = list(_listeners)

    for q in listeners_snapshot:
        try:
            q.put_nowait(event)
        except queue.Full:
            # Best-effort only; drop if a single client is too slow.
            continue


def event_stream() -> Generator[str, None, None]:
    """
    Generator used by the /events route to stream Server-Sent Events.

    Each connected client gets its own queue; we block on queue.get()
    and yield lines formatted according to the SSE spec.
    """
    q = add_listener()
    try:
        while True:
            event = q.get()
            data = json.dumps(event, separators=(",", ":"))
            # Basic SSE format – using only the default 'message' event.
            yield f"data: {data}\n\n"
    except GeneratorExit:
        # Client disconnected
        remove_listener(q)


# ---------------------------------------------------------------------------
# Detection event builder helpers
# ---------------------------------------------------------------------------

def _base_event(event_type: str, demo: str, message: str, level: str = "warning") -> Dict:
    """Base payload shared across all demo events."""
    return {
        "type": event_type,
        "demo": demo,
        "level": level,
        "message": message,
        "source": "backend",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def build_smoking_event() -> Dict:
    return _base_event(
        event_type="smoking",
        demo="Smoking Detection",
        message="Smoking activity detected in a non-smoking zone.",
        level="critical",
    )


def build_unauthorized_event() -> Dict:
    return _base_event(
        event_type="unauthorized",
        demo="Unauthorized Person",
        message="Unknown person detected in a controlled area.",
        level="critical",
    )


def build_restricted_event() -> Dict:
    return _base_event(
        event_type="restricted",
        demo="Restricted Area",
        message="Movement detected inside a restricted safety zone.",
        level="critical",
    )


def build_ppe_event() -> Dict:
    return _base_event(
        event_type="ppe",
        demo="PPE (Hardhat)",
        message="PPE violation: missing hardhat detected.",
        level="warning",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def home() -> str:
    """
    Intro landing page for the UNIface360 demo.

    This reuses the existing marketing-style `home.html` but points users
    toward the interactive safety demo.
    """
    return render_template("home.html")


@app.route("/demo")
def demo_welcome() -> str:
    """
    Welcome page that introduces the UNIface360 demo and offers four
    options (Face Recognition, Zone Monitoring, PPE Compliance, Behavior Detection).
    """
    return render_template("demo_welcome.html", datetime=datetime)


@app.route("/demo/live")
def demo_hub() -> str:
    """
    Original realtime safety demo hub with four cards and live camera
    feeds (kept for internal testing at /demo/live).
    """
    # Pass datetime into the template for the dynamic footer year.
    return render_template("index.html", datetime=datetime)


# ---------------------------------------------------------------------------
# Stub routes to satisfy links used in `home.html`
# ---------------------------------------------------------------------------

@app.route("/dashboard", endpoint="dashboard")
def dashboard_stub() -> str:
    """Lightweight placeholder for the main dashboard when running demo.py only."""
    return "<h1>UNIface360 Dashboard (stub)</h1><p>This route is provided only for the standalone demo.py app.</p>"


@app.route("/request_demo", endpoint="request_demo")
def request_demo_stub() -> str:
    """
    Request demo page stub so that `url_for('request_demo')` in home.html works
    when running only demo.py.
    """
    try:
        # Use the real template if it exists in this project.
        return render_template("request_demo.html")
    except Exception:
        return "<h1>Request a Demo</h1><p>This is a minimal placeholder page in demo.py.</p>"


@app.route("/events")
def sse_events() -> Response:
    """
    SSE endpoint consumed by the frontend using EventSource('/events').
    """
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Disable buffering in some proxies
        "Connection": "keep-alive",
    }
    return Response(event_stream(), mimetype="text/event-stream", headers=headers)


@app.route("/video_feed/<int:camera_index>")
def video_feed(camera_index: int) -> Response:
    """
    MJPEG video stream endpoint for camera feeds using cv2.
    Usage: /video_feed/0 for camera 0, /video_feed/1 for camera 1, etc.
    """
    return Response(
        _generate_camera_stream(camera_index),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.post("/trigger/smoking")
def trigger_smoking() -> Response:
    """HTTP trigger for the Smoking Detection demo."""
    event = build_smoking_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/unauthorized")
def trigger_unauthorized() -> Response:
    """HTTP trigger for the Unauthorized Person demo."""
    event = build_unauthorized_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/restricted")
def trigger_restricted() -> Response:
    """HTTP trigger for the Restricted Area demo."""
    event = build_restricted_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/ppe")
def trigger_ppe() -> Response:
    """HTTP trigger for the PPE (missing hardhat) demo."""
    event = build_ppe_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


# ---------------------------------------------------------------------------
# Email alert functionality with throttling
# ---------------------------------------------------------------------------

_last_email_time: float = 0.0
_EMAIL_COOLDOWN = 60.0  # 60 seconds cooldown between emails

_last_restricted_email_time: float = 0.0
_RESTRICTED_EMAIL_COOLDOWN = 60.0  # 60 seconds cooldown between restricted area emails

_last_ppe_email_time: float = 0.0
_PPE_EMAIL_COOLDOWN = 60.0  # 60 seconds cooldown between PPE violation emails

_last_smoking_email_time: float = 0.0
_SMOKING_EMAIL_COOLDOWN = 60.0  # 60 seconds cooldown between smoking/fire emails


def send_unauthorized_alert_email(person_info: str = "Unknown person", frame: np.ndarray | None = None) -> bool:
    """
    Send an email alert when an unauthorized person is detected.
    Uses throttling to prevent spam (max once per minute).
    
    Returns True if email was sent, False if throttled or failed.
    """
    global _last_email_time
    
    current_time = time.time()
    time_since_last_email = current_time - _last_email_time
    
    # Throttle: only send if enough time has passed
    if time_since_last_email < _EMAIL_COOLDOWN:
        print(f"[INFO] Email alert throttled. Last sent {time_since_last_email:.1f}s ago. Need {_EMAIL_COOLDOWN}s cooldown.")
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "dalia.ali@petrochoice.org"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Encode frame snapshot as base64 if provided
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                print(f"[WARN] Failed to encode frame snapshot: {e}")
        
        # Encode logo as base64 for inline embedding
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_data = fp.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        except Exception as e:
            print(f"[WARN] Failed to load logo: {e}")
        
        # Create HTML email body
        logo_img_tag = ""
        if logo_base64:
            logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />'
        else:
            logo_img_tag = '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">
        {logo_img_tag}
    </div>
    <h2 style="color: #d32f2f;">🚨 Security Alert: Unauthorized Person Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Person Status:</strong> <span style="color: #d32f2f; font-weight: bold;">Unauthorized / Unknown</span></p>
        <p><strong>Person Info:</strong> {person_info}</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #fafafa; border: 2px dashed #ccc; border-radius: 5px;">
        <p><strong>Captured Snapshot:</strong></p>
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
        <p style="font-size: 12px; color: #666; margin-top: 10px;">Frame captured at {timestamp}</p>
    </div>"""
        
        html_body += f"""
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>⚠️ Action Required:</strong> Please verify this detection and respond according to security procedures.
    </div>
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px;">
        <p>This is an automated alert from the <strong>UNIface360 Security System</strong>.</p>
    </div>
</body>
</html>"""
        
        # Plain text fallback
        text_body = f"""
UNIface360 Security Alert

An unauthorized person has been detected in a secure area.

Detection Details:
- Time: {timestamp}
- Person: {person_info}
- Status: Unauthorized / Unknown person
- Action Required: Please verify and respond according to security procedures.

This is an automated alert from the UNIface360 security system.
"""
        
        msg = Message(
            subject=f"🚨 UNIface360 Alert: Unauthorized Person Detected - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=text_body,
            html=html_body
        )
        
        # Logo is now embedded as base64 in HTML, no need to attach separately
        
        print(f"[DEBUG] Attempting to send email to {', '.join(recipients)}")
        print(f"[DEBUG] SMTP Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        
        try:
            mail.send(msg)
            _last_email_time = current_time
            print(f"[INFO] Email alert sent successfully to {', '.join(recipients)}")
            return True
        except Exception as send_error:
            print(f"[ERROR] Failed to send email: {send_error}")
            print(f"[ERROR] Error type: {type(send_error).__name__}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare email alert: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# API endpoints for frame-based checks (unauthorized, restricted, PPE)
# ---------------------------------------------------------------------------

_known_face_encodings: List[np.ndarray] = []
_known_face_names: List[str] = []
_faces_loaded = False

# Map folder-style IDs to display names (mirrors face.py:get_name_mapping)
NAME_MAPPING: Dict[str, str] = {
    "Abdelrahman_Ahmed": "Abdelrahman Ahmed",
    "Dalia": "Dalia",
    "Eng.mahmoud": "Mahmoud",
    "Eng.mostafa_magdy": "Mostafa Magdy",
    "Gamila": "Gamila",
    "Hagar": "Hagar",
    "Mahmoud_Ahmed": "Mahmoud Ahmed",
    "mohamed_ragab": "Mohamed Ragab",
    "Obama": "Obama",
    "yousef": "Yousef",
}


def _load_known_faces() -> None:
    """
    Load known faces from the same encodings file used by the main app.

    The logic mirrors the helper in `webcam_recognizer.py` so that demo.py
    behaves consistently with the production pipeline.
    """
    global _faces_loaded, _known_face_encodings, _known_face_names
    if _faces_loaded:
        return

    path = os.path.join(os.path.dirname(__file__), ENCODINGS_FILE)
    if not os.path.exists(path):
        _faces_loaded = True
        return

    try:
        # Compatibility shim for older NumPy pickles that reference
        # internal modules like "numpy._core" or "numpy._core.multiarray"
        # (removed in NumPy 2.x).
        if "numpy._core" not in sys.modules:  # type: ignore[attr-defined]
            sys.modules["numpy._core"] = np  # type: ignore[assignment]
        try:
            core = np.core  # type: ignore[attr-defined]
            if "numpy._core.multiarray" not in sys.modules:
                sys.modules["numpy._core.multiarray"] = core.multiarray  # type: ignore[attr-defined]
        except Exception:
            pass

        with open(path, "rb") as f:
            data = pickle.load(f)
    except Exception:
        _faces_loaded = True
        return

    encodings: List[np.ndarray] = []
    names: List[str] = []

    # Preferred format (used by face.py): {'encodings': [...], 'names': [...]}
    if isinstance(data, dict) and "encodings" in data and "names" in data:
        encodings = [np.array(e) for e in data.get("encodings", [])]
        names = [str(n) for n in data.get("names", [])]
    elif isinstance(data, dict):
        # Fallback: {name: encoding} or {name: [encodings]}
        for name, value in data.items():
            arr = np.array(value)
            if arr.ndim == 1:
                encodings.append(arr)
                names.append(str(name))
            elif arr.ndim == 2:
                for row in arr:
                    encodings.append(np.array(row))
                    names.append(str(name))
    elif isinstance(data, list):
        # Fallback: list of (name, encoding)
        for item in data:
            try:
                name, enc = item
            except Exception:
                continue
            arr = np.array(enc)
            if arr.ndim == 1:
                encodings.append(arr)
                names.append(str(name))
            elif arr.ndim == 2:
                for row in arr:
                    encodings.append(np.array(row))
                    names.append(str(name))

    _known_face_encodings = encodings
    _known_face_names = names
    _faces_loaded = True


def _decode_image_from_request(payload: Dict) -> np.ndarray | None:
    """Decode a base64 data URL image from JSON into a numpy RGB array."""
    image_data = payload.get("image")
    if not image_data or not isinstance(image_data, str):
        return None

    if "," in image_data:
        _, b64_data = image_data.split(",", 1)
    else:
        b64_data = image_data

    try:
        raw = base64.b64decode(b64_data)
        buffer = io.BytesIO(raw)
        from PIL import Image as PILImage

        img = PILImage.open(buffer).convert("RGB")
        return np.array(img)
    except Exception:
        return None


@app.post("/api/demo/unauthorized/check")
def api_demo_unauthorized() -> Response:
    """Check if the captured face is known; unknown = unauthorized."""
    _load_known_faces()

    payload = request.get_json(silent=True, force=True) or {}
    
    # Check if camera_index is provided instead of image
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        # Capture frame directly from camera with retry (camera thread needs time to capture)
        frame = None
        max_retries = 3  # Reduced retries to avoid too many concurrent requests
        for attempt in range(max_retries):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            # Wait longer between retries to give camera time
            if attempt < max_retries - 1:
                time.sleep(0.5)  # Increased wait time
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available", "message": "Could not capture frame from camera after retries"}), 400
    else:
        # Use provided image
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400

    face_locations = face_recognition.face_locations(frame)
    if not face_locations:
        # No face at all – treat as unauthorized for the demo.
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_face"})

    encodings = face_recognition.face_encodings(frame, face_locations)
    if not _known_face_encodings:
        # No known faces loaded; treat everything as unauthorized.
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_known_faces"})

    # Mirror the matching logic from face.py: use compare_faces with tolerance
    # and then choose the best (closest) match by distance.
    tolerance = 0.4
    best_overall = None

    for enc in encodings:
        matches = face_recognition.compare_faces(_known_face_encodings, enc, tolerance=tolerance)
        name = "Unknown"
        confidence = 0.0

        if True in matches and len(_known_face_encodings) > 0:
            distances = face_recognition.face_distance(_known_face_encodings, enc)
            best_idx = int(np.argmin(distances))
            if matches[best_idx]:
                folder_name = _known_face_names[best_idx]
                # Map folder name to display name like face.py
                name = NAME_MAPPING.get(folder_name, folder_name)
                confidence = float(max(0.0, 1.0 - float(distances[best_idx])))

        if best_overall is None or confidence > best_overall["confidence"]:
            best_overall = {"name": name, "confidence": confidence}

    if not best_overall or best_overall["name"] == "Unknown":
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_match"})

    return jsonify(
        {
            "ok": True,
            "unauthorized": False,
            "person_name": best_overall["name"],
            "confidence": best_overall["confidence"],
        }
    )


@app.post("/api/demo/restricted/check")
def api_demo_restricted() -> Response:
    """Simple person presence check in restricted zone using face detection."""
    payload = request.get_json(silent=True, force=True) or {}
    
    # Check if camera_index is provided instead of image
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        # Capture frame directly from camera with retry
        frame = None
        max_retries = 3
        for attempt in range(max_retries):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            if attempt < max_retries - 1:
                time.sleep(0.5)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available", "message": "Could not capture frame from camera after retries"}), 400
    else:
        # Use provided image
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400

    face_locations = face_recognition.face_locations(frame)
    intruder = bool(face_locations)
    return jsonify({"ok": True, "intruder": intruder})


def send_restricted_area_alert_email(frame: np.ndarray | None = None) -> bool:
    """
    Send an email alert when a person is detected in a restricted area.
    Uses throttling to prevent spam (max once per minute).
    
    Args:
        frame: Optional numpy array frame to include as snapshot
    
    Returns True if email was sent, False if throttled or failed.
    """
    global _last_restricted_email_time
    
    current_time = time.time()
    time_since_last_email = current_time - _last_restricted_email_time
    
    # Throttle: only send if enough time has passed
    if time_since_last_email < _RESTRICTED_EMAIL_COOLDOWN:
        print(f"[INFO] Restricted area email alert throttled. Last sent {time_since_last_email:.1f}s ago. Need {_RESTRICTED_EMAIL_COOLDOWN}s cooldown.")
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Encode frame snapshot as base64 if provided
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                print(f"[WARN] Failed to encode frame snapshot: {e}")
        
        # Encode logo as base64 for inline embedding
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_data = fp.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        except Exception as e:
            print(f"[WARN] Failed to load logo: {e}")
        
        # Create HTML email body
        logo_img_tag = ""
        if logo_base64:
            logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />'
        else:
            logo_img_tag = '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">
        {logo_img_tag}
    </div>
    <h2 style="color: #d32f2f;">🚨 Security Alert: Restricted Area Breach Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: #d32f2f; font-weight: bold;">Restricted Area Breach</span></p>
        <p><strong>Status:</strong> Person detected in restricted safety zone</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #fafafa; border: 2px dashed #ccc; border-radius: 5px;">
        <p><strong>Captured Snapshot:</strong></p>
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
        <p style="font-size: 12px; color: #666; margin-top: 10px;">Frame captured at {timestamp}</p>
    </div>"""
        
        html_body += f"""
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>⚠️ Action Required:</strong> A person has been detected inside the restricted safety zone. Initiate response plan immediately.
    </div>
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px;">
        <p>This is an automated alert from the <strong>UNIface360 Security System</strong>.</p>
    </div>
</body>
</html>"""
        
        # Plain text fallback
        text_body = f"""
UNIface360 Security Alert

🚨 RESTRICTED AREA BREACH DETECTED

A person has been detected inside a restricted safety zone.

Detection Details:
- Time: {timestamp}
- Alert Type: Restricted Area Breach
- Status: Person detected in restricted safety zone

Action Required: Initiate response plan immediately.

This is an automated alert from the UNIface360 security system.
"""
        
        msg = Message(
            subject=f"🚨 UNIface360 Alert: Restricted Area Breach Detected - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=text_body,
            html=html_body
        )
        
        print(f"[DEBUG] Attempting to send restricted area email to {', '.join(recipients)}")
        
        try:
            mail.send(msg)
            _last_restricted_email_time = current_time
            print(f"[INFO] Restricted area email alert sent successfully to {', '.join(recipients)}")
            return True
        except Exception as send_error:
            print(f"[ERROR] Failed to send restricted area email: {send_error}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare restricted area email alert: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_ppe_violation_alert_email(frame: np.ndarray | None = None) -> bool:
    """
    Send an email alert when a PPE violation (missing hardhat) is detected.
    Uses throttling to prevent spam (max once per minute).
    
    Args:
        frame: Optional numpy array frame to include as snapshot
    
    Returns True if email was sent, False if throttled or failed.
    """
    global _last_ppe_email_time
    
    current_time = time.time()
    time_since_last_email = current_time - _last_ppe_email_time
    
    # Throttle: only send if enough time has passed
    if time_since_last_email < _PPE_EMAIL_COOLDOWN:
        print(f"[INFO] PPE email alert throttled. Last sent {time_since_last_email:.1f}s ago. Need {_PPE_EMAIL_COOLDOWN}s cooldown.")
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Encode frame snapshot as base64 if provided
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                print(f"[WARN] Failed to encode frame snapshot: {e}")
        
        # Encode logo as base64 for inline embedding
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_data = fp.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        except Exception as e:
            print(f"[WARN] Failed to load logo: {e}")
        
        # Create HTML email body
        logo_img_tag = ""
        if logo_base64:
            logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />'
        else:
            logo_img_tag = '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">
        {logo_img_tag}
    </div>
    <h2 style="color: #ff9800;">⚠️ Safety Alert: PPE Violation Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: #ff9800; font-weight: bold;">PPE Violation - Missing Hardhat</span></p>
        <p><strong>Status:</strong> Worker detected without required hardhat in PPE zone</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #fafafa; border: 2px dashed #ccc; border-radius: 5px;">
        <p><strong>Captured Snapshot:</strong></p>
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
        <p style="font-size: 12px; color: #666; margin-top: 10px;">Frame captured at {timestamp}</p>
    </div>"""
        
        html_body += f"""
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>⚠️ Action Required:</strong> A worker has been detected without proper PPE (hardhat). Please ensure all personnel in the area are wearing required safety equipment.
    </div>
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px;">
        <p>This is an automated alert from the <strong>UNIface360 Safety System</strong>.</p>
    </div>
</body>
</html>"""
        
        # Plain text fallback
        text_body = f"""
UNIface360 Safety Alert

⚠️ PPE VIOLATION DETECTED - MISSING HARDHAT

A worker has been detected without required PPE (hardhat) in a mandatory PPE zone.

Detection Details:
- Time: {timestamp}
- Alert Type: PPE Violation - Missing Hardhat
- Status: Worker without hardhat detected

Action Required: Please ensure all personnel in the area are wearing required safety equipment.

This is an automated alert from the UNIface360 safety system.
"""
        
        msg = Message(
            subject=f"⚠️ UNIface360 Alert: PPE Violation Detected - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=text_body,
            html=html_body
        )
        
        print(f"[DEBUG] Attempting to send PPE violation email to {', '.join(recipients)}")
        
        try:
            mail.send(msg)
            _last_ppe_email_time = current_time
            print(f"[INFO] PPE violation email alert sent successfully to {', '.join(recipients)}")
            return True
        except Exception as send_error:
            print(f"[ERROR] Failed to send PPE violation email: {send_error}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare PPE violation email alert: {e}")
        import traceback
        traceback.print_exc()
        return False


@app.post("/api/demo/restricted/send-alert-email")
def api_send_restricted_email() -> Response:
    """
    Endpoint to send email alert for restricted area breach detection.
    Includes built-in throttling (60 seconds cooldown).
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    # Capture frame snapshot if camera_index is provided
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        try:
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is None:
                print(f"[WARN] Could not capture frame from camera {camera_index} for email - continuing without snapshot")
        except Exception as e:
            print(f"[WARN] Exception capturing frame for email: {e}")
            frame = None
    
    success = send_restricted_area_alert_email(frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email alert throttled or failed"}), 429


@app.post("/api/demo/smoking/flag")
def api_demo_smoking_flag() -> Response:
    """Optional backend hook for smoking simulation; currently just echoes."""
    payload = request.get_json(silent=True, force=True) or {}
    return jsonify({"ok": True, "received": bool(payload)})


@app.post("/api/demo/ppe/check")
def api_demo_ppe_check() -> Response:
    """
    PPE (hardhat) check using YOLO model.
    
    If hardhat is NOT detected, it's a violation.
    Uses camera_index from payload to capture frame directly from backend camera.
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    print(f"[DEBUG] PPE check called with payload: {payload}")
    
    # Check if camera_index is provided
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        print(f"[DEBUG] Getting frame from camera {camera_index}")
        # Capture frame directly from camera with retry
        frame = None
        max_retries = 3
        for attempt in range(max_retries):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                print(f"[DEBUG] Got frame from camera on attempt {attempt + 1}")
                break
            if attempt < max_retries - 1:
                time.sleep(0.5)
        
        if frame is None:
            print(f"[ERROR] Could not get frame from camera {camera_index}")
            return jsonify({"ok": False, "error": "camera_not_available", "message": "Could not capture frame from camera after retries"}), 400
    else:
        # Use provided image
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400
    
    print(f"[DEBUG] Frame obtained, shape: {frame.shape if frame is not None else 'None'}")
    
    # Ensure model is loaded
    if not _load_ppe_model():
        return jsonify({"ok": False, "error": "model_not_loaded", "message": "PPE detection model could not be loaded"}), 500
    
    # Detect hardhat using YOLO - using lower threshold for better detection
    hardhat_detected, confidence = detect_hardhat(frame, confidence_threshold=0.3)
    
    # Violation = no hardhat detected
    violation = not hardhat_detected
    
    return jsonify({
        "ok": True,
        "violation": violation,
        "hardhat_detected": hardhat_detected,
        "confidence": confidence
    })


@app.post("/api/demo/unauthorized/send-alert-email")
def api_send_unauthorized_email() -> Response:
    """
    Endpoint to send email alert for unauthorized person detection.
    Includes built-in throttling (60 seconds cooldown).
    """
    payload = request.get_json(silent=True, force=True) or {}
    person_info = payload.get("person_info", "Unknown person")
    
    # Capture frame snapshot if camera_index is provided
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        try:
            # Try to get frame, with fallback to camera 0 if camera_index fails
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is None:
                print(f"[WARN] Could not capture frame from camera {camera_index} for email - continuing without snapshot")
        except Exception as e:
            print(f"[WARN] Exception capturing frame for email: {e}")
            frame = None  # Continue without snapshot - email will still be sent
    
    success = send_unauthorized_alert_email(person_info, frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email alert throttled or failed"}), 429


@app.post("/api/demo/ppe/send-alert-email")
def api_send_ppe_email() -> Response:
    """
    Endpoint to send email alert for PPE violation (missing hardhat).
    Includes built-in throttling (60 seconds cooldown).
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    # Capture frame snapshot if camera_index is provided
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        try:
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is None:
                print(f"[WARN] Could not capture frame from camera {camera_index} for PPE email - continuing without snapshot")
        except Exception as e:
            print(f"[WARN] Exception capturing frame for PPE email: {e}")
            frame = None
    
    success = send_ppe_violation_alert_email(frame)
    
    if success:
        return jsonify({"ok": True, "message": "PPE violation email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email alert throttled or failed"}), 429


# ---------------------------------------------------------------------------
# Smoking/Fire Detection API endpoints
# ---------------------------------------------------------------------------

def send_smoking_alert_email(detection_type: str = "smoke", frame: np.ndarray | None = None) -> bool:
    """
    Send an email alert when smoke or fire is detected.
    Uses throttling to prevent spam (max once per minute).
    
    Args:
        detection_type: "smoke", "fire", or "both"
        frame: Optional numpy array frame to include as snapshot
    
    Returns True if email was sent, False if throttled or failed.
    """
    global _last_smoking_email_time
    
    current_time = time.time()
    time_since_last_email = current_time - _last_smoking_email_time
    
    # Throttle: only send if enough time has passed
    if time_since_last_email < _SMOKING_EMAIL_COOLDOWN:
        print(f"[INFO] Smoking/fire email alert throttled. Last sent {time_since_last_email:.1f}s ago. Need {_SMOKING_EMAIL_COOLDOWN}s cooldown.")
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine alert type and colors
        if detection_type == "both":
            alert_title = "🔥 CRITICAL: Smoke AND Fire Detected!"
            alert_color = "#dc2626"
            status_text = "Smoke and Fire detected simultaneously"
        elif detection_type == "fire":
            alert_title = "🔥 CRITICAL: Smoke AND Fire Detected!"
            alert_color = "#dc2626"
            status_text = "Smoke and Fire detected simultaneously"
        else:
            alert_title = "🚨 WARNING: Smoke AND Fire Detected!"
            alert_color = "#f59e0b"
            status_text = "Smoke and Fire detected simultaneously"
        
        # Encode frame snapshot as base64 if provided
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                print(f"[WARN] Failed to encode frame snapshot: {e}")
        
        # Encode logo as base64 for inline embedding
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_data = fp.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        except Exception as e:
            print(f"[WARN] Failed to load logo: {e}")
        
        # Create HTML email body
        logo_img_tag = ""
        if logo_base64:
            logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />'
        else:
            logo_img_tag = '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">
        {logo_img_tag}
    </div>
    <h2 style="color: {alert_color};">{alert_title}</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: {alert_color}; font-weight: bold;">{detection_type.upper()} Detection</span></p>
        <p><strong>Status:</strong> {status_text}</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #fafafa; border: 2px dashed #ccc; border-radius: 5px;">
        <p><strong>Captured Snapshot:</strong></p>
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
        <p style="font-size: 12px; color: #666; margin-top: 10px;">Frame captured at {timestamp}</p>
    </div>"""
        
        html_body += f"""
    <div style="background-color: #fee2e2; border: 1px solid #dc2626; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>🚨 IMMEDIATE ACTION REQUIRED:</strong> {status_text}. Evacuate the area if necessary and contact emergency services.
    </div>
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px;">
        <p>This is an automated alert from the <strong>UNIface360 Safety System</strong>.</p>
    </div>
</body>
</html>"""
        
        # Plain text fallback
        text_body = f"""
UNIface360 Safety Alert

{alert_title}

{status_text}

Detection Details:
- Time: {timestamp}
- Alert Type: {detection_type.upper()} Detection
- Status: {status_text}

IMMEDIATE ACTION REQUIRED: Evacuate the area if necessary and contact emergency services.

This is an automated alert from the UNIface360 safety system.
"""
        
        msg = Message(
            subject=f"{alert_title} - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=text_body,
            html=html_body
        )
        
        print(f"[DEBUG] Attempting to send smoking/fire email to {', '.join(recipients)}")
        
        try:
            mail.send(msg)
            _last_smoking_email_time = current_time
            print(f"[INFO] Smoking/fire email alert sent successfully to {', '.join(recipients)}")
            return True
        except Exception as send_error:
            print(f"[ERROR] Failed to send smoking/fire email: {send_error}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare smoking/fire email alert: {e}")
        import traceback
        traceback.print_exc()
        return False


@app.post("/api/demo/smoking/check")
def api_demo_smoking_check() -> Response:
    """
    Smoke/Fire detection check using YOLO model.
    
    Uses camera_index from payload to capture frame directly from backend camera.
    Returns detection status for both smoke and fire.
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    print(f"[DEBUG] Smoking check called with payload: {payload}")
    
    # Check if camera_index is provided
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        print(f"[DEBUG] Getting frame from camera {camera_index}")
        # Capture frame directly from camera with retry
        frame = None
        max_retries = 3
        for attempt in range(max_retries):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                print(f"[DEBUG] Got frame from camera on attempt {attempt + 1}")
                break
            if attempt < max_retries - 1:
                time.sleep(0.5)
        
        if frame is None:
            print(f"[ERROR] Could not get frame from camera {camera_index}")
            return jsonify({"ok": False, "error": "camera_not_available", "message": "Could not capture frame from camera after retries"}), 400
    else:
        # Use provided image
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400
    
    print(f"[DEBUG] Frame obtained, shape: {frame.shape if frame is not None else 'None'}")
    
    # Ensure model is loaded
    if not _load_smoke_model():
        return jsonify({"ok": False, "error": "model_not_loaded", "message": "Smoke detection model could not be loaded"}), 500
    
    # Detect smoke/fire using YOLO
    result = detect_smoke_fire(frame, conf_threshold=0.15)
    
    return jsonify({
        "ok": True,
        "smoke_detected": result["smoke_detected"],
        "fire_detected": result["fire_detected"],
        "smoke_confidence": result["smoke_confidence"],
        "fire_confidence": result["fire_confidence"]
    })


@app.post("/api/demo/smoking/send-alert-email")
def api_send_smoking_email() -> Response:
    """
    Endpoint to send email alert for smoke/fire detection.
    Includes built-in throttling (60 seconds cooldown).
    """
    payload = request.get_json(silent=True, force=True) or {}
    detection_type = payload.get("detection_type", "smoke")
    
    # Capture frame snapshot if camera_index is provided
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        try:
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is None:
                print(f"[WARN] Could not capture frame from camera {camera_index} for smoking email - continuing without snapshot")
        except Exception as e:
            print(f"[WARN] Exception capturing frame for smoking email: {e}")
            frame = None
    
    success = send_smoking_alert_email(detection_type, frame)
    
    if success:
        return jsonify({"ok": True, "message": "Smoking/fire email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email alert throttled or failed"}), 429


# ---------------------------------------------------------------------------
# Page routes for the four dedicated demos
# ---------------------------------------------------------------------------


@app.route("/demo/smoking")
def demo_smoking() -> str:
    return render_template("demo_smoking.html")


@app.route("/demo/unauthorized")
def demo_unauthorized() -> str:
    return render_template("demo_unauthorized.html")


@app.route("/demo/restricted")
def demo_restricted() -> str:
    return render_template("demo_restricted.html")


@app.route("/demo/ppe")
def demo_ppe() -> str:
    return render_template("demo_ppe.html")


if __name__ == "__main__":
    # Use the built-in development server for simplicity.
    app.run(debug=True, host="0.0.0.0", port=5000)


