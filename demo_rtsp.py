"""
UNIface360 Realtime Safety Demo - RTSP Version
===============================================

Same functionality as demo.py but uses RTSP IP camera streams instead of local webcams.
Includes dynamic camera configuration page.

Features:
- Neon / futuristic landing page
- Dynamic RTSP camera configuration (add/edit/remove cameras)
- Multiple live RTSP camera feeds
- Realtime notifications via Server-Sent Events (SSE)
- Four detection types:
  * Smoking/Fire Detection (YOLO)
  * Unauthorized Person (Face Recognition)
  * Restricted Area (Person Detection)
  * PPE (Missing Hardhat) (YOLO)

How to run
----------
1. Create / activate your virtual environment (optional but recommended).
2. Install dependencies:
   pip install -r requirements.txt
3. Run this demo app:
   python demo_rtsp.py
4. Open the browser at:
   http://127.0.0.1:5001/
5. Click the ⚙️ icon to configure RTSP cameras
"""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime
from typing import Dict, Generator, List, Optional
from dataclasses import dataclass, asdict

import base64
import io
import os
import pickle
import sys

import numpy as np
import face_recognition
import cv2
from flask import Flask, Response, jsonify, render_template, render_template_string, request
from flask_mail import Mail, Message

from config import ENCODINGS_FILE
import socket
import concurrent.futures
import uuid
from datetime import timedelta
from collections import defaultdict

app = Flask(__name__)

# Import Person Detection from local package
from human_detection.realtime_person_detection import UltraFastDetector
import onnxruntime as ort # Ensure onnxruntime is available


# ---------------------------------------------------------------------------
# Analytics & Event Storage System
# ---------------------------------------------------------------------------

EVENTS_FILE = os.path.join(os.path.dirname(__file__), "analytics_events.json")
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "static", "snapshots")
KNOWN_FACES_DIR = os.path.join(os.path.dirname(__file__), "known_faces")
PERSONS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "persons_config.json")
ZONES_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "zones_config.json")

# Ensure directories exist
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)


@dataclass
class DetectionEvent:
    """Represents a detection event for analytics."""
    id: str
    event_type: str  # "unauthorized", "restricted", "ppe"
    camera_id: int
    camera_name: str
    timestamp: str
    snapshot_path: Optional[str]
    details: dict
    severity: str  # "low", "medium", "high", "critical"


class AnalyticsStore:
    """Stores and manages detection events for analytics."""
    
    def __init__(self):
        self._events: List[dict] = []
        self._lock = threading.Lock()
        self._load_events()
    
    def _load_events(self) -> None:
        """Load events from JSON file."""
        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                    self._events = json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load events: {e}")
                self._events = []
    
    def _save_events(self) -> None:
        """Save events to JSON file."""
        try:
            with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._events, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save events: {e}")
    
    def add_event(
        self,
        event_type: str,
        camera_id: int,
        camera_name: str,
        details: dict,
        severity: str = "medium",
        snapshot: Optional[np.ndarray] = None
    ) -> dict:
        """Add a new detection event."""
        event_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        # Save snapshot if provided
        snapshot_path = None
        if snapshot is not None:
            try:
                filename = f"{event_type}_{event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                filepath = os.path.join(SNAPSHOTS_DIR, filename)
                cv2.imwrite(filepath, snapshot, [cv2.IMWRITE_JPEG_QUALITY, 90])
                snapshot_path = f"/static/snapshots/{filename}"
            except Exception as e:
                print(f"[ERROR] Failed to save snapshot: {e}")
        
        event = {
            "id": event_id,
            "event_type": event_type,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "timestamp": timestamp,
            "snapshot_path": snapshot_path,
            "details": details,
            "severity": severity
        }
        
        with self._lock:
            self._events.append(event)
            # Keep only last 1000 events
            if len(self._events) > 1000:
                self._events = self._events[-1000:]
            self._save_events()
        
        return event
    
    def get_events(
        self,
        event_type: Optional[str] = None,
        camera_id: Optional[int] = None,
        limit: int = 100,
        hours: Optional[int] = None
    ) -> List[dict]:
        """Get filtered events."""
        with self._lock:
            events = self._events.copy()
        
        # Filter by time
        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            events = [e for e in events if datetime.fromisoformat(e["timestamp"]) > cutoff]
        
        # Filter by type
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        
        # Filter by camera
        if camera_id is not None:
            events = [e for e in events if e["camera_id"] == camera_id]
        
        # Sort by timestamp (newest first) and limit
        events = sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]
        
        return events
    
    def get_statistics(self, hours: int = 24) -> dict:
        """Get analytics statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            events = [e for e in self._events if datetime.fromisoformat(e["timestamp"]) > cutoff]
        
        # Count by type
        by_type = defaultdict(int)
        by_camera = defaultdict(int)
        by_severity = defaultdict(int)
        by_hour = defaultdict(int)
        
        for event in events:
            by_type[event["event_type"]] += 1
            by_camera[event.get("camera_name", f"Camera {event['camera_id']}")] += 1
            by_severity[event["severity"]] += 1
            
            # Group by hour
            ts = datetime.fromisoformat(event["timestamp"])
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            by_hour[hour_key] += 1
        
        return {
            "total": len(events),
            "by_type": dict(by_type),
            "by_camera": dict(by_camera),
            "by_severity": dict(by_severity),
            "by_hour": dict(sorted(by_hour.items())),
            "period_hours": hours
        }
    
    def clear_events(self, event_type: Optional[str] = None) -> int:
        """Clear events (optionally filtered by type)."""
        with self._lock:
            if event_type:
                original_count = len(self._events)
                self._events = [e for e in self._events if e["event_type"] != event_type]
                deleted = original_count - len(self._events)
            else:
                deleted = len(self._events)
                self._events = []
            self._save_events()
        return deleted


# Global analytics store
_analytics = AnalyticsStore()


# ---------------------------------------------------------------------------
# Person Management System
# ---------------------------------------------------------------------------

class PersonManager:
    """Manages persons for authorization and face recognition."""
    
    def __init__(self):
        self._persons: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load_persons()
    
    def _load_persons(self) -> None:
        """Load persons configuration from file."""
        if os.path.exists(PERSONS_CONFIG_FILE):
            try:
                with open(PERSONS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._persons = json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load persons: {e}")
                self._persons = {}
        else:
            # Scan existing known_faces directory
            self._scan_known_faces()
    
    def _scan_known_faces(self) -> None:
        """Scan known_faces directory and add existing persons."""
        if not os.path.exists(KNOWN_FACES_DIR):
            return
        
        for folder in os.listdir(KNOWN_FACES_DIR):
            folder_path = os.path.join(KNOWN_FACES_DIR, folder)
            if os.path.isdir(folder_path):
                photos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if folder not in self._persons:
                    self._persons[folder] = {
                        "id": folder,
                        "name": folder.replace("_", " "),
                        "authorized": True,  # Default to authorized
                        "photo_count": len(photos),
                        "trained": os.path.exists(os.path.join(os.path.dirname(__file__), "face_encodings.pkl")),
                        "created_at": datetime.now().isoformat()
                    }
        self._save_persons()
    
    def _save_persons(self) -> None:
        """Save persons configuration to file."""
        try:
            with open(PERSONS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._persons, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save persons: {e}")
    
    def get_all_persons(self) -> List[dict]:
        """Get all persons."""
        with self._lock:
            persons = []
            for pid, pdata in self._persons.items():
                person = pdata.copy()
                person["id"] = pid
                # Count actual photos
                folder_path = os.path.join(KNOWN_FACES_DIR, pid)
                if os.path.exists(folder_path):
                    photos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    person["photo_count"] = len(photos)
                    person["photos"] = [f"/static/known_faces/{pid}/{f}" for f in photos[:5]]  # First 5 for preview
                else:
                    person["photo_count"] = 0
                    person["photos"] = []
                persons.append(person)
            return persons
    
    def add_person(self, person_id: str, name: str, authorized: bool = True) -> dict:
        """Add a new person."""
        # Sanitize ID
        safe_id = "".join(c if c.isalnum() or c == "_" else "_" for c in person_id)
        
        # Create folder
        folder_path = os.path.join(KNOWN_FACES_DIR, safe_id)
        os.makedirs(folder_path, exist_ok=True)
        
        with self._lock:
            self._persons[safe_id] = {
                "id": safe_id,
                "name": name,
                "authorized": authorized,
                "photo_count": 0,
                "trained": False,
                "created_at": datetime.now().isoformat()
            }
            self._save_persons()
            return self._persons[safe_id]
    
    def update_person(self, person_id: str, name: str = None, authorized: bool = None) -> dict:
        """Update person details."""
        with self._lock:
            if person_id not in self._persons:
                return None
            if name is not None:
                self._persons[person_id]["name"] = name
            if authorized is not None:
                self._persons[person_id]["authorized"] = authorized
            self._save_persons()
            return self._persons[person_id]
    
    def delete_person(self, person_id: str) -> bool:
        """Delete a person and their photos."""
        with self._lock:
            if person_id not in self._persons:
                return False
            
            # Remove folder
            folder_path = os.path.join(KNOWN_FACES_DIR, person_id)
            if os.path.exists(folder_path):
                import shutil
                shutil.rmtree(folder_path)
            
            del self._persons[person_id]
            self._save_persons()
            return True
    
    def add_photo(self, person_id: str, photo_data: bytes, filename: str = None) -> str:
        """Add a photo to a person."""
        if person_id not in self._persons:
            return None
        
        folder_path = os.path.join(KNOWN_FACES_DIR, person_id)
        os.makedirs(folder_path, exist_ok=True)
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{person_id}_{timestamp}.jpg"
        
        filepath = os.path.join(folder_path, filename)
        
        with open(filepath, 'wb') as f:
            f.write(photo_data)
        
        # Update photo count
        with self._lock:
            photos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            self._persons[person_id]["photo_count"] = len(photos)
            self._persons[person_id]["trained"] = False  # Need retraining
            self._save_persons()
        
        return f"/static/known_faces/{person_id}/{filename}"
    
    def is_authorized(self, person_id: str) -> bool:
        """Check if a person is authorized."""
        with self._lock:
            if person_id in self._persons:
                return self._persons[person_id].get("authorized", False)
            return False
    
    def get_authorized_names(self) -> List[str]:
        """Get list of authorized person names."""
        with self._lock:
            return [p["name"] for p in self._persons.values() if p.get("authorized", False)]


# Global person manager
_person_manager = PersonManager()


# ---------------------------------------------------------------------------
# Model Camera Configuration System
# ---------------------------------------------------------------------------

MODEL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "model_cameras_config.json")


class ModelCameraManager:
    """Manages camera configurations for each detection model."""
    
    MODEL_TYPES = ["unauthorized", "restricted", "ppe", "evacuation", "live_tracking"]
    
    def __init__(self):
        self._config: Dict[str, dict] = {
            "unauthorized": {},    # camera_id -> {enabled: bool, name: str}
            "restricted": {},      # camera_id -> {enabled: bool, is_restricted: bool, name: str}
            "ppe": {},             # camera_id -> {enabled: bool, name: str}
            "evacuation": {},      # camera_id -> {enabled: bool} - Person detection/head count only
            "live_tracking": {}    # camera_id -> {enabled: bool} - Face recognition with person logs
        }
        self._lock = threading.Lock()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if os.path.exists(MODEL_CONFIG_FILE):
            try:
                with open(MODEL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for model_type in self.MODEL_TYPES:
                        if model_type in saved:
                            self._config[model_type] = saved[model_type]
            except Exception as e:
                print(f"[WARN] Failed to load model config: {e}")
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(MODEL_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save model config: {e}")
    
    def get_model_cameras(self, model_type: str) -> Dict[str, dict]:
        """Get all camera configurations for a model type."""
        with self._lock:
            return self._config.get(model_type, {}).copy()
    
    def get_all_config(self) -> dict:
        """Get all model configurations."""
        with self._lock:
            return {mt: self._config[mt].copy() for mt in self.MODEL_TYPES}
    
    def add_camera_to_model(self, model_type: str, camera_id: int, name: str = "", 
                            enabled: bool = True, is_restricted: bool = False,
                            is_smoking_zone: bool = False) -> dict:
        """Add a camera configuration to a model."""
        cam_key = str(camera_id)
        
        with self._lock:
            if model_type not in self._config:
                return None
            
            config = {
                "camera_id": camera_id,
                "name": name or f"Camera {camera_id}",
                "enabled": enabled,
                "added_at": datetime.now().isoformat()
            }
            
            # Model-specific flags
            if model_type == "restricted":
                config["is_restricted"] = is_restricted
            elif model_type == "evacuation":
                config["is_evacuation_zone"] = is_smoking_zone # Reuse parameter for compatibility or mapped
            
            self._config[model_type][cam_key] = config
            self._save_config()
            return config
    
    def update_camera_in_model(self, model_type: str, camera_id: int, 
                               name: str = None, enabled: bool = None, 
                               is_restricted: bool = None, is_smoking_zone: bool = None) -> dict:
        """Update a camera configuration in a model."""
        cam_key = str(camera_id)
        
        with self._lock:
            if model_type not in self._config:
                return None
            if cam_key not in self._config[model_type]:
                return None
            
            if name is not None:
                self._config[model_type][cam_key]["name"] = name
            if enabled is not None:
                self._config[model_type][cam_key]["enabled"] = enabled
            if is_restricted is not None and model_type == "restricted":
                self._config[model_type][cam_key]["is_restricted"] = is_restricted
            if is_smoking_zone is not None and model_type == "evacuation":
                self._config[model_type][cam_key]["is_evacuation_zone"] = is_smoking_zone
            
            self._save_config()
            return self._config[model_type][cam_key]
    
    def remove_camera_from_model(self, model_type: str, camera_id: int) -> bool:
        """Remove a camera from a model configuration."""
        cam_key = str(camera_id)
        
        with self._lock:
            if model_type not in self._config:
                return False
            if cam_key not in self._config[model_type]:
                return False
            
            del self._config[model_type][cam_key]
            self._save_config()
            return True
    
    def is_camera_enabled_for_model(self, model_type: str, camera_id: int) -> bool:
        """Check if a camera is enabled for a specific model."""
        cam_key = str(camera_id)
        with self._lock:
            if model_type in self._config and cam_key in self._config[model_type]:
                return self._config[model_type][cam_key].get("enabled", False)
            return False
    
    def is_camera_restricted(self, camera_id: int) -> bool:
        """Check if a camera is marked as restricted."""
        cam_key = str(camera_id)
        with self._lock:
            if cam_key in self._config["restricted"]:
                return self._config["restricted"][cam_key].get("is_restricted", False)
            return False
    
    def get_restricted_cameras(self) -> List[int]:
        """Get list of camera IDs that are marked as restricted."""
        with self._lock:
            return [int(cam_key) for cam_key, cfg in self._config["restricted"].items() 
                    if cfg.get("is_restricted", False) and cfg.get("enabled", False)]


# Global model camera manager
_model_camera_manager = ModelCameraManager()


# Legacy zone manager for backwards compatibility
class ZoneManager:
    """Manages zones/areas for restricted area detection (legacy)."""
    
    def __init__(self):
        self._zones: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load_zones()
    
    def _load_zones(self) -> None:
        if os.path.exists(ZONES_CONFIG_FILE):
            try:
                with open(ZONES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._zones = json.load(f)
            except:
                self._zones = {}
    
    def _save_zones(self) -> None:
        try:
            with open(ZONES_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._zones, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def get_all_zones(self) -> List[dict]:
        with self._lock:
            return [{"id": zid, **zdata} for zid, zdata in self._zones.items()]
    
    def add_zone(self, name: str, camera_id: int, is_restricted: bool = False, description: str = "") -> dict:
        zone_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._zones[zone_id] = {"id": zone_id, "name": name, "camera_id": camera_id, 
                                    "is_restricted": is_restricted, "description": description,
                                    "created_at": datetime.now().isoformat()}
            self._save_zones()
            return self._zones[zone_id]
    
    def update_zone(self, zone_id: str, **kwargs) -> dict:
        with self._lock:
            if zone_id not in self._zones:
                return None
            for k, v in kwargs.items():
                if v is not None:
                    self._zones[zone_id][k] = v
            self._save_zones()
            return self._zones[zone_id]
    
    def delete_zone(self, zone_id: str) -> bool:
        with self._lock:
            if zone_id in self._zones:
                del self._zones[zone_id]
                self._save_zones()
                return True
            return False
    
    def is_camera_restricted(self, camera_id: int) -> bool:
        with self._lock:
            return any(z.get("camera_id") == camera_id and z.get("is_restricted") 
                      for z in self._zones.values())


# Global zone manager (legacy)
_zone_manager = ZoneManager()


# ---------------------------------------------------------------------------
# RTSP Camera Configuration (Persistent)
# ---------------------------------------------------------------------------

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "rtsp_cameras.json")

# Default cameras (empty - user will add via config page)
DEFAULT_CAMERAS = {}

# Default scan settings
SCAN_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "rtsp_scan_settings.json")

DEFAULT_SCAN_SETTINGS = {
    "ip": "192.168.1.168",
    "username": "admin",
    "password": "UNIface360",
    "port": 554
}


def load_scan_settings() -> dict:
    """Load scan settings from JSON file."""
    if os.path.exists(SCAN_SETTINGS_FILE):
        try:
            with open(SCAN_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SCAN_SETTINGS.copy()


def save_scan_settings(settings: dict) -> bool:
    """Save scan settings to JSON file."""
    try:
        with open(SCAN_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception:
        return False


# Global scan settings
SCAN_SETTINGS = load_scan_settings()


def load_camera_config() -> Dict[int, dict]:
    """Load camera configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"[WARN] Failed to load camera config: {e}")
    return DEFAULT_CAMERAS.copy()


def save_camera_config(cameras: Dict[int, dict]) -> bool:
    """Save camera configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cameras, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save camera config: {e}")
        return False


# Global camera configuration
RTSP_CAMERAS = load_camera_config()

# Streaming settings
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS = 25
JPEG_QUALITY = 85
RECONNECT_DELAY = 3  # seconds
BUFFER_SIZE = 2  # frames to buffer

# ---------------------------------------------------------------------------
# RTSP Stream Handler (Threaded)
# ---------------------------------------------------------------------------

@dataclass
class StreamStats:
    fps: float = 0.0
    frame_count: int = 0
    last_frame_time: float = 0.0
    connected: bool = False
    error: Optional[str] = None


class RTSPStream:
    """Threaded RTSP stream handler for smooth video capture."""
    
    def __init__(self, camera_index: int, url: str, name: str):
        self.camera_index = camera_index
        self.url = url
        self.name = name
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self.stats = StreamStats()
        self._fps_frames = 0
        self._fps_start_time = time.time()
        
    def _configure_capture(self, cap: cv2.VideoCapture) -> None:
        """Configure capture for optimal RTSP streaming."""
        cap.set(cv2.CAP_PROP_BUFFERSIZE, BUFFER_SIZE)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        
    def _connect(self) -> bool:
        """Establish connection to RTSP stream."""
        try:
            if self._cap is not None:
                try:
                    self._cap.release()
                except:
                    pass
            
            print(f"[RTSP-{self.camera_index}] Connecting to {self.url}...")
            
            # Set RTSP transport to TCP for reliability
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;1024000"
            
            self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.url)
            
            if self._cap.isOpened():
                self._configure_capture(self._cap)
                self.stats.connected = True
                self.stats.error = None
                print(f"[RTSP-{self.camera_index}] Connected successfully!")
                return True
            else:
                self.stats.connected = False
                self.stats.error = "Failed to open stream"
                print(f"[RTSP-{self.camera_index}] Failed to connect")
                return False
                
        except Exception as e:
            self.stats.connected = False
            self.stats.error = str(e)
            print(f"[RTSP-{self.camera_index}] Connection error: {e}")
            return False
    
    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that can be interrupted when _running becomes False."""
        end_time = time.time() + seconds
        while time.time() < end_time and self._running:
            time.sleep(0.1)  # Check every 100ms
    
    def _grab_frames(self) -> None:
        """Background thread for grabbing frames continuously."""
        consecutive_failures = 0
        max_failures = 10
        
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                if not self._connect():
                    self._interruptible_sleep(RECONNECT_DELAY)
                    continue
            
            try:
                ret = self._cap.grab()
                
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        print(f"[RTSP-{self.camera_index}] Too many failures, reconnecting...")
                        self.stats.connected = False
                        self.stats.error = "Stream disconnected"
                        if self._cap:
                            self._cap.release()
                        self._cap = None
                        consecutive_failures = 0
                        self._interruptible_sleep(RECONNECT_DELAY)
                    continue
                
                ret, frame = self._cap.retrieve()
                
                if ret and frame is not None:
                    consecutive_failures = 0
                    
                    with self._frame_lock:
                        self._frame = frame
                    
                    self.stats.frame_count += 1
                    self.stats.last_frame_time = time.time()
                    self.stats.connected = True
                    self.stats.error = None
                    
                    self._fps_frames += 1
                    elapsed = time.time() - self._fps_start_time
                    if elapsed >= 1.0:
                        self.stats.fps = self._fps_frames / elapsed
                        self._fps_frames = 0
                        self._fps_start_time = time.time()
                else:
                    consecutive_failures += 1
                    
            except Exception as e:
                print(f"[RTSP-{self.camera_index}] Frame grab error: {e}")
                consecutive_failures += 1
                
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def start(self) -> None:
        """Start the stream capture thread."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._grab_frames, daemon=True)
        self._thread.start()
        print(f"[RTSP-{self.camera_index}] Stream thread started")
    
    def stop(self) -> None:
        """Stop the stream capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        print(f"[RTSP-{self.camera_index}] Stream stopped")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame (thread-safe)."""
        with self._frame_lock:
            if self._frame is not None:
                return self._frame.copy()
        return None
    
    def is_connected(self) -> bool:
        """Check if stream is connected."""
        return self.stats.connected


# ---------------------------------------------------------------------------
# RTSP Stream Manager
# ---------------------------------------------------------------------------

class RTSPStreamManager:
    """Manages multiple RTSP streams with dynamic configuration."""
    
    def __init__(self):
        self.streams: Dict[int, RTSPStream] = {}
        self._initialized = False
        self._lock = threading.Lock()
        
    def initialize(self) -> None:
        """Initialize all configured RTSP streams."""
        with self._lock:
            if self._initialized:
                return
            
            for cam_idx, cam_info in RTSP_CAMERAS.items():
                if cam_info.get('enabled', True):
                    stream = RTSPStream(cam_idx, cam_info['url'], cam_info['name'])
                    self.streams[cam_idx] = stream
                    stream.start()
                
            self._initialized = True
            print(f"[INFO] Initialized {len(self.streams)} RTSP streams")
    
    def add_camera(self, camera_index: int, url: str, name: str, enabled: bool = True) -> bool:
        """Add or update a camera."""
        global RTSP_CAMERAS
        
        with self._lock:
            # Stop existing stream if any
            if camera_index in self.streams:
                self.streams[camera_index].stop()
                del self.streams[camera_index]
            
            # Update config
            RTSP_CAMERAS[camera_index] = {
                "name": name,
                "url": url,
                "enabled": enabled
            }
            save_camera_config(RTSP_CAMERAS)
            
            # Start new stream if enabled
            if enabled:
                stream = RTSPStream(camera_index, url, name)
                self.streams[camera_index] = stream
                stream.start()
            
            return True
    
    def remove_camera(self, camera_index: int) -> bool:
        """Remove a camera."""
        global RTSP_CAMERAS
        
        print(f"[DELETE] Attempting to remove camera {camera_index}")
        print(f"[DELETE] Current cameras: {list(RTSP_CAMERAS.keys())}")
        
        with self._lock:
            # Check if camera exists
            if camera_index not in RTSP_CAMERAS:
                print(f"[DELETE] Camera {camera_index} NOT found in RTSP_CAMERAS")
                return False
            
            # Stop stream if exists
            if camera_index in self.streams:
                print(f"[DELETE] Stopping stream for camera {camera_index}")
                self.streams[camera_index].stop()
                del self.streams[camera_index]
            
            # Remove from config
            del RTSP_CAMERAS[camera_index]
            result = save_camera_config(RTSP_CAMERAS)
            print(f"[DELETE] Save result: {result}, Remaining cameras: {list(RTSP_CAMERAS.keys())}")
            
            return True
    
    def toggle_camera(self, camera_index: int, enabled: bool) -> bool:
        """Enable or disable a camera."""
        global RTSP_CAMERAS
        
        with self._lock:
            if camera_index not in RTSP_CAMERAS:
                return False
            
            RTSP_CAMERAS[camera_index]['enabled'] = enabled
            save_camera_config(RTSP_CAMERAS)
            
            if enabled and camera_index not in self.streams:
                cam_info = RTSP_CAMERAS[camera_index]
                stream = RTSPStream(camera_index, cam_info['url'], cam_info['name'])
                self.streams[camera_index] = stream
                stream.start()
            elif not enabled and camera_index in self.streams:
                self.streams[camera_index].stop()
                del self.streams[camera_index]
            
            return True
    
    def restart_camera(self, camera_index: int) -> bool:
        """Restart a camera stream."""
        with self._lock:
            if camera_index not in RTSP_CAMERAS:
                return False
            
            cam_info = RTSP_CAMERAS[camera_index]
            
            if camera_index in self.streams:
                self.streams[camera_index].stop()
                del self.streams[camera_index]
            
            if cam_info.get('enabled', True):
                stream = RTSPStream(camera_index, cam_info['url'], cam_info['name'])
                self.streams[camera_index] = stream
                stream.start()
            
            return True
    
    def get_frame(self, camera_index: int) -> Optional[np.ndarray]:
        """Get frame from a specific camera."""
        self.initialize()
        
        stream = self.streams.get(camera_index)
        if stream:
            return stream.get_frame()
        
        # Fallback to first available camera
        if camera_index != 0 and self.streams:
            first_key = next(iter(self.streams))
            print(f"[WARN] Camera {camera_index} not found, falling back to camera {first_key}")
            return self.streams[first_key].get_frame()
            
        return None
    
    def get_stream(self, camera_index: int) -> Optional[RTSPStream]:
        """Get stream object for a camera."""
        self.initialize()
        return self.streams.get(camera_index)
    
    def stop_all(self) -> None:
        """Stop all streams."""
        with self._lock:
            for stream in self.streams.values():
                stream.stop()
            self.streams.clear()
            self._initialized = False
    
    def get_all_stats(self) -> Dict[int, dict]:
        """Get stats for all streams."""
        result = {}
        for cam_idx, cam_info in RTSP_CAMERAS.items():
            stream = self.streams.get(cam_idx)
            if stream:
                result[cam_idx] = {
                    "name": stream.name,
                    "url": cam_info['url'],
                    "enabled": cam_info.get('enabled', True),
                    "connected": stream.stats.connected,
                    "fps": round(stream.stats.fps, 1),
                    "frame_count": stream.stats.frame_count,
                    "error": stream.stats.error
                }
            else:
                result[cam_idx] = {
                    "name": cam_info['name'],
                    "url": cam_info['url'],
                    "enabled": cam_info.get('enabled', True),
                    "connected": False,
                    "fps": 0,
                    "frame_count": 0,
                    "error": "Stream not started" if cam_info.get('enabled', True) else "Disabled"
                }
        return result


# Global stream manager
_stream_manager = RTSPStreamManager()


def _get_camera_frame(camera_index: int, fallback_to_zero: bool = True) -> Optional[np.ndarray]:
    """Get the latest frame from an RTSP camera."""
    frame = _stream_manager.get_frame(camera_index)
    
    if frame is None and fallback_to_zero and camera_index != 0:
        frame = _stream_manager.get_frame(0)
    
    return frame


def _generate_camera_stream(camera_index: int) -> Generator[bytes, None, None]:
    """Generate MJPEG stream from RTSP camera."""
    _stream_manager.initialize()
    
    while True:
        frame = _get_camera_frame(camera_index, fallback_to_zero=False)
        
        if frame is None:
            # Send a placeholder frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"RTSP Camera {camera_index}", (30, 200),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, "Connecting...", (30, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 1)
            cv2.putText(frame, "Please wait or check configuration", (30, 280),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        time.sleep(1.0 / TARGET_FPS)


# ---------------------------------------------------------------------------
# YOLO-based PPE (Hardhat) Detection
# ---------------------------------------------------------------------------

_ppe_net = None
_ppe_output_layers = None
_ppe_model_loaded = False
_ppe_model_lock = threading.Lock()
_ppe_inference_lock = threading.Lock()

PPE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "simple ppe", "yolov3_ppe2.cfg")
PPE_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "simple ppe", "yolov3_ppe2_last.weights")


def _load_ppe_model() -> bool:
    """Load YOLO model for hardhat detection."""
    global _ppe_net, _ppe_output_layers, _ppe_model_loaded
    
    with _ppe_model_lock:
        if _ppe_model_loaded:
            return _ppe_net is not None
        
        if not os.path.exists(PPE_CONFIG_PATH) or not os.path.exists(PPE_WEIGHTS_PATH):
            print(f"[WARN] PPE model files not found!")
            _ppe_model_loaded = True
            return False
        
        try:
            print(f"[INFO] Loading PPE YOLO model...")
            _ppe_net = cv2.dnn.readNetFromDarknet(PPE_CONFIG_PATH, PPE_WEIGHTS_PATH)
            layer_names = _ppe_net.getLayerNames()
            
            unconnected = _ppe_net.getUnconnectedOutLayers()
            if len(unconnected.shape) == 1:
                _ppe_output_layers = [layer_names[i - 1] for i in unconnected]
            else:
                _ppe_output_layers = [layer_names[i[0] - 1] for i in unconnected]
            
            _ppe_model_loaded = True
            print(f"[INFO] PPE YOLO model loaded successfully!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load PPE model: {e}")
            _ppe_model_loaded = True
            return False


def detect_hardhat(frame: np.ndarray, confidence_threshold: float = 0.5) -> tuple:
    """Detect hardhat in frame using YOLO model."""
    global _ppe_net, _ppe_output_layers
    
    if _ppe_net is None or _ppe_output_layers is None:
        if not _load_ppe_model():
            return False, 0.0
    
    if _ppe_net is None:
        return False, 0.0
    
    try:
        frame_copy = np.ascontiguousarray(frame)
        blob = cv2.dnn.blobFromImage(frame_copy, 1/255.0, (416, 416), (0, 0, 0), swapRB=True, crop=False)
        
        with _ppe_inference_lock:
            _ppe_net.setInput(blob)
            outputs = _ppe_net.forward(_ppe_output_layers)
        
        for out in outputs:
            for detection in out:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                
                if class_id == 0 and confidence > confidence_threshold:
                    return True, float(confidence)
        
        return False, 0.0
    except Exception as e:
        print(f"[ERROR] Hardhat detection failed: {e}")
        return False, 0.0



# ---------------------------------------------------------------------------
# Evacuation System (Person Detection Only - Head Count)
# ---------------------------------------------------------------------------

_tracking_model = None
_tracking_model_loaded = False
_tracking_model_lock = threading.Lock()
_tracking_inference_lock = threading.Lock()

# Path to ONNX model - relative to this file
TRACKING_MODEL_PATH = os.path.join(os.path.dirname(__file__), "human_detection", "weights", "model_256.onnx")

def _load_tracking_model() -> bool:
    """Load UltraFastDetector model for person detection."""
    global _tracking_model, _tracking_model_loaded
    
    with _tracking_model_lock:
        if _tracking_model_loaded:
            return _tracking_model is not None
        
        try:
            print(f"[INFO] Loading Person Detection model...")
            if not os.path.exists(TRACKING_MODEL_PATH):
                print(f"[ERROR] ONNX model not found at {TRACKING_MODEL_PATH}")
                _tracking_model_loaded = True
                return False

            _tracking_model = UltraFastDetector(TRACKING_MODEL_PATH, input_size=256, conf=0.5)
            _tracking_model_loaded = True
            print(f"[INFO] Person Detection model loaded successfully!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load person detection model: {e}")
            import traceback
            traceback.print_exc()
            _tracking_model_loaded = True
            return False


def detect_persons_only(frame: np.ndarray) -> dict:
    """
    Evacuation System: Detect persons only (no face recognition).
    Fast and reliable for head count per camera.
    """
    global _tracking_model
    
    result = {
        "person_count": 0,
        "persons_boxes": []
    }
    
    if frame is None:
        return result
    
    if _tracking_model is None:
        if not _load_tracking_model():
            return result
            
    try:
        # Detect persons using UltraFastDetector
        # Returns [(x1,y1,x2,y2,conf), ...]
        with _tracking_inference_lock:
            detections = _tracking_model.detect(frame)
        
        result["person_count"] = len(detections)
        result["persons_boxes"] = detections
                        
    except Exception as e:
        print(f"[ERROR] Person detection failed: {e}")
        import traceback
        traceback.print_exc()
        
    return result


# ---------------------------------------------------------------------------
# Live Tracking System (Face Recognition + Person Logs)
# ---------------------------------------------------------------------------

# Person tracking logs storage
PERSON_LOGS_FILE = os.path.join(os.path.dirname(__file__), "person_tracking_logs.json")
_person_tracking_logs: List[dict] = []
_person_logs_lock = threading.Lock()

def _load_person_logs() -> None:
    """Load person tracking logs from file."""
    global _person_tracking_logs
    if os.path.exists(PERSON_LOGS_FILE):
        try:
            with open(PERSON_LOGS_FILE, 'r', encoding='utf-8') as f:
                _person_tracking_logs = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load person logs: {e}")
            _person_tracking_logs = []


def _save_person_logs() -> None:
    """Save person tracking logs to file."""
    try:
        with open(PERSON_LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_person_tracking_logs[-500:], f, indent=2, ensure_ascii=False)  # Keep last 500
    except Exception as e:
        print(f"[ERROR] Failed to save person logs: {e}")


def add_person_log(person_name: str, camera_id: int, camera_name: str, 
                   confidence: float = 0.0, snapshot_path: str = None) -> dict:
    """Add a person tracking log entry."""
    global _person_tracking_logs
    
    log_entry = {
        "id": str(uuid.uuid4())[:8],
        "person_name": person_name,
        "camera_id": camera_id,
        "camera_name": camera_name,
        "timestamp": datetime.now().isoformat(),
        "confidence": round(confidence, 2),
        "snapshot_path": snapshot_path,
        "status": "detected"
    }
    
    with _person_logs_lock:
        _person_tracking_logs.append(log_entry)
        if len(_person_tracking_logs) % 10 == 0:  # Save every 10 entries
            _save_person_logs()
    
    return log_entry


def get_person_logs(person_name: str = None, camera_id: int = None, 
                   limit: int = 100, hours: int = None) -> List[dict]:
    """Get filtered person tracking logs."""
    with _person_logs_lock:
        logs = _person_tracking_logs.copy()
    
    # Filter by time
    if hours:
        cutoff = datetime.now() - timedelta(hours=hours)
        logs = [l for l in logs if datetime.fromisoformat(l["timestamp"]) > cutoff]
    
    # Filter by person
    if person_name:
        logs = [l for l in logs if l["person_name"].lower() == person_name.lower()]
    
    # Filter by camera
    if camera_id is not None:
        logs = [l for l in logs if l["camera_id"] == camera_id]
    
    # Sort by timestamp (newest first) and limit
    logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    return logs


def get_person_summary() -> dict:
    """Get summary of all tracked persons."""
    with _person_logs_lock:
        logs = _person_tracking_logs.copy()
    
    # Group by person
    person_stats = defaultdict(lambda: {
        "total_sightings": 0,
        "cameras_seen": set(),
        "first_seen": None,
        "last_seen": None
    })
    
    for log in logs:
        name = log["person_name"]
        ts = log["timestamp"]
        person_stats[name]["total_sightings"] += 1
        person_stats[name]["cameras_seen"].add(log["camera_id"])
        
        if person_stats[name]["first_seen"] is None or ts < person_stats[name]["first_seen"]:
            person_stats[name]["first_seen"] = ts
        if person_stats[name]["last_seen"] is None or ts > person_stats[name]["last_seen"]:
            person_stats[name]["last_seen"] = ts
    
    # Convert sets to lists for JSON serialization
    result = {}
    for name, stats in person_stats.items():
        result[name] = {
            "total_sightings": stats["total_sightings"],
            "cameras_seen": list(stats["cameras_seen"]),
            "first_seen": stats["first_seen"],
            "last_seen": stats["last_seen"]
        }
    
    return result


def detect_and_identify(frame: np.ndarray) -> dict:
    """
    Live Tracking System: Detect persons AND identify them using face recognition.
    Returns person count plus identified person names with confidence.
    """
    global _tracking_model
    
    result = {
        "person_count": 0,
        "identified_persons": [],
        "unknown_count": 0,
        "persons_boxes": [],
        "face_details": []
    }
    
    if frame is None:
        return result
    
    # First, detect persons
    if _tracking_model is None:
        if not _load_tracking_model():
            return result
            
    try:
        # Detect persons using UltraFastDetector
        with _tracking_inference_lock:
            detections = _tracking_model.detect(frame)
        
        result["person_count"] = len(detections)
        result["persons_boxes"] = detections
        
        # Only do face recognition if persons are detected
        if len(detections) > 0:
            try:
                # Lazy load known faces (this function is defined later in the file)
                _load_known_faces()
                
                # Find faces in the frame
                rgb_frame = frame[:, :, ::-1]  # BGR to RGB
                
                # Use HOG model for faster face detection on CPU
                face_locations = face_recognition.face_locations(rgb_frame, model='hog')
                
                if face_locations:
                    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    tolerance = 0.45
                    
                    for i, (enc, face_loc) in enumerate(zip(encodings, face_locations)):
                        top, right, bottom, left = face_loc
                        name = "Unknown"
                        confidence = 0.0
                        
                        if _known_face_encodings and len(_known_face_encodings) > 0:
                            distances = face_recognition.face_distance(_known_face_encodings, enc)
                            best_idx = int(np.argmin(distances))
                            best_distance = distances[best_idx]
                            
                            # Convert distance to confidence (lower distance = higher confidence)
                            confidence = max(0, 1 - best_distance)
                            
                            if best_distance <= tolerance:
                                folder_name = _known_face_names[best_idx]
                                name = NAME_MAPPING.get(folder_name, folder_name)
                        
                        face_detail = {
                            "name": name,
                            "confidence": round(confidence, 2),
                            "bbox": [left, top, right, bottom]
                        }
                        result["face_details"].append(face_detail)
                        
                        if name != "Unknown":
                            if name not in result["identified_persons"]:
                                result["identified_persons"].append(name)
                        else:
                            result["unknown_count"] += 1
                            
            except Exception as e:
                print(f"[WARN] Face recognition failed (non-critical): {e}")
                # Face recognition failure is non-critical - we still have person count
                        
    except Exception as e:
        print(f"[ERROR] Live tracking detection failed: {e}")
        import traceback
        traceback.print_exc()
        
    return result


# Legacy function for backwards compatibility
def detect_and_track(frame: np.ndarray) -> dict:
    """Legacy wrapper - redirects to detect_and_identify."""
    result = detect_and_identify(frame)
    return {
        "person_count": result["person_count"],
        "identified_persons": result["identified_persons"],
        "persons_boxes": result["persons_boxes"]
    }


# Initialize person logs on module load
_load_person_logs()

# ---------------------------------------------------------------------------
# Old Smoking Logic (Removed)
# ---------------------------------------------------------------------------
'''
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
            return _smoke_model is not None
        
        if not os.path.exists(SMOKE_MODEL_PATH):
            print(f"[WARN] Smoke model file not found: {SMOKE_MODEL_PATH}")
            _smoke_model_loaded = True
            return False
        
        try:
            print(f"[INFO] Loading Smoke/Fire YOLO model...")
            from ultralytics import YOLO
            _smoke_model = YOLO(SMOKE_MODEL_PATH)
            _smoke_model.to("cpu")
            _smoke_model_loaded = True
            print(f"[INFO] Smoke/Fire YOLO model loaded successfully!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load smoke model: {e}")
            _smoke_model_loaded = True
            return False


def detect_smoke_fire(frame: np.ndarray, conf_threshold: float = SMOKE_CONF_THRESHOLD) -> dict:
    """Detect smoke and fire in frame using YOLO model."""
    global _smoke_model
    
    result = {
        "smoke_detected": False,
        "fire_detected": False,
        "smoke_confidence": 0.0,
        "fire_confidence": 0.0
    }
    
    if _smoke_model is None:
        if not _load_smoke_model():
            return result
    
    if _smoke_model is None:
        return result
    
    try:
        frame_copy = np.ascontiguousarray(frame)
        frame_resized = cv2.resize(frame_copy, (512, 512))
        
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
                    
                    if "smoke" in cls_name:
                        if conf > result["smoke_confidence"]:
                            result["smoke_detected"] = True
                            result["smoke_confidence"] = conf
                    
                    if "fire" in cls_name:
                        if conf > result["fire_confidence"]:
                            result["fire_detected"] = True
                            result["fire_confidence"] = conf
        
        return result
    except Exception as e:
        print(f"[ERROR] Smoke/fire detection failed: {e}")
        return result
'''

# ---------------------------------------------------------------------------
# Configure Flask-Mail for email alerts
# ---------------------------------------------------------------------------

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'petrochoiceserver@gmail.com'
app.config['MAIL_PASSWORD'] = 'lbip fpbl irss wvbo'

mail = Mail(app)


# ---------------------------------------------------------------------------
# In-memory SSE event bus
# ---------------------------------------------------------------------------

_listeners_lock = threading.Lock()
_listeners: List["queue.Queue[Dict]"] = []


def add_listener() -> "queue.Queue[Dict]":
    """Register a new listener queue for SSE connections."""
    q: "queue.Queue[Dict]" = queue.Queue()
    with _listeners_lock:
        _listeners.append(q)
    return q


def remove_listener(q: "queue.Queue[Dict]") -> None:
    """Unregister a listener queue."""
    with _listeners_lock:
        if q in _listeners:
            _listeners.remove(q)


def broadcast_event(event: Dict) -> None:
    """Push an event to all active listeners."""
    with _listeners_lock:
        listeners_snapshot = list(_listeners)

    for q in listeners_snapshot:
        try:
            q.put_nowait(event)
        except queue.Full:
            continue


def event_stream() -> Generator[str, None, None]:
    """Generator for SSE endpoint."""
    q = add_listener()
    try:
        while True:
            event = q.get()
            data = json.dumps(event, separators=(",", ":"))
            yield f"data: {data}\n\n"
    except GeneratorExit:
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


def build_evacuation_event() -> Dict:
    return _base_event(
        event_type="evacuation",
        demo="Evacuation System",
        message="Person detected for evacuation tracking.",
        level="info",
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
# Email alert functionality with throttling
# ---------------------------------------------------------------------------

_last_email_time: float = 0.0
_EMAIL_COOLDOWN = 60.0

_last_restricted_email_time: float = 0.0
_RESTRICTED_EMAIL_COOLDOWN = 60.0

_last_ppe_email_time: float = 0.0
_PPE_EMAIL_COOLDOWN = 60.0

_last_smoking_email_time: float = 0.0
_SMOKING_EMAIL_COOLDOWN = 60.0


def send_unauthorized_alert_email(person_info: str = "Unknown person", frame: np.ndarray | None = None) -> bool:
    """Send an email alert when an unauthorized person is detected."""
    global _last_email_time
    
    current_time = time.time()
    if current_time - _last_email_time < _EMAIL_COOLDOWN:
        print(f"[INFO] Email alert throttled.")
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "dalia.ali@petrochoice.org"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception as e:
                print(f"[WARN] Failed to encode frame snapshot: {e}")
        
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_base64 = base64.b64encode(fp.read()).decode('utf-8')
        except Exception:
            pass
        
        logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />' if logo_base64 else '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">{logo_img_tag}</div>
    <h2 style="color: #d32f2f;">🚨 Security Alert: Unauthorized Person Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Person Status:</strong> <span style="color: #d32f2f; font-weight: bold;">Unauthorized / Unknown</span></p>
        <p><strong>Person Info:</strong> {person_info}</p>
        <p><strong>Source:</strong> RTSP Camera Stream</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #fafafa; border: 2px dashed #ccc; border-radius: 5px;">
        <p><strong>Captured Snapshot:</strong></p>
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
    </div>"""
        
        html_body += """
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>⚠️ Action Required:</strong> Please verify this detection and respond according to security procedures.
    </div>
</body>
</html>"""
        
        msg = Message(
            subject=f"🚨 UNIface360 Alert: Unauthorized Person Detected - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=f"Unauthorized person detected at {timestamp}. Person: {person_info}",
            html=html_body
        )
        
        mail.send(msg)
        _last_email_time = current_time
        print(f"[INFO] Email alert sent successfully")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


def send_restricted_area_alert_email(frame: np.ndarray | None = None) -> bool:
    """Send an email alert when a person is detected in a restricted area."""
    global _last_restricted_email_time
    
    current_time = time.time()
    if current_time - _last_restricted_email_time < _RESTRICTED_EMAIL_COOLDOWN:
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception:
                pass
        
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_base64 = base64.b64encode(fp.read()).decode('utf-8')
        except Exception:
            pass
        
        logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />' if logo_base64 else '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">{logo_img_tag}</div>
    <h2 style="color: #d32f2f;">🚨 Security Alert: Restricted Area Breach Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: #d32f2f; font-weight: bold;">Restricted Area Breach</span></p>
        <p><strong>Source:</strong> RTSP Camera Stream</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0;">
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
    </div>"""
        
        html_body += """
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px;">
        <strong>⚠️ Action Required:</strong> Initiate response plan immediately.
    </div>
</body>
</html>"""
        
        msg = Message(
            subject=f"🚨 UNIface360 Alert: Restricted Area Breach - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=f"Restricted area breach detected at {timestamp}.",
            html=html_body
        )
        
        mail.send(msg)
        _last_restricted_email_time = current_time
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


def send_ppe_violation_alert_email(frame: np.ndarray | None = None) -> bool:
    """Send an email alert when a PPE violation is detected."""
    global _last_ppe_email_time
    
    current_time = time.time()
    if current_time - _last_ppe_email_time < _PPE_EMAIL_COOLDOWN:
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception:
                pass
        
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_base64 = base64.b64encode(fp.read()).decode('utf-8')
        except Exception:
            pass
        
        logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />' if logo_base64 else '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">{logo_img_tag}</div>
    <h2 style="color: #ff9800;">⚠️ Safety Alert: PPE Violation Detected</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: #ff9800; font-weight: bold;">PPE Violation - Missing Hardhat</span></p>
        <p><strong>Source:</strong> RTSP Camera Stream</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0;">
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
    </div>"""
        
        html_body += """
    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px;">
        <strong>⚠️ Action Required:</strong> Ensure all personnel wear required safety equipment.
    </div>
</body>
</html>"""
        
        msg = Message(
            subject=f"⚠️ UNIface360 Alert: PPE Violation - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=f"PPE violation (missing hardhat) detected at {timestamp}.",
            html=html_body
        )
        
        mail.send(msg)
        _last_ppe_email_time = current_time
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


def send_smoking_alert_email(detection_type: str = "smoke", frame: np.ndarray | None = None) -> bool:
    """Send an email alert when smoke or fire is detected."""
    global _last_smoking_email_time
    
    current_time = time.time()
    if current_time - _last_smoking_email_time < _SMOKING_EMAIL_COOLDOWN:
        return False
    
    try:
        recipients = ["mostafa.magdy@petrochoice.org", "mahmoud.hussein@petrochoice.org", "hr.petrochoice@gmail.com"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if detection_type == "both":
            alert_title = "🔥 CRITICAL: Smoke AND Fire Detected!"
            alert_color = "#dc2626"
        elif detection_type == "fire":
            alert_title = "🔥 CRITICAL: Fire Detected!"
            alert_color = "#dc2626"
        else:
            alert_title = "🚨 WARNING: Smoke Detected!"
            alert_color = "#f59e0b"
        
        snapshot_base64 = None
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    snapshot_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            except Exception:
                pass
        
        logo_base64 = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "static", "Unifaces360.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as fp:
                    logo_base64 = base64.b64encode(fp.read()).decode('utf-8')
        except Exception:
            pass
        
        logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" alt="UNIface360" style="max-width: 200px;" />' if logo_base64 else '<div style="font-size: 24px; font-weight: bold; color: #1976d2;">UNIface360</div>'
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">{logo_img_tag}</div>
    <h2 style="color: {alert_color};">{alert_title}</h2>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p><strong>Detection Time:</strong> {timestamp}</p>
        <p><strong>Alert Type:</strong> <span style="color: {alert_color}; font-weight: bold;">{detection_type.upper()} Detection</span></p>
        <p><strong>Source:</strong> RTSP Camera Stream</p>
    </div>"""
        
        if snapshot_base64:
            html_body += f"""
    <div style="text-align: center; margin: 20px 0;">
        <img src="data:image/jpeg;base64,{snapshot_base64}" alt="Snapshot" style="max-width: 100%; border-radius: 5px;" />
    </div>"""
        
        html_body += """
    <div style="background-color: #fee2e2; border: 1px solid #dc2626; padding: 15px; border-radius: 5px;">
        <strong>🚨 IMMEDIATE ACTION REQUIRED:</strong> Evacuate the area if necessary and contact emergency services.
    </div>
</body>
</html>"""
        
        msg = Message(
            subject=f"{alert_title} - {timestamp}",
            sender=app.config['MAIL_USERNAME'],
            recipients=recipients,
            body=f"{detection_type.upper()} detected at {timestamp}. Take immediate action.",
            html=html_body
        )
        
        mail.send(msg)
        _last_smoking_email_time = current_time
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


# ---------------------------------------------------------------------------
# Face Recognition for Unauthorized Person Detection
# ---------------------------------------------------------------------------

_known_face_encodings: List[np.ndarray] = []
_known_face_names: List[str] = []
_faces_loaded = False

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
    """Load known faces from the encodings file."""
    global _faces_loaded, _known_face_encodings, _known_face_names
    if _faces_loaded:
        return

    path = os.path.join(os.path.dirname(__file__), ENCODINGS_FILE)
    if not os.path.exists(path):
        _faces_loaded = True
        return

    try:
        if "numpy._core" not in sys.modules:
            sys.modules["numpy._core"] = np
        try:
            core = np.core
            if "numpy._core.multiarray" not in sys.modules:
                sys.modules["numpy._core.multiarray"] = core.multiarray
        except Exception:
            pass

        with open(path, "rb") as f:
            data = pickle.load(f)
    except Exception:
        _faces_loaded = True
        return

    encodings: List[np.ndarray] = []
    names: List[str] = []

    if isinstance(data, dict) and "encodings" in data and "names" in data:
        encodings = [np.array(e) for e in data.get("encodings", [])]
        names = [str(n) for n in data.get("names", [])]
    elif isinstance(data, dict):
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
    print(f"[INFO] Loaded {len(_known_face_encodings)} known face encodings")


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


# ---------------------------------------------------------------------------
# Configuration Page Template
# ---------------------------------------------------------------------------

CONFIG_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNIface360 - RTSP Camera Configuration</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --accent-cyan: #00f0ff;
            --accent-magenta: #ff00aa;
            --accent-green: #00ff88;
            --accent-orange: #ff9500;
            --text-primary: #ffffff;
            --text-secondary: #888899;
            --border-color: #2a2a3a;
            --danger: #ff4444;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 20% 0%, rgba(0, 240, 255, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(255, 0, 170, 0.08) 0%, transparent 50%);
        }
        
        .header {
            padding: 1.5rem 2rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .back-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 0.9rem;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.3s ease;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .back-btn:hover {
            border-color: var(--accent-cyan);
            color: var(--accent-cyan);
        }
        
        .logo {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-left: 1rem;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .section-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.2rem;
            color: var(--accent-cyan);
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .cameras-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .camera-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        
        .camera-card:hover {
            border-color: var(--accent-cyan);
            box-shadow: 0 5px 30px rgba(0, 240, 255, 0.1);
        }
        
        .camera-card.disabled {
            opacity: 0.6;
        }
        
        .camera-header {
            padding: 1rem 1.5rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .camera-id {
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9rem;
            color: var(--accent-cyan);
        }
        
        .camera-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .status-dot.connected { background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
        .status-dot.disconnected { background: var(--danger); box-shadow: 0 0 8px var(--danger); }
        .status-dot.disabled { background: var(--text-secondary); }
        
        .camera-preview {
            position: relative;
            width: 100%;
            height: 200px;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .camera-preview img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        
        .camera-preview .no-preview {
            color: var(--text-secondary);
            font-size: 0.85rem;
        }
        
        .camera-body {
            padding: 1.5rem;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        .form-group label {
            display: block;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .form-group input {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 2px rgba(0, 240, 255, 0.1);
        }
        
        .form-group input::placeholder {
            color: var(--text-secondary);
        }
        
        .camera-actions {
            display: flex;
            gap: 0.75rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 0.6rem 1rem;
            border: 1px solid var(--accent-cyan);
            background: transparent;
            color: var(--accent-cyan);
            font-family: inherit;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }
        
        .btn:hover {
            background: var(--accent-cyan);
            color: var(--bg-primary);
        }
        
        .btn-success { border-color: var(--accent-green); color: var(--accent-green); }
        .btn-success:hover { background: var(--accent-green); color: var(--bg-primary); }
        
        .btn-warning { border-color: var(--accent-orange); color: var(--accent-orange); }
        .btn-warning:hover { background: var(--accent-orange); color: var(--bg-primary); }
        
        .btn-danger { border-color: var(--danger); color: var(--danger); }
        .btn-danger:hover { background: var(--danger); color: var(--bg-primary); }
        
        .btn-primary { background: var(--accent-cyan); color: var(--bg-primary); }
        .btn-primary:hover { background: var(--accent-magenta); border-color: var(--accent-magenta); }
        
        .add-camera-card {
            background: var(--bg-card);
            border: 2px dashed var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 400px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .add-camera-card:hover {
            border-color: var(--accent-cyan);
            background: rgba(0, 240, 255, 0.05);
        }
        
        .add-icon {
            font-size: 3rem;
            color: var(--accent-cyan);
            margin-bottom: 1rem;
        }
        
        .add-text {
            font-size: 1rem;
            color: var(--text-secondary);
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active { display: flex; }
        
        .modal-content {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            width: 90%;
            max-width: 500px;
        }
        
        .modal-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.2rem;
            color: var(--accent-cyan);
            margin-bottom: 1.5rem;
        }
        
        .modal-actions {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            margin-top: 1.5rem;
        }
        
        .stats-bar {
            display: flex;
            gap: 0.5rem;
            font-size: 0.7rem;
            color: var(--text-secondary);
            padding: 0.5rem 1.5rem;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        .stat-value {
            color: var(--accent-green);
            font-weight: 600;
        }
        
        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: var(--bg-card);
            border: 1px solid var(--accent-green);
            border-radius: 8px;
            color: var(--accent-green);
            font-size: 0.9rem;
            z-index: 2000;
            display: none;
            animation: slideIn 0.3s ease;
        }
        
        .toast.error {
            border-color: var(--danger);
            color: var(--danger);
        }
        
        .toast.active { display: block; }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .discovered-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            transition: all 0.2s ease;
        }
        
        .discovered-item:hover {
            border-color: var(--accent-cyan);
        }
        
        .discovered-info {
            flex: 1;
        }
        
        .discovered-name {
            font-size: 0.9rem;
            color: var(--text-primary);
            font-weight: 500;
        }
        
        .discovered-url {
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-family: monospace;
            word-break: break-all;
        }
        
        @media (max-width: 768px) {
            .cameras-grid { grid-template-columns: 1fr; }
            .container { padding: 1rem; }
            .camera-actions { flex-direction: column; }
            .btn { width: 100%; justify-content: center; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <a href="/" class="back-btn">← Back to Demo</a>
            <div class="logo">UNIface360</div>
            <span class="subtitle">RTSP Camera Configuration</span>
        </div>
    </header>
    
    <main class="container">
        <!-- Connection Settings Section -->
        <div class="settings-section" style="margin-bottom: 1.5rem; padding: 1.5rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px;">
            <h3 style="font-family: 'Orbitron', sans-serif; font-size: 1.1rem; color: var(--accent-orange); margin: 0 0 1rem 0;">
                ⚙️ Connection Settings
            </h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                <div class="form-group" style="margin: 0;">
                    <label>Camera IP / Subnet</label>
                    <input type="text" id="settingsIp" placeholder="192.168.1.101">
                </div>
                <div class="form-group" style="margin: 0;">
                    <label>Username</label>
                    <input type="text" id="settingsUsername" placeholder="admin">
                </div>
                <div class="form-group" style="margin: 0;">
                    <label>Password</label>
                    <input type="text" id="settingsPassword" placeholder="password">
                </div>
                <div class="form-group" style="margin: 0;">
                    <label>Port</label>
                    <input type="number" id="settingsPort" placeholder="554" value="554">
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 0.75rem; flex-wrap: wrap;">
                <button class="btn btn-success" onclick="saveSettings()">💾 Save Settings</button>
                <button class="btn" onclick="loadSettingsToForm()">↻ Reset</button>
            </div>
        </div>
        
        <!-- Scan Section -->
        <div class="scan-section" style="margin-bottom: 2rem; padding: 1.5rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h3 style="font-family: 'Orbitron', sans-serif; font-size: 1.1rem; color: var(--accent-cyan); margin: 0 0 0.5rem 0;">
                        🔍 Auto-Discover Cameras
                    </h3>
                    <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0;">
                        Scan your network using the settings above
                    </p>
                </div>
                <div style="display: flex; gap: 0.75rem;">
                    <button class="btn btn-primary" onclick="scanNetwork('quick')" id="quickScanBtn">
                        ⚡ Quick Scan
                    </button>
                    <button class="btn" onclick="scanNetwork('full')" id="fullScanBtn">
                        🌐 Full Scan
                    </button>
                </div>
            </div>
            
            <!-- Discovered cameras will appear here -->
            <div id="discoveredCameras" style="display: none; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border-color);">
                <h4 style="font-size: 0.9rem; color: var(--accent-green); margin: 0 0 1rem 0;">
                    ✅ Discovered Cameras <span id="discoveredCount">(0)</span>
                </h4>
                <div id="discoveredList" style="display: grid; gap: 0.75rem; max-height: 300px; overflow-y: auto;"></div>
            </div>
            
            <!-- Scanning indicator -->
            <div id="scanningIndicator" style="display: none; margin-top: 1rem; text-align: center; padding: 1rem;">
                <div style="font-size: 1.5rem; animation: spin 1s linear infinite;">🔄</div>
                <p style="color: var(--text-secondary); font-size: 0.85rem; margin: 0.5rem 0 0 0;">Scanning network...</p>
            </div>
        </div>
        
        <h2 class="section-title">📹 Configured Cameras</h2>
        
        <div class="cameras-grid" id="camerasGrid">
            <!-- Camera cards will be inserted here -->
        </div>
    </main>
    
    <!-- Add Camera Modal -->
    <div class="modal" id="addModal">
        <div class="modal-content">
            <h3 class="modal-title">➕ Add New Camera</h3>
            <div class="form-group">
                <label>Camera ID (Number)</label>
                <input type="number" id="newCameraId" placeholder="e.g., 2" min="0">
            </div>
            <div class="form-group">
                <label>Camera Name</label>
                <input type="text" id="newCameraName" placeholder="e.g., Entrance Camera">
            </div>
            <div class="form-group">
                <label>RTSP URL</label>
                <input type="text" id="newCameraUrl" placeholder="rtsp://user:pass@ip:port/path">
            </div>
            <div class="modal-actions">
                <button class="btn" onclick="closeAddModal()">Cancel</button>
                <button class="btn btn-primary" onclick="addCamera()">Add Camera</button>
            </div>
        </div>
    </div>
    
    <!-- Toast Notification -->
    <div class="toast" id="toast"></div>
    
    <script>
        let cameras = {};
        
        async function loadCameras() {
            try {
                const response = await fetch('/api/rtsp/cameras');
                cameras = await response.json();
                renderCameras();
            } catch (err) {
                showToast('Failed to load cameras', true);
            }
        }
        
        function renderCameras() {
            const grid = document.getElementById('camerasGrid');
            grid.innerHTML = '';
            
            // Sort cameras by ID
            const sortedCameras = Object.entries(cameras).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
            
            for (const [id, cam] of sortedCameras) {
                const card = document.createElement('div');
                card.className = 'camera-card' + (cam.enabled ? '' : ' disabled');
                card.innerHTML = `
                    <div class="camera-header">
                        <span class="camera-id">Camera ${id}</span>
                        <div class="camera-status">
                            <span class="status-dot ${cam.enabled ? (cam.connected ? 'connected' : 'disconnected') : 'disabled'}"></span>
                            <span>${cam.enabled ? (cam.connected ? 'Connected' : 'Disconnected') : 'Disabled'}</span>
                        </div>
                    </div>
                    <div class="camera-preview">
                        ${cam.enabled ? `<img src="/video_feed/${id}" alt="Camera ${id}" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">` : ''}
                        <div class="no-preview" ${cam.enabled ? 'style="display:none"' : ''}>Preview disabled</div>
                    </div>
                    <div class="camera-body">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" id="name_${id}" value="${cam.name}">
                        </div>
                        <div class="form-group">
                            <label>RTSP URL</label>
                            <input type="text" id="url_${id}" value="${cam.url}">
                        </div>
                        <div class="camera-actions">
                            <button class="btn btn-success" onclick="updateCamera(${id})">💾 Save</button>
                            <button class="btn ${cam.enabled ? 'btn-warning' : 'btn-success'}" onclick="toggleCamera(${id}, ${!cam.enabled})">
                                ${cam.enabled ? '⏸ Disable' : '▶ Enable'}
                            </button>
                            <button class="btn" onclick="restartCamera(${id})">↻ Restart</button>
                            <button class="btn btn-danger" onclick="deleteCamera(${id})">🗑 Delete</button>
                        </div>
                    </div>
                    <div class="stats-bar">
                        <span class="stat-item">FPS: <span class="stat-value">${cam.fps || 0}</span></span>
                        <span class="stat-item">Frames: <span class="stat-value">${cam.frame_count || 0}</span></span>
                        ${cam.error ? `<span class="stat-item" style="color: var(--danger)">Error: ${cam.error}</span>` : ''}
                    </div>
                `;
                grid.appendChild(card);
            }
            
            // Add "Add Camera" card
            const addCard = document.createElement('div');
            addCard.className = 'add-camera-card';
            addCard.onclick = openAddModal;
            addCard.innerHTML = `
                <div class="add-icon">+</div>
                <div class="add-text">Add New Camera</div>
            `;
            grid.appendChild(addCard);
        }
        
        async function updateCamera(id) {
            const name = document.getElementById(`name_${id}`).value;
            const url = document.getElementById(`url_${id}`).value;
            
            try {
                const response = await fetch('/api/rtsp/cameras', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, name, url, enabled: cameras[id].enabled })
                });
                
                if (response.ok) {
                    showToast('Camera updated successfully');
                    loadCameras();
                } else {
                    showToast('Failed to update camera', true);
                }
            } catch (err) {
                showToast('Failed to update camera', true);
            }
        }
        
        async function toggleCamera(id, enabled) {
            try {
                const response = await fetch(`/api/rtsp/cameras/${id}/toggle`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled })
                });
                
                if (response.ok) {
                    showToast(enabled ? 'Camera enabled' : 'Camera disabled');
                    loadCameras();
                } else {
                    showToast('Failed to toggle camera', true);
                }
            } catch (err) {
                showToast('Failed to toggle camera', true);
            }
        }
        
        async function restartCamera(id) {
            try {
                const response = await fetch(`/api/rtsp/cameras/${id}/restart`, { method: 'POST' });
                if (response.ok) {
                    showToast('Camera restarting...');
                    setTimeout(loadCameras, 2000);
                } else {
                    showToast('Failed to restart camera', true);
                }
            } catch (err) {
                showToast('Failed to restart camera', true);
            }
        }
        
        let deleteInProgress = false;
        
        async function deleteCamera(id) {
            console.log('[DELETE] Button clicked for camera', id);
            
            // Prevent multiple simultaneous deletes
            if (deleteInProgress) {
                console.log('[DELETE] Another delete in progress, please wait...');
                showToast('⏳ Please wait, processing...', true);
                return;
            }
            
            if (!confirm(`Are you sure you want to delete Camera ${id}?`)) {
                console.log('[DELETE] User cancelled');
                return;
            }
            
            deleteInProgress = true;
            console.log('[DELETE] Sending DELETE request...');
            
            // Create abort controller for timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            try {
                const response = await fetch(`/api/rtsp/cameras/${id}`, { 
                    method: 'DELETE',
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                console.log('[DELETE] Response status:', response.status);
                
                const text = await response.text();
                console.log('[DELETE] Raw response:', text);
                
                let data;
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    console.error('[DELETE] Failed to parse JSON:', e);
                    showToast('❌ Server error', true);
                    return;
                }
                
                console.log('[DELETE] Response data:', data);
                
                if (data.ok) {
                    showToast('✅ Camera ' + id + ' deleted!');
                    console.log('[DELETE] Reloading cameras...');
                    await loadCameras();
                } else {
                    showToast('❌ ' + (data.error || 'Failed to delete'), true);
                }
            } catch (err) {
                clearTimeout(timeoutId);
                if (err.name === 'AbortError') {
                    console.error('[DELETE] Request timed out');
                    showToast('❌ Request timed out - try again', true);
                } else {
                    console.error('[DELETE] Error:', err);
                    showToast('❌ Error: ' + err.message, true);
                }
            } finally {
                deleteInProgress = false;
            }
        }
        
        function openAddModal() {
            document.getElementById('addModal').classList.add('active');
            // Suggest next available ID
            const maxId = Math.max(-1, ...Object.keys(cameras).map(Number));
            document.getElementById('newCameraId').value = maxId + 1;
        }
        
        function closeAddModal() {
            document.getElementById('addModal').classList.remove('active');
        }
        
        async function addCamera() {
            const id = parseInt(document.getElementById('newCameraId').value);
            const name = document.getElementById('newCameraName').value;
            const url = document.getElementById('newCameraUrl').value;
            
            if (isNaN(id) || !name || !url) {
                showToast('Please fill all fields', true);
                return;
            }
            
            try {
                const response = await fetch('/api/rtsp/cameras', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, name, url, enabled: true })
                });
                
                if (response.ok) {
                    showToast('Camera added successfully');
                    closeAddModal();
                    loadCameras();
                } else {
                    showToast('Failed to add camera', true);
                }
            } catch (err) {
                showToast('Failed to add camera', true);
            }
        }
        
        function showToast(message, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast active' + (isError ? ' error' : '');
            setTimeout(() => toast.classList.remove('active'), 3000);
        }
        
        // Settings management
        let currentSettings = {};
        
        async function loadSettingsToForm() {
            try {
                const response = await fetch('/api/rtsp/settings');
                currentSettings = await response.json();
                
                document.getElementById('settingsIp').value = currentSettings.ip || '';
                document.getElementById('settingsUsername').value = currentSettings.username || '';
                document.getElementById('settingsPassword').value = currentSettings.password || '';
                document.getElementById('settingsPort').value = currentSettings.port || 554;
            } catch (err) {
                console.error('Failed to load settings:', err);
            }
        }
        
        async function saveSettings() {
            const settings = {
                ip: document.getElementById('settingsIp').value,
                username: document.getElementById('settingsUsername').value,
                password: document.getElementById('settingsPassword').value,
                port: parseInt(document.getElementById('settingsPort').value) || 554
            };
            
            try {
                const response = await fetch('/api/rtsp/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                if (response.ok) {
                    currentSettings = settings;
                    showToast('Settings saved successfully!');
                } else {
                    showToast('Failed to save settings', true);
                }
            } catch (err) {
                showToast('Failed to save settings', true);
            }
        }
        
        function getSettingsFromForm() {
            return {
                ip: document.getElementById('settingsIp').value || currentSettings.ip,
                username: document.getElementById('settingsUsername').value || currentSettings.username,
                password: document.getElementById('settingsPassword').value || currentSettings.password,
                port: parseInt(document.getElementById('settingsPort').value) || currentSettings.port || 554
            };
        }
        
        // Network scanning
        let discoveredCameras = [];
        
        async function scanNetwork(scanType) {
            const quickBtn = document.getElementById('quickScanBtn');
            const fullBtn = document.getElementById('fullScanBtn');
            const indicator = document.getElementById('scanningIndicator');
            const discoveredSection = document.getElementById('discoveredCameras');
            
            // Disable buttons and show loading
            quickBtn.disabled = true;
            fullBtn.disabled = true;
            quickBtn.style.opacity = '0.5';
            fullBtn.style.opacity = '0.5';
            indicator.style.display = 'block';
            discoveredSection.style.display = 'none';
            
            showToast(scanType === 'quick' ? 'Quick scanning...' : 'Full network scan (may take a minute)...');
            
            // Get settings from form
            const settings = getSettingsFromForm();
            
            try {
                const response = await fetch('/api/rtsp/discover', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        scan_type: scanType,
                        ip: settings.ip,
                        username: settings.username,
                        password: settings.password,
                        port: settings.port
                    })
                });
                
                const data = await response.json();
                
                if (data.ok && data.cameras.length > 0) {
                    discoveredCameras = data.cameras;
                    renderDiscoveredCameras();
                    showToast(`Found ${data.cameras.length} camera(s)!`);
                } else if (data.ok) {
                    showToast('No cameras found on the network', true);
                } else {
                    showToast('Scan failed: ' + (data.error || 'Unknown error'), true);
                }
            } catch (err) {
                showToast('Scan failed: ' + err.message, true);
            } finally {
                // Re-enable buttons
                quickBtn.disabled = false;
                fullBtn.disabled = false;
                quickBtn.style.opacity = '1';
                fullBtn.style.opacity = '1';
                indicator.style.display = 'none';
            }
        }
        
        function renderDiscoveredCameras() {
            const section = document.getElementById('discoveredCameras');
            const list = document.getElementById('discoveredList');
            const count = document.getElementById('discoveredCount');
            
            if (discoveredCameras.length === 0) {
                section.style.display = 'none';
                return;
            }
            
            section.style.display = 'block';
            count.textContent = `(${discoveredCameras.length})`;
            
            list.innerHTML = discoveredCameras.map((cam, idx) => `
                <div class="discovered-item">
                    <div class="discovered-info">
                        <div class="discovered-name">${cam.name}</div>
                        <div class="discovered-url">${cam.url}</div>
                    </div>
                    <button class="btn btn-success" onclick="addDiscoveredCamera(${idx})" style="flex-shrink: 0;">
                        ➕ Add
                    </button>
                </div>
            `).join('');
        }
        
        async function addDiscoveredCamera(index) {
            const cam = discoveredCameras[index];
            if (!cam) return;
            
            // Find next available ID
            const maxId = Math.max(-1, ...Object.keys(cameras).map(Number));
            const newId = maxId + 1;
            
            try {
                const response = await fetch('/api/rtsp/cameras', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: newId,
                        name: cam.name,
                        url: cam.url,
                        enabled: true
                    })
                });
                
                if (response.ok) {
                    showToast(`Camera added as ID ${newId}`);
                    // Remove from discovered list
                    discoveredCameras.splice(index, 1);
                    renderDiscoveredCameras();
                    loadCameras();
                } else {
                    showToast('Failed to add camera', true);
                }
            } catch (err) {
                showToast('Failed to add camera', true);
            }
        }
        
        // Initial load and periodic refresh
        loadCameras();
        loadSettingsToForm();
        setInterval(loadCameras, 5000);
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Management Page Template
# ---------------------------------------------------------------------------

MANAGEMENT_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNIface360 - Person & Zone Management</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-hover: #1a1a24;
            --border: #2a2a3a;
            --text: #ffffff;
            --text-muted: #888899;
            --cyan: #00f0ff;
            --magenta: #ff00aa;
            --green: #00ff88;
            --orange: #ff9500;
            --red: #ff4444;
            --purple: #a855f7;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 20% 0%, rgba(0, 240, 255, 0.05) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(168, 85, 247, 0.05) 0%, transparent 50%);
        }
        
        .header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }
        
        .back-link {
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
        }
        
        .back-link:hover { color: var(--cyan); }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .tabs {
            display: flex;
            gap: 0.5rem;
            background: var(--bg-hover);
            padding: 0.25rem;
            border-radius: 10px;
        }
        
        .tab-btn {
            padding: 0.6rem 1.5rem;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
        }
        
        .tab-btn:hover { color: var(--text); }
        .tab-btn.active { background: var(--cyan); color: var(--bg-dark); }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* Cards Grid */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.5rem;
        }
        
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
        }
        
        .card:hover {
            border-color: var(--cyan);
            box-shadow: 0 10px 40px rgba(0, 240, 255, 0.1);
        }
        
        .card-header {
            padding: 1rem 1.25rem;
            background: var(--bg-hover);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-title {
            font-weight: 600;
            font-size: 1rem;
        }
        
        .card-badge {
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge-authorized { background: rgba(0, 255, 136, 0.15); color: var(--green); }
        .badge-unauthorized { background: rgba(255, 68, 68, 0.15); color: var(--red); }
        .badge-restricted { background: rgba(255, 149, 0, 0.15); color: var(--orange); }
        .badge-normal { background: rgba(0, 240, 255, 0.15); color: var(--cyan); }
        
        .card-body {
            padding: 1.25rem;
        }
        
        .photos-grid {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        
        .photo-thumb {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            object-fit: cover;
            border: 2px solid var(--border);
        }
        
        .photo-count {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            background: var(--bg-hover);
            border: 2px dashed var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            color: var(--text-muted);
        }
        
        .card-info {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }
        
        .card-actions {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-muted);
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
        }
        
        .btn:hover { border-color: var(--cyan); color: var(--cyan); }
        .btn-primary { background: var(--cyan); color: var(--bg-dark); border-color: var(--cyan); }
        .btn-primary:hover { background: var(--green); border-color: var(--green); }
        .btn-success { border-color: var(--green); color: var(--green); }
        .btn-success:hover { background: var(--green); color: var(--bg-dark); }
        .btn-danger { border-color: var(--red); color: var(--red); }
        .btn-danger:hover { background: var(--red); color: var(--text); }
        .btn-warning { border-color: var(--orange); color: var(--orange); }
        .btn-warning:hover { background: var(--orange); color: var(--bg-dark); }
        
        /* Add Card */
        .add-card {
            border: 2px dashed var(--border);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 250px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .add-card:hover {
            border-color: var(--cyan);
            background: rgba(0, 240, 255, 0.05);
        }
        
        .add-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            color: var(--cyan);
        }
        
        .add-text {
            color: var(--text-muted);
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(10px);
        }
        
        .modal.active { display: flex; }
        
        .modal-content {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            max-width: 600px;
            width: 95%;
            max-height: 90vh;
            overflow: auto;
        }
        
        .modal-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-title {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
        }
        
        .modal-close:hover { color: var(--red); }
        
        .modal-body {
            padding: 1.5rem;
        }
        
        .form-group {
            margin-bottom: 1.25rem;
        }
        
        .form-label {
            display: block;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .form-input, .form-select {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--bg-hover);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-family: inherit;
            font-size: 0.9rem;
        }
        
        .form-input:focus, .form-select:focus {
            outline: none;
            border-color: var(--cyan);
        }
        
        .form-checkbox {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            cursor: pointer;
        }
        
        .form-checkbox input {
            width: 20px;
            height: 20px;
            accent-color: var(--cyan);
        }
        
        .modal-footer {
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
        }
        
        /* Camera Preview */
        .camera-preview {
            width: 100%;
            aspect-ratio: 16/9;
            background: #000;
            border-radius: 8px;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        
        .camera-preview img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        
        .camera-controls {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        /* File Upload */
        .file-drop {
            border: 2px dashed var(--border);
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 1rem;
        }
        
        .file-drop:hover, .file-drop.dragover {
            border-color: var(--cyan);
            background: rgba(0, 240, 255, 0.05);
        }
        
        .file-drop-icon {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .file-drop-text {
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        
        .file-drop input {
            display: none;
        }
        
        /* Toast */
        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: var(--bg-card);
            border: 1px solid var(--green);
            border-radius: 10px;
            color: var(--green);
            font-size: 0.9rem;
            z-index: 2000;
            display: none;
            animation: slideIn 0.3s ease;
        }
        
        .toast.error { border-color: var(--red); color: var(--red); }
        .toast.active { display: block; }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        /* Train Button */
        .train-section {
            background: linear-gradient(135deg, rgba(0, 240, 255, 0.1), rgba(168, 85, 247, 0.1));
            border: 1px solid var(--cyan);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }
        
        .train-info h3 {
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }
        
        .train-info p {
            font-size: 0.85rem;
            color: var(--text-muted);
        }
        
        .train-btn {
            padding: 0.75rem 2rem;
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            border: none;
            border-radius: 10px;
            color: var(--text);
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .train-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(0, 240, 255, 0.3);
        }
        
        .train-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Training Progress */
        .train-progress {
            margin-top: 1rem;
            display: none;
        }
        
        .train-progress.active {
            display: block;
        }
        
        .progress-bar-container {
            background: var(--bg-hover);
            border-radius: 10px;
            height: 24px;
            overflow: hidden;
            margin-bottom: 0.75rem;
        }
        
        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--cyan), var(--purple));
            border-radius: 10px;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--bg-dark);
        }
        
        .train-logs {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            max-height: 200px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            margin-top: 1rem;
        }
        
        .train-logs p {
            margin: 0.25rem 0;
            color: var(--text-muted);
        }
        
        .train-logs p.success { color: var(--green); }
        .train-logs p.error { color: var(--red); }
        .train-logs p.warning { color: var(--orange); }
        
        /* Model Camera Config */
        .model-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        
        .model-header {
            padding: 1rem 1.25rem;
            background: var(--bg-hover);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .model-title {
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .model-body {
            padding: 1rem;
        }
        
        .camera-config-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .camera-config-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            background: var(--bg-hover);
            border-radius: 8px;
            gap: 1rem;
        }
        
        .camera-config-info {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex: 1;
        }
        
        .camera-config-icon {
            font-size: 1.2rem;
        }
        
        .camera-config-name {
            font-weight: 500;
        }
        
        .camera-config-id {
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .camera-config-actions {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        
        .toggle-switch {
            position: relative;
            width: 48px;
            height: 24px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--border);
            transition: 0.3s;
            border-radius: 24px;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background: white;
            transition: 0.3s;
            border-radius: 50%;
        }
        
        .toggle-switch input:checked + .toggle-slider {
            background: var(--green);
        }
        
        .toggle-switch input:checked + .toggle-slider:before {
            transform: translateX(24px);
        }
        
        .restricted-toggle input:checked + .toggle-slider {
            background: var(--red);
        }
        
        .add-camera-btn {
            width: 100%;
            padding: 0.75rem;
            border: 2px dashed var(--border);
            background: transparent;
            color: var(--text-muted);
            font-family: inherit;
            font-size: 0.9rem;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
            margin-top: 0.5rem;
        }
        
        .add-camera-btn:hover {
            border-color: var(--cyan);
            color: var(--cyan);
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <a href="/demo" class="back-link">← Back to Demo</a>
            <div class="logo">Person & Zone Management</div>
        </div>
        <div class="tabs">
            <button class="tab-btn active" data-tab="persons">👤 Persons</button>
            <button class="tab-btn" data-tab="unauthorized">🚫 Unauthorized</button>
            <button class="tab-btn" data-tab="restricted">⚠️ Restricted</button>
            <button class="tab-btn" data-tab="ppe">🦺 PPE</button>
            <button class="tab-btn" data-tab="evacuation">🏃 Evacuation</button>
        </div>
    </header>
    
    <main class="container">
        <!-- Persons Tab -->
        <div class="tab-content active" id="persons-tab">
            <div class="train-section">
                <div class="train-info">
                    <h3>🧠 Train Face Recognition</h3>
                    <p>Train the AI model with all registered persons' photos</p>
                </div>
                <button class="train-btn" id="trainBtn" onclick="trainFaces()">⚡ Train Now</button>
            </div>
            
            <!-- Training Progress -->
            <div class="train-progress" id="trainProgress">
                <div class="progress-bar-container">
                    <div class="progress-bar" id="progressBar" style="width: 0%">0%</div>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-muted);">
                    <span id="progressStatus">Initializing...</span>
                </div>
                <div class="train-logs" id="trainLogs"></div>
            </div>
            
            <div class="section-title">👤 Registered Persons</div>
            <div class="cards-grid" id="personsGrid">
                <!-- Cards will be loaded here -->
            </div>
        </div>
        
        <!-- Unauthorized Model Tab -->
        <div class="tab-content" id="unauthorized-tab">
            <div class="section-title">🚫 Unauthorized Person Detection Cameras</div>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Configure which cameras are used for unauthorized person detection. Enable cameras to monitor for unknown faces.</p>
            
            <div class="model-section">
                <div class="model-header">
                    <div class="model-title">📹 Assigned Cameras</div>
                    <button class="btn btn-primary" onclick="openAddCameraModal('unauthorized')">+ Add Camera</button>
                </div>
                <div class="model-body">
                    <div class="camera-config-list" id="unauthorizedCameras">
                        <!-- Cameras will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Restricted Area Tab -->
        <div class="tab-content" id="restricted-tab">
            <div class="section-title">⚠️ Restricted Area Detection Cameras</div>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Configure cameras for restricted area monitoring. Mark which cameras cover restricted zones.</p>
            
            <div class="model-section">
                <div class="model-header">
                    <div class="model-title">📹 Assigned Cameras</div>
                    <button class="btn btn-primary" onclick="openAddCameraModal('restricted')">+ Add Camera</button>
                </div>
                <div class="model-body">
                    <div class="camera-config-list" id="restrictedCameras">
                        <!-- Cameras will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- PPE Tab -->
        <div class="tab-content" id="ppe-tab">
            <div class="section-title">🦺 PPE Detection Cameras</div>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Configure cameras for PPE (hardhat) compliance monitoring.</p>
            
            <div class="model-section">
                <div class="model-header">
                    <div class="model-title">📹 Assigned Cameras</div>
                    <button class="btn btn-primary" onclick="openAddCameraModal('ppe')">+ Add Camera</button>
                </div>
                <div class="model-body">
                    <div class="camera-config-list" id="ppeCameras">
                        <!-- Cameras will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Evacuation Tab -->
        <div class="tab-content" id="evacuation-tab">
            <div class="section-title">🏃 Evacuation System Cameras</div>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Configure cameras for evacuation tracking and live person detection.</p>
            
            <div class="model-section">
                <div class="model-header">
                    <div class="model-title">📹 Assigned Cameras</div>
                    <button class="btn btn-primary" onclick="openAddCameraModal('evacuation')">+ Add Camera</button>
                </div>
                <div class="model-body">
                    <div class="camera-config-list" id="evacuationCameras">
                        <!-- Cameras will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Add Person Modal -->
    <div class="modal" id="addPersonModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">👤 Add New Person</div>
                <button class="modal-close" onclick="closeModal('addPersonModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Name</label>
                    <input type="text" class="form-input" id="personName" placeholder="Enter person's name">
                </div>
                <div class="form-group">
                    <label class="form-checkbox">
                        <input type="checkbox" id="personAuthorized" checked>
                        <span>Authorized (can access system)</span>
                    </label>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeModal('addPersonModal')">Cancel</button>
                <button class="btn btn-primary" onclick="addPerson()">Add Person</button>
            </div>
        </div>
    </div>
    
    <!-- Add Photo Modal -->
    <div class="modal" id="addPhotoModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">📸 Add Photo for <span id="photoPersonName"></span></div>
                <button class="modal-close" onclick="closeModal('addPhotoModal')">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Camera Capture -->
                <div class="form-group">
                    <label class="form-label">Option 1: Camera Capture</label>
                    <div class="camera-preview">
                        <img id="cameraPreview" src="" alt="Camera preview">
                    </div>
                    <div class="camera-controls">
                        <select class="form-select" id="cameraSelect" style="flex: 1;">
                            <option value="0">Loading cameras...</option>
                        </select>
                        <button class="btn btn-success" onclick="captureFromCamera()">📸 Capture</button>
                    </div>
                </div>
                
                <!-- File Upload -->
                <div class="form-group">
                    <label class="form-label">Option 2: Upload Photo</label>
                    <div class="file-drop" id="fileDrop">
                        <div class="file-drop-icon">📁</div>
                        <div class="file-drop-text">Click or drag & drop photo here</div>
                        <input type="file" id="fileInput" accept="image/*" multiple>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeModal('addPhotoModal')">Done</button>
            </div>
        </div>
    </div>
    
    <!-- Add Zone Modal -->
    <div class="modal" id="addZoneModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">📍 Add New Zone</div>
                <button class="modal-close" onclick="closeModal('addZoneModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Zone Name</label>
                    <input type="text" class="form-input" id="zoneName" placeholder="e.g., Server Room, Warehouse">
                </div>
                <div class="form-group">
                    <label class="form-label">Assigned Camera</label>
                    <select class="form-select" id="zoneCamera">
                        <option value="0">Loading cameras...</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-checkbox">
                        <input type="checkbox" id="zoneRestricted">
                        <span>🔴 Restricted Zone (triggers alerts when persons detected)</span>
                    </label>
                </div>
                <div class="form-group">
                    <label class="form-label">Description (Optional)</label>
                    <input type="text" class="form-input" id="zoneDescription" placeholder="Brief description of this zone">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeModal('addZoneModal')">Cancel</button>
                <button class="btn btn-primary" onclick="addZone()">Add Zone</button>
            </div>
        </div>
    </div>
    
    <!-- Add Camera to Model Modal -->
    <div class="modal" id="addCameraModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">📹 Add Camera to Detection</div>
                <button class="modal-close" onclick="closeModal('addCameraModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Select Camera</label>
                    <select class="form-input" id="addCameraSelect">
                        <!-- Options will be populated dynamically -->
                    </select>
                </div>
                <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 1rem;">
                    You can enable/disable cameras and configure restricted zones after adding.
                </p>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeModal('addCameraModal')">Cancel</button>
                <button class="btn btn-primary" onclick="addCameraToModel()">Add Camera</button>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let persons = [];
        let zones = [];
        let cameras = {};
        let modelCameras = { unauthorized: {}, restricted: {}, ppe: {} };
        let currentPhotoPersonId = null;
        let currentModelType = null;
        let trainingInterval = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadCameras();
            loadPersons();
            loadModelCameras();
            
            // Tab switching
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    btn.classList.add('active');
                    document.getElementById(btn.dataset.tab + '-tab').classList.add('active');
                });
            });
            
            // File drop
            const fileDrop = document.getElementById('fileDrop');
            const fileInput = document.getElementById('fileInput');
            
            fileDrop.addEventListener('click', () => fileInput.click());
            fileDrop.addEventListener('dragover', (e) => {
                e.preventDefault();
                fileDrop.classList.add('dragover');
            });
            fileDrop.addEventListener('dragleave', () => fileDrop.classList.remove('dragover'));
            fileDrop.addEventListener('drop', (e) => {
                e.preventDefault();
                fileDrop.classList.remove('dragover');
                handleFiles(e.dataTransfer.files);
            });
            fileInput.addEventListener('change', () => handleFiles(fileInput.files));
        });
        
        async function loadCameras() {
            try {
                const res = await fetch('/api/rtsp/cameras');
                cameras = await res.json();
                
                const selects = [document.getElementById('cameraSelect'), document.getElementById('zoneCamera')];
                selects.forEach(select => {
                    if (!select) return;
                    select.innerHTML = '';
                    Object.entries(cameras).sort((a, b) => parseInt(a[0]) - parseInt(b[0])).forEach(([id, cam]) => {
                        const opt = document.createElement('option');
                        opt.value = id;
                        opt.textContent = `${cam.name} (Camera ${id})`;
                        select.appendChild(opt);
                    });
                });
            } catch (err) {
                console.error('Failed to load cameras:', err);
            }
        }
        
        async function loadPersons() {
            try {
                const res = await fetch('/api/persons');
                const data = await res.json();
                persons = data.persons || [];
                renderPersons();
            } catch (err) {
                console.error('Failed to load persons:', err);
            }
        }
        
        function renderPersons() {
            const grid = document.getElementById('personsGrid');
            grid.innerHTML = '';
            
            persons.forEach(person => {
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title">${person.name}</div>
                        <span class="card-badge ${person.authorized ? 'badge-authorized' : 'badge-unauthorized'}">
                            ${person.authorized ? '✓ Authorized' : '✗ Unauthorized'}
                        </span>
                    </div>
                    <div class="card-body">
                        <div class="photos-grid">
                            ${(person.photos || []).map(p => `<img src="${p}" class="photo-thumb" alt="Photo">`).join('')}
                            <div class="photo-count">${person.photo_count} photos</div>
                        </div>
                        <div class="card-info">
                            ${person.trained ? '🧠 Trained' : '⏳ Not trained'} | 
                            ID: ${person.id}
                        </div>
                        <div class="card-actions">
                            <button class="btn btn-success" onclick="openPhotoModal('${person.id}', '${person.name}')">📸 Add Photo</button>
                            <button class="btn ${person.authorized ? 'btn-warning' : 'btn-success'}" onclick="toggleAuthorization('${person.id}', ${!person.authorized})">
                                ${person.authorized ? '🔒 Revoke' : '🔓 Authorize'}
                            </button>
                            <button class="btn btn-danger" onclick="deletePerson('${person.id}')">🗑</button>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });
            
            // Add card
            const addCard = document.createElement('div');
            addCard.className = 'card add-card';
            addCard.onclick = () => openModal('addPersonModal');
            addCard.innerHTML = `
                <div class="add-icon">+</div>
                <div class="add-text">Add New Person</div>
            `;
            grid.appendChild(addCard);
        }
        
        async function loadZones() {
            try {
                const res = await fetch('/api/zones');
                const data = await res.json();
                zones = data.zones || [];
                renderZones();
            } catch (err) {
                console.error('Failed to load zones:', err);
            }
        }
        
        function renderZones() {
            const grid = document.getElementById('zonesGrid');
            grid.innerHTML = '';
            
            zones.forEach(zone => {
                const cam = cameras[zone.camera_id] || { name: `Camera ${zone.camera_id}` };
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title">${zone.name}</div>
                        <span class="card-badge ${zone.is_restricted ? 'badge-restricted' : 'badge-normal'}">
                            ${zone.is_restricted ? '🔴 Restricted' : '🟢 Normal'}
                        </span>
                    </div>
                    <div class="card-body">
                        <div class="card-info">
                            📹 ${cam.name}<br>
                            ${zone.description || 'No description'}
                        </div>
                        <div class="card-actions">
                            <button class="btn ${zone.is_restricted ? 'btn-success' : 'btn-warning'}" onclick="toggleZoneRestricted('${zone.id}', ${!zone.is_restricted})">
                                ${zone.is_restricted ? '🟢 Make Normal' : '🔴 Make Restricted'}
                            </button>
                            <button class="btn btn-danger" onclick="deleteZone('${zone.id}')">🗑</button>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });
            
            // Add card
            const addCard = document.createElement('div');
            addCard.className = 'card add-card';
            addCard.onclick = () => openModal('addZoneModal');
            addCard.innerHTML = `
                <div class="add-icon">+</div>
                <div class="add-text">Add New Zone</div>
            `;
            grid.appendChild(addCard);
        }
        
        function openModal(id) {
            document.getElementById(id).classList.add('active');
        }
        
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }
        
        function openPhotoModal(personId, personName) {
            currentPhotoPersonId = personId;
            document.getElementById('photoPersonName').textContent = personName;
            
            // Start camera preview
            const camId = document.getElementById('cameraSelect').value;
            document.getElementById('cameraPreview').src = `/video_feed/${camId}`;
            
            openModal('addPhotoModal');
        }
        
        async function addPerson() {
            const name = document.getElementById('personName').value.trim();
            const authorized = document.getElementById('personAuthorized').checked;
            
            if (!name) {
                showToast('Please enter a name', true);
                return;
            }
            
            try {
                const res = await fetch('/api/persons', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, authorized })
                });
                
                if (res.ok) {
                    showToast('Person added successfully');
                    closeModal('addPersonModal');
                    document.getElementById('personName').value = '';
                    loadPersons();
                } else {
                    showToast('Failed to add person', true);
                }
            } catch (err) {
                showToast('Failed to add person', true);
            }
        }
        
        async function toggleAuthorization(personId, authorized) {
            try {
                const res = await fetch(`/api/persons/${personId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ authorized })
                });
                
                if (res.ok) {
                    showToast(authorized ? 'Person authorized' : 'Authorization revoked');
                    loadPersons();
                }
            } catch (err) {
                showToast('Failed to update', true);
            }
        }
        
        async function deletePerson(personId) {
            if (!confirm('Delete this person and all their photos?')) return;
            
            try {
                const res = await fetch(`/api/persons/${personId}`, { method: 'DELETE' });
                if (res.ok) {
                    showToast('Person deleted');
                    loadPersons();
                }
            } catch (err) {
                showToast('Failed to delete', true);
            }
        }
        
        async function captureFromCamera() {
            if (!currentPhotoPersonId) return;
            
            const camId = document.getElementById('cameraSelect').value;
            
            try {
                const res = await fetch(`/api/persons/${currentPhotoPersonId}/capture`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_id: parseInt(camId) })
                });
                
                if (res.ok) {
                    showToast('Photo captured!');
                    loadPersons();
                } else {
                    showToast('Failed to capture', true);
                }
            } catch (err) {
                showToast('Failed to capture', true);
            }
        }
        
        async function handleFiles(files) {
            if (!currentPhotoPersonId || !files.length) return;
            
            for (const file of files) {
                const formData = new FormData();
                formData.append('photo', file);
                
                try {
                    const res = await fetch(`/api/persons/${currentPhotoPersonId}/photo`, {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (res.ok) {
                        showToast(`Photo uploaded: ${file.name}`);
                    }
                } catch (err) {
                    showToast(`Failed to upload ${file.name}`, true);
                }
            }
            
            loadPersons();
        }
        
        async function trainFaces() {
            const btn = document.getElementById('trainBtn');
            const progressDiv = document.getElementById('trainProgress');
            const progressBar = document.getElementById('progressBar');
            const progressStatus = document.getElementById('progressStatus');
            const logsDiv = document.getElementById('trainLogs');
            
            btn.disabled = true;
            btn.textContent = '⏳ Training...';
            progressDiv.classList.add('active');
            logsDiv.innerHTML = '';
            
            // Start progress polling
            trainingInterval = setInterval(async () => {
                try {
                    const res = await fetch('/api/persons/train/progress');
                    const progress = await res.json();
                    
                    progressBar.style.width = progress.percentage + '%';
                    progressBar.textContent = progress.percentage + '%';
                    
                    if (progress.current_person) {
                        progressStatus.textContent = `Processing: ${progress.current_person} (${progress.photos_done}/${progress.total_photos} photos)`;
                    }
                    
                    // Update logs
                    if (progress.logs && progress.logs.length > 0) {
                        logsDiv.innerHTML = progress.logs.map(log => {
                            let cls = '';
                            if (log.includes('✓') || log.includes('✅')) cls = 'success';
                            else if (log.includes('✗') || log.includes('❌')) cls = 'error';
                            else if (log.includes('⚠')) cls = 'warning';
                            return `<p class="${cls}">${log}</p>`;
                        }).join('');
                        logsDiv.scrollTop = logsDiv.scrollHeight;
                    }
                } catch (e) {}
            }, 500);
            
            try {
                const res = await fetch('/api/persons/train', { method: 'POST' });
                const data = await res.json();
                
                clearInterval(trainingInterval);
                
                if (data.ok) {
                    progressBar.style.width = '100%';
                    progressBar.textContent = '100%';
                    progressStatus.textContent = 'Training complete!';
                    
                    // Show final logs
                    if (data.logs) {
                        logsDiv.innerHTML = data.logs.map(log => {
                            let cls = '';
                            if (log.includes('✓') || log.includes('✅')) cls = 'success';
                            else if (log.includes('✗') || log.includes('❌')) cls = 'error';
                            else if (log.includes('⚠')) cls = 'warning';
                            return `<p class="${cls}">${log}</p>`;
                        }).join('');
                    }
                    
                    showToast(`Training complete! ${data.persons_count} persons, ${data.total_faces} faces`);
                    loadPersons();
                } else {
                    progressStatus.textContent = 'Training failed!';
                    showToast('Training failed: ' + data.error, true);
                }
            } catch (err) {
                clearInterval(trainingInterval);
                progressStatus.textContent = 'Training failed!';
                showToast('Training failed', true);
            } finally {
                btn.disabled = false;
                btn.textContent = '⚡ Train Now';
            }
        }
        
        // Model Camera Functions
        async function loadModelCameras() {
            try {
                const res = await fetch('/api/model-cameras');
                const data = await res.json();
                modelCameras = data.config || { unauthorized: {}, restricted: {}, ppe: {}, evacuation: {} };
                renderModelCameras('unauthorized');
                renderModelCameras('restricted');
                renderModelCameras('ppe');
                renderModelCameras('evacuation');
            } catch (err) {
                console.error('Failed to load model cameras:', err);
            }
        }
        
        function renderModelCameras(modelType) {
            const container = document.getElementById(modelType + 'Cameras');
            if (!container) return;
            
            const camConfigs = modelCameras[modelType] || {};
            const entries = Object.entries(camConfigs);
            
            if (entries.length === 0) {
                container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No cameras configured. Click "Add Camera" to start.</p>';
                return;
            }
            
            container.innerHTML = entries.map(([camId, cfg]) => {
                const cam = cameras[camId] || { name: cfg.name || `Camera ${camId}` };
                const isRestricted = modelType === 'restricted';
                const isEvacuation = modelType === 'evacuation';
                
                // Build toggle for special zones
                let zoneToggle = '';
                if (isRestricted) {
                    zoneToggle = `
                        <span style="font-size: 0.8rem; color: var(--text-muted); margin-right: 0.5rem;">Restricted:</span>
                        <label class="toggle-switch restricted-toggle">
                            <input type="checkbox" ${cfg.is_restricted ? 'checked' : ''} 
                                   onchange="toggleCameraRestricted('${modelType}', ${camId}, this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    `;
                } else if (isEvacuation) {
                    zoneToggle = `
                        <span style="font-size: 0.8rem; color: var(--text-muted); margin-right: 0.5rem;">Evacuation Zone:</span>
                        <label class="toggle-switch restricted-toggle">
                            <input type="checkbox" ${cfg.is_evacuation_zone ? 'checked' : ''} 
                                   onchange="toggleCameraEvacuationZone('${modelType}', ${camId}, this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    `;
                }
                
                return `
                    <div class="camera-config-item">
                        <div class="camera-config-info">
                            <span class="camera-config-icon">📹</span>
                            <div>
                                <div class="camera-config-name">${cfg.name || cam.name}</div>
                                <div class="camera-config-id">Camera ${camId}</div>
                            </div>
                        </div>
                        <div class="camera-config-actions">
                            ${zoneToggle}
                            <span style="font-size: 0.8rem; color: var(--text-muted); margin: 0 0.5rem;">Enabled:</span>
                            <label class="toggle-switch">
                                <input type="checkbox" ${cfg.enabled ? 'checked' : ''} 
                                       onchange="toggleCameraEnabled('${modelType}', ${camId}, this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                            <button class="btn btn-danger" onclick="removeModelCamera('${modelType}', ${camId})" style="padding: 0.4rem 0.6rem;">🗑</button>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function openAddCameraModal(modelType) {
            currentModelType = modelType;
            // Show camera selection
            const availableCameras = Object.entries(cameras).filter(([id, cam]) => {
                return !modelCameras[modelType]?.[id];
            });
            
            if (availableCameras.length === 0) {
                showToast('All cameras are already added to this model', true);
                return;
            }
            
            const select = document.getElementById('addCameraSelect');
            select.innerHTML = availableCameras.map(([id, cam]) => 
                `<option value="${id}">${cam.name} (Camera ${id})</option>`
            ).join('');
            
            openModal('addCameraModal');
        }
        
        async function addCameraToModel() {
            const camId = parseInt(document.getElementById('addCameraSelect').value);
            const cam = cameras[camId];
            
            try {
                const res = await fetch(`/api/model-cameras/${currentModelType}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        camera_id: camId,
                        name: cam?.name || `Camera ${camId}`,
                        enabled: true,
                        is_restricted: false
                    })
                });
                
                if (res.ok) {
                    showToast('Camera added');
                    closeModal('addCameraModal');
                    loadModelCameras();
                } else {
                    showToast('Failed to add camera', true);
                }
            } catch (err) {
                showToast('Failed to add camera', true);
            }
        }
        
        async function toggleCameraEnabled(modelType, camId, enabled) {
            try {
                await fetch(`/api/model-cameras/${modelType}/${camId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled })
                });
                showToast(enabled ? 'Camera enabled' : 'Camera disabled');
            } catch (err) {
                showToast('Failed to update', true);
                loadModelCameras();
            }
        }
        
        async function toggleCameraRestricted(modelType, camId, is_restricted) {
            try {
                await fetch(`/api/model-cameras/${modelType}/${camId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_restricted })
                });
                showToast(is_restricted ? 'Camera marked as RESTRICTED' : 'Camera marked as normal');
            } catch (err) {
                showToast('Failed to update', true);
                loadModelCameras();
            }
        }
        
        async function toggleCameraEvacuationZone(modelType, camId, is_evacuation_zone) {
            try {
                await fetch(`/api/model-cameras/${modelType}/${camId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_smoking_zone: is_evacuation_zone })
                });
                showToast(is_evacuation_zone ? 'Camera marked as EVACUATION ZONE' : 'Camera marked as normal area');
            } catch (err) {
                showToast('Failed to update', true);
                loadModelCameras();
            }
        }
        
        async function removeModelCamera(modelType, camId) {
            if (!confirm('Remove this camera from ' + modelType + ' detection?')) return;
            
            try {
                await fetch(`/api/model-cameras/${modelType}/${camId}`, { method: 'DELETE' });
                showToast('Camera removed');
                loadModelCameras();
            } catch (err) {
                showToast('Failed to remove', true);
            }
        }
        
        async function addZone() {
            const name = document.getElementById('zoneName').value.trim();
            const camera_id = parseInt(document.getElementById('zoneCamera').value);
            const is_restricted = document.getElementById('zoneRestricted').checked;
            const description = document.getElementById('zoneDescription').value.trim();
            
            if (!name) {
                showToast('Please enter a zone name', true);
                return;
            }
            
            try {
                const res = await fetch('/api/zones', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, camera_id, is_restricted, description })
                });
                
                if (res.ok) {
                    showToast('Zone added successfully');
                    closeModal('addZoneModal');
                    document.getElementById('zoneName').value = '';
                    document.getElementById('zoneDescription').value = '';
                    document.getElementById('zoneRestricted').checked = false;
                    loadZones();
                } else {
                    showToast('Failed to add zone', true);
                }
            } catch (err) {
                showToast('Failed to add zone', true);
            }
        }
        
        async function toggleZoneRestricted(zoneId, is_restricted) {
            try {
                const res = await fetch(`/api/zones/${zoneId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_restricted })
                });
                
                if (res.ok) {
                    showToast(is_restricted ? 'Zone marked as restricted' : 'Zone marked as normal');
                    loadZones();
                }
            } catch (err) {
                showToast('Failed to update', true);
            }
        }
        
        async function deleteZone(zoneId) {
            if (!confirm('Delete this zone?')) return;
            
            try {
                const res = await fetch(`/api/zones/${zoneId}`, { method: 'DELETE' });
                if (res.ok) {
                    showToast('Zone deleted');
                    loadZones();
                }
            } catch (err) {
                showToast('Failed to delete', true);
            }
        }
        
        function showToast(message, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast active' + (isError ? ' error' : '');
            setTimeout(() => toast.classList.remove('active'), 3000);
        }
        
        // Update camera preview when selection changes
        document.getElementById('cameraSelect')?.addEventListener('change', (e) => {
            document.getElementById('cameraPreview').src = `/video_feed/${e.target.value}`;
        });
    </script>
</body>
</html>
'''


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home() -> str:
    """Intro landing page."""
    return render_template("home.html")


@app.route("/demo")
def demo_welcome() -> str:
    """Welcome page for the demo."""
    return render_template("demo_welcome.html", datetime=datetime)


@app.route("/demo/live")
def demo_hub() -> str:
    """Realtime safety demo hub."""
    return render_template("index.html", datetime=datetime)


@app.route("/config")
def config_page() -> str:
    """RTSP Camera Configuration page."""
    return render_template_string(CONFIG_PAGE_TEMPLATE)


@app.route("/static/known_faces/<path:filename>")
def serve_known_faces(filename: str) -> Response:
    """Serve files from known_faces directory."""
    from flask import send_from_directory
    return send_from_directory(KNOWN_FACES_DIR, filename)


@app.route("/manage")
def management_page() -> str:
    """Person & Zone Management page."""
    return render_template_string(MANAGEMENT_PAGE_TEMPLATE)


@app.route("/dashboard", endpoint="dashboard")
def dashboard_stub() -> str:
    """Dashboard placeholder."""
    return "<h1>UNIface360 Dashboard (RTSP Version)</h1><p>Running with RTSP camera streams.</p>"


@app.route("/request_demo", endpoint="request_demo")
def request_demo_stub() -> str:
    """Request demo page."""
    try:
        return render_template("request_demo.html")
    except Exception:
        return "<h1>Request a Demo</h1><p>RTSP version placeholder.</p>"


@app.route("/events")
def sse_events() -> Response:
    """SSE endpoint for realtime events."""
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(event_stream(), mimetype="text/event-stream", headers=headers)


@app.route("/video_feed/<int:camera_index>")
def video_feed(camera_index: int) -> Response:
    """MJPEG video stream endpoint for RTSP cameras."""
    return Response(
        _generate_camera_stream(camera_index),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


# ---------------------------------------------------------------------------
# Person Management API
# ---------------------------------------------------------------------------

@app.route("/api/persons", methods=["GET"])
def api_get_persons() -> Response:
    """Get all persons."""
    persons = _person_manager.get_all_persons()
    return jsonify({"ok": True, "persons": persons})


@app.route("/api/persons", methods=["POST"])
def api_add_person() -> Response:
    """Add a new person."""
    payload = request.get_json(silent=True, force=True) or {}
    
    person_id = payload.get("id") or payload.get("name", "").replace(" ", "_")
    name = payload.get("name", person_id)
    authorized = payload.get("authorized", True)
    
    if not person_id:
        return jsonify({"ok": False, "error": "Name is required"}), 400
    
    person = _person_manager.add_person(person_id, name, authorized)
    return jsonify({"ok": True, "person": person})


@app.route("/api/persons/<person_id>", methods=["PUT"])
def api_update_person(person_id: str) -> Response:
    """Update a person."""
    payload = request.get_json(silent=True, force=True) or {}
    
    person = _person_manager.update_person(
        person_id,
        name=payload.get("name"),
        authorized=payload.get("authorized")
    )
    
    if person:
        return jsonify({"ok": True, "person": person})
    return jsonify({"ok": False, "error": "Person not found"}), 404


@app.route("/api/persons/<person_id>", methods=["DELETE"])
def api_delete_person(person_id: str) -> Response:
    """Delete a person."""
    if _person_manager.delete_person(person_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Person not found"}), 404


@app.route("/api/persons/<person_id>/photo", methods=["POST"])
def api_add_person_photo(person_id: str) -> Response:
    """Add a photo to a person (from upload or camera capture)."""
    
    # Check if it's a file upload
    if 'photo' in request.files:
        file = request.files['photo']
        if file:
            photo_data = file.read()
            filename = file.filename
            path = _person_manager.add_photo(person_id, photo_data, filename)
            if path:
                return jsonify({"ok": True, "path": path})
            return jsonify({"ok": False, "error": "Person not found"}), 404
    
    # Check if it's base64 data
    payload = request.get_json(silent=True, force=True) or {}
    image_data = payload.get("image")
    
    if image_data:
        # Decode base64
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        photo_data = base64.b64decode(image_data)
        path = _person_manager.add_photo(person_id, photo_data)
        if path:
            return jsonify({"ok": True, "path": path})
        return jsonify({"ok": False, "error": "Person not found"}), 404
    
    return jsonify({"ok": False, "error": "No photo provided"}), 400


@app.route("/api/persons/<person_id>/capture", methods=["POST"])
def api_capture_person_photo(person_id: str) -> Response:
    """Capture a photo from camera for a person."""
    payload = request.get_json(silent=True, force=True) or {}
    camera_id = payload.get("camera_id", 0)
    
    # Get frame from camera
    frame = _get_camera_frame(camera_id, fallback_to_zero=True)
    if frame is None:
        return jsonify({"ok": False, "error": "Camera not available"}), 400
    
    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    photo_data = buffer.tobytes()
    
    path = _person_manager.add_photo(person_id, photo_data)
    if path:
        return jsonify({"ok": True, "path": path})
    return jsonify({"ok": False, "error": "Person not found"}), 404


# Global training progress
_training_progress = {
    "is_training": False,
    "current_person": "",
    "current_photo": "",
    "persons_done": 0,
    "total_persons": 0,
    "photos_done": 0,
    "total_photos": 0,
    "logs": [],
    "percentage": 0
}


@app.route("/api/persons/train", methods=["POST"])
def api_train_faces() -> Response:
    """Train face encodings from all persons' photos."""
    global _training_progress
    
    try:
        import pickle
        
        # Reset progress
        _training_progress = {
            "is_training": True,
            "current_person": "",
            "current_photo": "",
            "persons_done": 0,
            "total_persons": 0,
            "photos_done": 0,
            "total_photos": 0,
            "logs": [],
            "percentage": 0
        }
        
        def log(msg):
            _training_progress["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
            print(f"[TRAIN] {msg}")
        
        log("🚀 Starting face recognition training...")
        
        encodings_dict = {}
        total_faces = 0
        failed_photos = []
        
        # Get all person folders
        person_folders = [f for f in os.listdir(KNOWN_FACES_DIR) 
                         if os.path.isdir(os.path.join(KNOWN_FACES_DIR, f))]
        _training_progress["total_persons"] = len(person_folders)
        
        # Count total photos
        total_photos = 0
        for person_id in person_folders:
            folder_path = os.path.join(KNOWN_FACES_DIR, person_id)
            photos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            total_photos += len(photos)
        _training_progress["total_photos"] = total_photos
        
        log(f"📊 Found {len(person_folders)} persons with {total_photos} photos")
        
        # Iterate through all person folders
        for person_idx, person_id in enumerate(person_folders):
            folder_path = os.path.join(KNOWN_FACES_DIR, person_id)
            _training_progress["current_person"] = person_id
            _training_progress["persons_done"] = person_idx
            
            log(f"👤 Processing: {person_id}")
            
            person_encodings = []
            photos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            for photo_idx, photo in enumerate(photos):
                photo_path = os.path.join(folder_path, photo)
                _training_progress["current_photo"] = photo
                _training_progress["photos_done"] += 1
                _training_progress["percentage"] = int((_training_progress["photos_done"] / total_photos) * 100)
                
                try:
                    # Load image
                    image = face_recognition.load_image_file(photo_path)
                    
                    # Get face encodings
                    face_encs = face_recognition.face_encodings(image)
                    if face_encs:
                        person_encodings.append(face_encs[0])
                        total_faces += 1
                        log(f"   ✓ {photo} - Face detected")
                    else:
                        log(f"   ⚠ {photo} - No face found")
                        failed_photos.append(f"{person_id}/{photo}")
                except Exception as e:
                    log(f"   ✗ {photo} - Error: {str(e)[:50]}")
                    failed_photos.append(f"{person_id}/{photo}")
                    continue
            
            if person_encodings:
                # Average the encodings for better recognition
                avg_encoding = np.mean(person_encodings, axis=0)
                encodings_dict[person_id] = avg_encoding
                log(f"   ✅ {person_id}: {len(person_encodings)} faces encoded")
            else:
                log(f"   ❌ {person_id}: No faces could be encoded!")
        
        # Save encodings
        log("💾 Saving encodings to file...")
        encodings_path = os.path.join(os.path.dirname(__file__), "face_encodings.pkl")
        with open(encodings_path, 'wb') as f:
            pickle.dump(encodings_dict, f)
        
        # Reset loaded faces to force reload
        global _faces_loaded
        _faces_loaded = False
        
        # Update trained status for all persons
        for person_id in encodings_dict.keys():
            _person_manager.update_person(person_id, authorized=_person_manager._persons.get(person_id, {}).get("authorized", True))
            if person_id in _person_manager._persons:
                _person_manager._persons[person_id]["trained"] = True
        _person_manager._save_persons()
        
        _training_progress["percentage"] = 100
        _training_progress["is_training"] = False
        
        summary = f"✅ Training complete! {len(encodings_dict)} persons, {total_faces} faces"
        if failed_photos:
            summary += f", {len(failed_photos)} photos failed"
        log(summary)
        
        return jsonify({
            "ok": True,
            "message": summary,
            "persons_count": len(encodings_dict),
            "total_faces": total_faces,
            "failed_photos": failed_photos,
            "logs": _training_progress["logs"]
        })
    except Exception as e:
        _training_progress["is_training"] = False
        _training_progress["logs"].append(f"[ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e), "logs": _training_progress["logs"]}), 500


@app.route("/api/persons/train/progress", methods=["GET"])
def api_train_progress() -> Response:
    """Get current training progress."""
    return jsonify(_training_progress)


# ---------------------------------------------------------------------------
# Model Camera Configuration API
# ---------------------------------------------------------------------------

@app.route("/api/model-cameras", methods=["GET"])
def api_get_model_cameras() -> Response:
    """Get all model camera configurations."""
    config = _model_camera_manager.get_all_config()
    return jsonify({"ok": True, "config": config})


@app.route("/api/model-cameras/<model_type>", methods=["GET"])
def api_get_model_cameras_by_type(model_type: str) -> Response:
    """Get camera configurations for a specific model."""
    if model_type not in ["unauthorized", "restricted", "ppe", "evacuation"]:
        return jsonify({"ok": False, "error": "Invalid model type"}), 400
    
    cameras = _model_camera_manager.get_model_cameras(model_type)
    return jsonify({"ok": True, "model_type": model_type, "cameras": cameras})


@app.route("/api/model-cameras/<model_type>", methods=["POST"])
def api_add_model_camera(model_type: str) -> Response:
    """Add a camera to a model configuration."""
    if model_type not in ["unauthorized", "restricted", "ppe", "evacuation"]:
        return jsonify({"ok": False, "error": "Invalid model type"}), 400
    
    payload = request.get_json(silent=True, force=True) or {}
    camera_id = payload.get("camera_id")
    name = payload.get("name", "")
    enabled = payload.get("enabled", True)
    is_restricted = payload.get("is_restricted", False)
    
    if camera_id is None:
        return jsonify({"ok": False, "error": "camera_id is required"}), 400
    
    config = _model_camera_manager.add_camera_to_model(
        model_type, int(camera_id), name, enabled, is_restricted
    )
    
    if config:
        return jsonify({"ok": True, "config": config})
    return jsonify({"ok": False, "error": "Failed to add camera"}), 500


@app.route("/api/model-cameras/<model_type>/<int:camera_id>", methods=["PUT"])
def api_update_model_camera(model_type: str, camera_id: int) -> Response:
    """Update a camera configuration in a model."""
    if model_type not in ["unauthorized", "restricted", "ppe", "evacuation"]:
        return jsonify({"ok": False, "error": "Invalid model type"}), 400
    
    payload = request.get_json(silent=True, force=True) or {}
    
    config = _model_camera_manager.update_camera_in_model(
        model_type, camera_id,
        name=payload.get("name"),
        enabled=payload.get("enabled"),
        is_restricted=payload.get("is_restricted"),
        is_smoking_zone=payload.get("is_smoking_zone")
    )
    
    if config:
        return jsonify({"ok": True, "config": config})
    return jsonify({"ok": False, "error": "Camera not found in this model"}), 404


@app.route("/api/model-cameras/<model_type>/<int:camera_id>", methods=["DELETE"])
def api_delete_model_camera(model_type: str, camera_id: int) -> Response:
    """Remove a camera from a model configuration."""
    if model_type not in ["unauthorized", "restricted", "ppe", "evacuation"]:
        return jsonify({"ok": False, "error": "Invalid model type"}), 400
    
    if _model_camera_manager.remove_camera_from_model(model_type, camera_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Camera not found in this model"}), 404


# ---------------------------------------------------------------------------
# Zone Management API (Legacy)
# ---------------------------------------------------------------------------

@app.route("/api/zones", methods=["GET"])
def api_get_zones() -> Response:
    """Get all zones."""
    zones = _zone_manager.get_all_zones()
    return jsonify({"ok": True, "zones": zones})


@app.route("/api/zones", methods=["POST"])
def api_add_zone() -> Response:
    """Add a new zone."""
    payload = request.get_json(silent=True, force=True) or {}
    
    name = payload.get("name")
    camera_id = payload.get("camera_id", 0)
    is_restricted = payload.get("is_restricted", False)
    description = payload.get("description", "")
    
    if not name:
        return jsonify({"ok": False, "error": "Name is required"}), 400
    
    zone = _zone_manager.add_zone(name, camera_id, is_restricted, description)
    return jsonify({"ok": True, "zone": zone})


@app.route("/api/zones/<zone_id>", methods=["PUT"])
def api_update_zone(zone_id: str) -> Response:
    """Update a zone."""
    payload = request.get_json(silent=True, force=True) or {}
    
    zone = _zone_manager.update_zone(
        zone_id,
        name=payload.get("name"),
        camera_id=payload.get("camera_id"),
        is_restricted=payload.get("is_restricted"),
        description=payload.get("description")
    )
    
    if zone:
        return jsonify({"ok": True, "zone": zone})
    return jsonify({"ok": False, "error": "Zone not found"}), 404


@app.route("/api/zones/<zone_id>", methods=["DELETE"])
def api_delete_zone(zone_id: str) -> Response:
    """Delete a zone."""
    if _zone_manager.delete_zone(zone_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Zone not found"}), 404


# ---------------------------------------------------------------------------
# RTSP Camera Configuration API
# ---------------------------------------------------------------------------

@app.route("/api/rtsp/cameras")
def api_rtsp_cameras() -> Response:
    """Get all cameras with their stats."""
    return jsonify(_stream_manager.get_all_stats())


@app.route("/api/rtsp/cameras", methods=["POST"])
def api_rtsp_add_camera() -> Response:
    """Add or update a camera."""
    payload = request.get_json(silent=True, force=True) or {}
    
    cam_id = payload.get("id")
    name = payload.get("name")
    url = payload.get("url")
    enabled = payload.get("enabled", True)
    
    if cam_id is None or not name or not url:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400
    
    success = _stream_manager.add_camera(int(cam_id), url, name, enabled)
    return jsonify({"ok": success})


@app.route("/api/rtsp/cameras/<int:camera_id>", methods=["DELETE"])
def api_rtsp_delete_camera(camera_id: int) -> Response:
    """Delete a camera."""
    print(f"[API DELETE] Received request to delete camera {camera_id}")
    success = _stream_manager.remove_camera(camera_id)
    print(f"[API DELETE] Result: {success}")
    if success:
        return jsonify({"ok": True, "message": f"Camera {camera_id} deleted"})
    else:
        return jsonify({"ok": False, "error": f"Camera {camera_id} not found"}), 404


@app.route("/api/rtsp/cameras/<int:camera_id>/toggle", methods=["POST"])
def api_rtsp_toggle_camera(camera_id: int) -> Response:
    """Enable or disable a camera."""
    payload = request.get_json(silent=True, force=True) or {}
    enabled = payload.get("enabled", True)
    success = _stream_manager.toggle_camera(camera_id, enabled)
    return jsonify({"ok": success})


@app.route("/api/rtsp/cameras/<int:camera_id>/restart", methods=["POST"])
def api_rtsp_restart_camera(camera_id: int) -> Response:
    """Restart a camera stream."""
    success = _stream_manager.restart_camera(camera_id)
    return jsonify({"ok": success})


@app.route("/api/rtsp/stats")
def api_rtsp_stats() -> Response:
    """Get stats for all RTSP streams."""
    return jsonify(_stream_manager.get_all_stats())


# ---------------------------------------------------------------------------
# Camera Auto-Discovery
# ---------------------------------------------------------------------------

def get_local_ip() -> str:
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.1"


def check_rtsp_port(ip: str, port: int = 554, timeout: float = 1.0) -> bool:
    """Check if RTSP port is open on an IP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def test_rtsp_stream(url: str, timeout: float = 3.0) -> bool:
    """Test if an RTSP stream is accessible."""
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
        
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            return ret
        return False
    except Exception:
        return False


def discover_cameras_on_network(
    subnet: str = None,
    username: str = "admin",
    password: str = "Admin123",
    max_workers: int = 50
) -> List[dict]:
    """
    Scan the local network for RTSP cameras.
    Returns list of discovered cameras with their URLs.
    """
    discovered = []
    
    # Get local IP and determine subnet
    local_ip = get_local_ip()
    if subnet is None:
        # Extract subnet from local IP (e.g., 192.168.1.x -> 192.168.1)
        parts = local_ip.split('.')
        subnet = '.'.join(parts[:3])
    
    print(f"[DISCOVERY] Scanning subnet {subnet}.0/24 for RTSP cameras...")
    
    # Common RTSP paths for different camera brands
    rtsp_paths = [
        "/Streaming/Channels/101",  # Hikvision main stream
        "/Streaming/Channels/102",  # Hikvision sub stream
        "/Streaming/Channels/201",  # Hikvision camera 2
        "/Streaming/Channels/301",  # Hikvision camera 3
        "/cam/realmonitor?channel=1&subtype=0",  # Dahua
        "/live/ch00_0",  # Some generic cameras
        "/h264_ulaw.sdp",  # Axis
        "/video1",  # Generic
        "/stream1",  # Generic
        "/1",  # Simple path
        "/",  # Root
    ]
    
    # Scan IPs with RTSP port open
    def scan_ip(ip: str) -> Optional[dict]:
        if check_rtsp_port(ip, 554, timeout=0.5):
            print(f"[DISCOVERY] Found open RTSP port on {ip}")
            
            # Try different RTSP paths
            for path in rtsp_paths:
                url = f"rtsp://{username}:{password}@{ip}:554{path}"
                
                # Quick test - just check if port responds, don't fully validate stream
                # (full validation is slow)
                return {
                    "ip": ip,
                    "port": 554,
                    "url": url,
                    "path": path,
                    "name": f"Camera at {ip}",
                    "tested": False  # Mark as not fully tested
                }
        return None
    
    # Parallel scan
    ips_to_scan = [f"{subnet}.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(scan_ip, ips_to_scan)
        
        for result in results:
            if result:
                discovered.append(result)
    
    print(f"[DISCOVERY] Found {len(discovered)} potential cameras")
    return discovered


def quick_discover_cameras(base_ip: str = None) -> List[dict]:
    """
    Quick discovery focusing on common camera IPs.
    Uses the known camera format from the config.
    """
    settings = load_scan_settings()
    return quick_discover_cameras_with_settings(
        settings.get("ip", "192.168.1.101"),
        settings.get("username", "admin"),
        settings.get("password", ""),
        settings.get("port", 554)
    )


def quick_discover_cameras_with_settings(
    target_ip: str,
    username: str,
    password: str,
    port: int = 554
) -> List[dict]:
    """
    Quick discovery using provided settings.
    First checks the specific IP, then scans the subnet.
    """
    discovered = []
    
    # Extract subnet from target IP
    parts = target_ip.split('.')
    subnet = '.'.join(parts[:3]) if len(parts) >= 3 else "192.168.1"
    target_last_octet = int(parts[3]) if len(parts) >= 4 else 1
    
    # Common Hikvision channels
    channels = [
        ("101", "Channel 1 - Main"),
        ("102", "Channel 1 - Sub"),
        ("201", "Channel 2 - Main"),
        ("202", "Channel 2 - Sub"),
        ("301", "Channel 3 - Main"),
        ("302", "Channel 3 - Sub"),
        ("401", "Channel 4 - Main"),
        ("402", "Channel 4 - Sub"),
        ("501", "Channel 5 - Main"),
        ("601", "Channel 6 - Main"),
        ("701", "Channel 7 - Main"),
        ("801", "Channel 8 - Main"),
    ]
    
    # First, check the specific target IP
    print(f"[DISCOVERY] Checking target IP: {target_ip}:{port}...")
    
    if check_rtsp_port(target_ip, port, timeout=1.0):
        print(f"[DISCOVERY] Found RTSP device at {target_ip}!")
        for channel, channel_name in channels:
            url = f"rtsp://{username}:{password}@{target_ip}:{port}/Streaming/Channels/{channel}"
            discovered.append({
                "ip": target_ip,
                "port": port,
                "channel": channel,
                "url": url,
                "name": f"Camera {target_ip} - {channel_name}",
                "tested": False
            })
    
    # Then scan common IPs in the same subnet
    common_last_octets = [168, 169, 170, 171, 172, 100, 101, 102, 200, 201, 64, 65, 66, 1, 2, 10, 20, 50]
    
    # Add nearby IPs to the target
    for offset in range(-5, 6):
        octet = target_last_octet + offset
        if 1 <= octet <= 254 and octet not in common_last_octets:
            common_last_octets.append(octet)
    
    print(f"[DISCOVERY] Scanning subnet {subnet}.x for more cameras...")
    
    for last_octet in common_last_octets:
        ip = f"{subnet}.{last_octet}"
        if ip == target_ip:  # Skip already checked
            continue
            
        if check_rtsp_port(ip, port, timeout=0.3):
            print(f"[DISCOVERY] Found RTSP device at {ip}")
            for channel, channel_name in channels:
                url = f"rtsp://{username}:{password}@{ip}:{port}/Streaming/Channels/{channel}"
                discovered.append({
                    "ip": ip,
                    "port": port,
                    "channel": channel,
                    "url": url,
                    "name": f"Camera {ip} - {channel_name}",
                    "tested": False
                })
    
    print(f"[DISCOVERY] Quick scan found {len(discovered)} potential streams")
    return discovered


@app.route("/api/rtsp/settings")
def api_rtsp_get_settings() -> Response:
    """Get current scan settings."""
    return jsonify(SCAN_SETTINGS)


@app.route("/api/rtsp/settings", methods=["POST"])
def api_rtsp_save_settings() -> Response:
    """Save scan settings."""
    global SCAN_SETTINGS
    
    payload = request.get_json(silent=True, force=True) or {}
    
    SCAN_SETTINGS["ip"] = payload.get("ip", SCAN_SETTINGS.get("ip", "192.168.1.101"))
    SCAN_SETTINGS["username"] = payload.get("username", SCAN_SETTINGS.get("username", "admin"))
    SCAN_SETTINGS["password"] = payload.get("password", SCAN_SETTINGS.get("password", ""))
    SCAN_SETTINGS["port"] = int(payload.get("port", SCAN_SETTINGS.get("port", 554)))
    
    success = save_scan_settings(SCAN_SETTINGS)
    
    return jsonify({"ok": success, "settings": SCAN_SETTINGS})


@app.route("/api/rtsp/discover", methods=["POST"])
def api_rtsp_discover() -> Response:
    """Discover RTSP cameras on the network."""
    payload = request.get_json(silent=True, force=True) or {}
    
    scan_type = payload.get("scan_type", "quick")  # "quick" or "full"
    
    # Use settings from payload or from saved settings
    ip = payload.get("ip", SCAN_SETTINGS.get("ip", "192.168.1.101"))
    username = payload.get("username", SCAN_SETTINGS.get("username", "admin"))
    password = payload.get("password", SCAN_SETTINGS.get("password", ""))
    port = int(payload.get("port", SCAN_SETTINGS.get("port", 554)))
    
    # Extract subnet from IP
    parts = ip.split('.')
    subnet = '.'.join(parts[:3]) if len(parts) >= 3 else "192.168.1"
    
    try:
        if scan_type == "full":
            cameras = discover_cameras_on_network(subnet, username, password)
        else:
            cameras = quick_discover_cameras_with_settings(ip, username, password, port)
        
        return jsonify({
            "ok": True,
            "cameras": cameras,
            "count": len(cameras)
        })
    except Exception as e:
        print(f"[ERROR] Discovery failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "cameras": []
        }), 500


@app.route("/api/rtsp/test-url", methods=["POST"])
def api_rtsp_test_url() -> Response:
    """Test if an RTSP URL is accessible."""
    payload = request.get_json(silent=True, force=True) or {}
    url = payload.get("url")
    
    if not url:
        return jsonify({"ok": False, "error": "No URL provided"}), 400
    
    try:
        accessible = test_rtsp_stream(url, timeout=5.0)
        return jsonify({
            "ok": True,
            "accessible": accessible,
            "url": url
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "accessible": False,
            "error": str(e)
        })


# ---------------------------------------------------------------------------
# Trigger routes for manual testing
# ---------------------------------------------------------------------------

@app.post("/trigger/evacuation")
def trigger_evacuation() -> Response:
    event = build_evacuation_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/unauthorized")
def trigger_unauthorized() -> Response:
    event = build_unauthorized_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/restricted")
def trigger_restricted() -> Response:
    event = build_restricted_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


@app.post("/trigger/ppe")
def trigger_ppe() -> Response:
    event = build_ppe_event()
    broadcast_event(event)
    return jsonify({"status": "ok", "event": event})


# ---------------------------------------------------------------------------
# API endpoints for detection checks
# ---------------------------------------------------------------------------

@app.post("/api/demo/unauthorized/check")
def api_demo_unauthorized() -> Response:
    """Check if the captured face is known; unknown = unauthorized."""
    _load_known_faces()

    payload = request.get_json(silent=True, force=True) or {}
    
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = None
        for attempt in range(3):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            time.sleep(0.5)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available"}), 400
    else:
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400

    face_locations = face_recognition.face_locations(frame)
    if not face_locations:
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_face"})

    encodings = face_recognition.face_encodings(frame, face_locations)
    if not _known_face_encodings:
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_known_faces"})

    tolerance = 0.4
    best_overall = None

    for enc in encodings:
        matches = face_recognition.compare_faces(_known_face_encodings, enc, tolerance=tolerance)
        name = "Unknown"
        person_id = None
        confidence = 0.0

        if True in matches and len(_known_face_encodings) > 0:
            distances = face_recognition.face_distance(_known_face_encodings, enc)
            best_idx = int(np.argmin(distances))
            if matches[best_idx]:
                folder_name = _known_face_names[best_idx]
                person_id = folder_name  # Store person_id for authorization check
                name = NAME_MAPPING.get(folder_name, folder_name)
                confidence = float(max(0.0, 1.0 - float(distances[best_idx])))

        if best_overall is None or confidence > best_overall["confidence"]:
            best_overall = {"name": name, "person_id": person_id, "confidence": confidence}

    cam_id = camera_index if camera_index is not None else 0
    cam_name = RTSP_CAMERAS.get(cam_id, {}).get("name", f"Camera {cam_id}")

    # Case 1: No match found - Unknown person
    if not best_overall or best_overall["name"] == "Unknown":
        _analytics.add_event(
            event_type="unauthorized",
            camera_id=cam_id,
            camera_name=cam_name,
            details={"message": "Unknown person detected", "reason": "no_match"},
            severity="high",
            snapshot=frame
        )
        return jsonify({"ok": True, "unauthorized": True, "reason": "no_match"})

    # Case 2: Person recognized - check if they are AUTHORIZED
    person_id = best_overall.get("person_id")
    is_authorized = _person_manager.is_authorized(person_id) if person_id else False
    
    if not is_authorized:
        # Person is known but NOT authorized - this is unauthorized access!
        _analytics.add_event(
            event_type="unauthorized",
            camera_id=cam_id,
            camera_name=cam_name,
            details={
                "message": f"Unauthorized person detected: {best_overall['name']}", 
                "reason": "not_authorized",
                "person_name": best_overall["name"],
                "person_id": person_id
            },
            severity="critical",
            snapshot=frame
        )
        return jsonify({
            "ok": True,
            "unauthorized": True,
            "reason": "not_authorized",
            "person_name": best_overall["name"],
            "confidence": best_overall["confidence"],
        })

    # Case 3: Person is recognized AND authorized
    return jsonify({
        "ok": True,
        "unauthorized": False,
        "person_name": best_overall["name"],
        "confidence": best_overall["confidence"],
    })


@app.post("/api/demo/restricted/check")
def api_demo_restricted() -> Response:
    """Check for person presence in restricted zone with face recognition."""
    _load_known_faces()  # Ensure known faces are loaded
    
    payload = request.get_json(silent=True, force=True) or {}
    
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = None
        for attempt in range(3):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            time.sleep(0.5)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available"}), 400
    else:
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400

    face_locations = face_recognition.face_locations(frame)
    intruder = bool(face_locations)
    
    # Identify detected persons using face recognition
    detected_persons = []
    if face_locations and _known_face_encodings:
        encodings = face_recognition.face_encodings(frame, face_locations)
        tolerance = 0.4
        
        for enc in encodings:
            matches = face_recognition.compare_faces(_known_face_encodings, enc, tolerance=tolerance)
            name = "Unknown"
            confidence = 0.0
            
            if True in matches:
                distances = face_recognition.face_distance(_known_face_encodings, enc)
                best_idx = int(np.argmin(distances))
                if matches[best_idx]:
                    folder_name = _known_face_names[best_idx]
                    name = NAME_MAPPING.get(folder_name, folder_name)
                    confidence = float(max(0.0, 1.0 - float(distances[best_idx])))
            
            detected_persons.append({
                "name": name,
                "confidence": round(confidence * 100, 1)
            })
    elif face_locations:
        # Faces detected but no known encodings to compare
        for _ in face_locations:
            detected_persons.append({"name": "Unknown", "confidence": 0})
    
    # Record event if intruder detected
    if intruder:
        cam_id = camera_index if camera_index is not None else 0
        cam_name = RTSP_CAMERAS.get(cam_id, {}).get("name", f"Camera {cam_id}")
        
        # Build person names list for the message
        person_names = [p["name"] for p in detected_persons]
        names_str = ", ".join(person_names) if person_names else "Unknown"
        
        _analytics.add_event(
            event_type="restricted",
            camera_id=cam_id,
            camera_name=cam_name,
            details={
                "message": f"Person detected in restricted area: {names_str}", 
                "persons_count": len(face_locations),
                "persons": detected_persons
            },
            severity="high",
            snapshot=frame
        )
    
    return jsonify({
        "ok": True, 
        "intruder": intruder,
        "persons_count": len(detected_persons),
        "persons": detected_persons
    })


@app.post("/api/demo/ppe/check")
def api_demo_ppe_check() -> Response:
    """PPE (hardhat) check using YOLO model."""
    payload = request.get_json(silent=True, force=True) or {}
    
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = None
        for attempt in range(3):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            time.sleep(0.5)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available"}), 400
    else:
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400
    
    if not _load_ppe_model():
        return jsonify({"ok": False, "error": "model_not_loaded"}), 500
    
    hardhat_detected, confidence = detect_hardhat(frame, confidence_threshold=0.3)
    violation = not hardhat_detected
    
    # Record event if PPE violation detected
    if violation:
        cam_id = camera_index if camera_index is not None else 0
        cam_name = RTSP_CAMERAS.get(cam_id, {}).get("name", f"Camera {cam_id}")
        _analytics.add_event(
            event_type="ppe",
            camera_id=cam_id,
            camera_name=cam_name,
            details={"message": "Missing hardhat detected", "violation_type": "No Hardhat", "confidence": confidence},
            severity="medium",
            snapshot=frame
        )
    
    return jsonify({
        "ok": True,
        "violation": violation,
        "hardhat_detected": hardhat_detected,
        "confidence": confidence
    })


@app.post("/api/demo/evacuation/check")
def api_demo_evacuation_check() -> Response:
    """
    Evacuation System check - Person detection only (head count).
    Fast and reliable for evacuation scenarios.
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = None
        for attempt in range(3):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            time.sleep(0.3)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available"}), 400
    else:
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400
    
    if not _load_tracking_model():
        return jsonify({"ok": False, "error": "model_not_loaded"}), 500
    
    # Use fast person-only detection (no face recognition)
    result = detect_persons_only(frame)
    
    # Store analytics event if people are detected
    if result["person_count"] > 0:
        cam_id = camera_index if camera_index is not None else 0
        cam_name = RTSP_CAMERAS.get(cam_id, {}).get("name", f"Camera {cam_id}")
        
        _analytics.add_event(
            event_type="evacuation",
            camera_id=cam_id,
            camera_name=cam_name,
            details={
                "person_count": result["person_count"]
            },
            severity="info",
            snapshot=None  # No snapshot for fast evacuation check
        )
    
    return jsonify({
        "ok": True,
        "person_count": result["person_count"],
        "boxes": [[int(b) for b in box[:4]] for box in result.get("persons_boxes", [])]
    })


@app.post("/api/demo/live-tracking/check")
def api_demo_live_tracking_check() -> Response:
    """
    Live Tracking System check - Person detection WITH face recognition.
    Records person logs for analytics.
    """
    payload = request.get_json(silent=True, force=True) or {}
    
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = None
        for attempt in range(3):
            frame = _get_camera_frame(camera_index, fallback_to_zero=True)
            if frame is not None:
                break
            time.sleep(0.3)
        
        if frame is None:
            return jsonify({"ok": False, "error": "camera_not_available"}), 400
    else:
        frame = _decode_image_from_request(payload)
        if frame is None:
            return jsonify({"ok": False, "error": "invalid_image"}), 400
    
    if not _load_tracking_model():
        return jsonify({"ok": False, "error": "model_not_loaded"}), 500
    
    # Use full detection with face recognition
    result = detect_and_identify(frame)
    
    cam_id = camera_index if camera_index is not None else 0
    cam_name = RTSP_CAMERAS.get(cam_id, {}).get("name", f"Camera {cam_id}")
    
    # Log each identified person
    for face_detail in result.get("face_details", []):
        if face_detail["name"] != "Unknown":
            # Save snapshot for identified person
            snapshot_path = None
            try:
                filename = f"tracking_{face_detail['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                filepath = os.path.join(SNAPSHOTS_DIR, filename)
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                snapshot_path = f"/static/snapshots/{filename}"
            except:
                pass
            
            add_person_log(
                person_name=face_detail["name"],
                camera_id=cam_id,
                camera_name=cam_name,
                confidence=face_detail["confidence"],
                snapshot_path=snapshot_path
            )
    
    # Store analytics event
    if result["person_count"] > 0:
        _analytics.add_event(
            event_type="live_tracking",
            camera_id=cam_id,
            camera_name=cam_name,
            details={
                "person_count": result["person_count"],
                "identified_persons": result["identified_persons"],
                "unknown_count": result["unknown_count"],
                "face_details": result["face_details"]
            },
            severity="info",
            snapshot=frame if result["identified_persons"] else None
        )
    
    return jsonify({
        "ok": True,
        "person_count": result["person_count"],
        "identified_persons": result["identified_persons"],
        "unknown_count": result["unknown_count"],
        "face_details": result["face_details"],
        "boxes": [[int(b) for b in box[:4]] for box in result.get("persons_boxes", [])]
    })


@app.get("/api/person-logs")
def api_get_person_logs() -> Response:
    """Get person tracking logs for analytics."""
    person_name = request.args.get("person")
    camera_id = request.args.get("camera_id", type=int)
    limit = request.args.get("limit", 100, type=int)
    hours = request.args.get("hours", type=int)
    
    logs = get_person_logs(
        person_name=person_name,
        camera_id=camera_id,
        limit=limit,
        hours=hours
    )
    
    return jsonify({"ok": True, "logs": logs, "count": len(logs)})


@app.get("/api/person-logs/summary")
def api_get_person_summary() -> Response:
    """Get summary of all tracked persons for analytics."""
    summary = get_person_summary()
    return jsonify({"ok": True, "summary": summary})


@app.get("/api/person-logs/<person_name>")
def api_get_person_detail(person_name: str) -> Response:
    """Get detailed logs for a specific person."""
    limit = request.args.get("limit", 50, type=int)
    hours = request.args.get("hours", type=int)
    
    logs = get_person_logs(person_name=person_name, limit=limit, hours=hours)
    summary = get_person_summary().get(person_name, {})
    
    return jsonify({
        "ok": True,
        "person_name": person_name,
        "logs": logs,
        "summary": summary,
        "total_logs": len(logs)
    })


@app.post("/api/demo/evacuation/flag")
def api_demo_evacuation_flag() -> Response:
    """Optional backend hook for evacuation simulation."""
    payload = request.get_json(silent=True, force=True) or {}
    return jsonify({"ok": True, "received": bool(payload)})


# ---------------------------------------------------------------------------
# Email alert endpoints
# ---------------------------------------------------------------------------

@app.post("/api/demo/unauthorized/send-alert-email")
def api_send_unauthorized_email() -> Response:
    """Send email alert for unauthorized person."""
    payload = request.get_json(silent=True, force=True) or {}
    person_info = payload.get("person_info", "Unknown person")
    
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = _get_camera_frame(camera_index, fallback_to_zero=True)
    
    success = send_unauthorized_alert_email(person_info, frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email throttled or failed"}), 429


@app.post("/api/demo/restricted/send-alert-email")
def api_send_restricted_email() -> Response:
    """Send email alert for restricted area breach."""
    payload = request.get_json(silent=True, force=True) or {}
    
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = _get_camera_frame(camera_index, fallback_to_zero=True)
    
    success = send_restricted_area_alert_email(frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email throttled or failed"}), 429


@app.post("/api/demo/ppe/send-alert-email")
def api_send_ppe_email() -> Response:
    """Send email alert for PPE violation."""
    payload = request.get_json(silent=True, force=True) or {}
    
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = _get_camera_frame(camera_index, fallback_to_zero=True)
    
    success = send_ppe_violation_alert_email(frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email throttled or failed"}), 429


@app.post("/api/demo/smoking/send-alert-email")
def api_send_smoking_email() -> Response:
    """Send email alert for smoke/fire detection."""
    payload = request.get_json(silent=True, force=True) or {}
    detection_type = payload.get("detection_type", "smoke")
    
    frame = None
    camera_index = payload.get("camera_index")
    if camera_index is not None:
        frame = _get_camera_frame(camera_index, fallback_to_zero=True)
    
    success = send_smoking_alert_email(detection_type, frame)
    
    if success:
        return jsonify({"ok": True, "message": "Email alert sent successfully"})
    else:
        return jsonify({"ok": False, "message": "Email throttled or failed"}), 429


# ---------------------------------------------------------------------------
# Analytics API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/analytics/events", methods=["GET"])
def api_analytics_events() -> Response:
    """Get filtered detection events."""
    event_type = request.args.get("type")
    camera_id = request.args.get("camera_id")
    limit = int(request.args.get("limit", 100))
    hours = request.args.get("hours")
    
    events = _analytics.get_events(
        event_type=event_type,
        camera_id=int(camera_id) if camera_id else None,
        limit=limit,
        hours=int(hours) if hours else None
    )
    
    return jsonify({"ok": True, "events": events})


@app.route("/api/analytics/events", methods=["POST"])
def api_analytics_add_event() -> Response:
    """Manually add a detection event."""
    payload = request.get_json(silent=True, force=True) or {}
    
    event_type = payload.get("event_type")
    camera_id = payload.get("camera_id", 0)
    camera_name = payload.get("camera_name", f"Camera {camera_id}")
    details = payload.get("details", {})
    severity = payload.get("severity", "medium")
    
    # Get camera frame for snapshot if camera_id provided
    snapshot = None
    if payload.get("capture_snapshot", True):
        snapshot = _get_camera_frame(camera_id, fallback_to_zero=False)
    
    event = _analytics.add_event(
        event_type=event_type,
        camera_id=camera_id,
        camera_name=camera_name,
        details=details,
        severity=severity,
        snapshot=snapshot
    )
    
    return jsonify({"ok": True, "event": event})


@app.route("/api/analytics/stats", methods=["GET"])
def api_analytics_stats() -> Response:
    """Get analytics statistics."""
    hours = int(request.args.get("hours", 24))
    stats = _analytics.get_statistics(hours=hours)
    return jsonify({"ok": True, "stats": stats})


@app.route("/api/analytics/clear", methods=["POST"])
def api_analytics_clear() -> Response:
    """Clear analytics events."""
    payload = request.get_json(silent=True, force=True) or {}
    event_type = payload.get("event_type")
    deleted = _analytics.clear_events(event_type=event_type)
    return jsonify({"ok": True, "deleted": deleted})


# ---------------------------------------------------------------------------
# Analytics Dashboard Template
# ---------------------------------------------------------------------------

ANALYTICS_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNIface360 - Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-hover: #1a1a24;
            --border: #2a2a3a;
            --text: #ffffff;
            --text-muted: #888899;
            --cyan: #00f0ff;
            --magenta: #ff00aa;
            --green: #00ff88;
            --orange: #ff9500;
            --red: #ff4444;
            --purple: #a855f7;
            --blue: #3b82f6;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 10% 10%, rgba(0, 240, 255, 0.05) 0%, transparent 40%),
                radial-gradient(ellipse at 90% 90%, rgba(255, 0, 170, 0.05) 0%, transparent 40%);
        }
        
        /* Header */
        .header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--cyan), var(--magenta));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .back-link {
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s;
        }
        
        .back-link:hover { color: var(--cyan); }
        
        .time-filter {
            display: flex;
            gap: 0.5rem;
        }
        
        .time-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-muted);
            font-family: inherit;
            font-size: 0.85rem;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
        }
        
        .time-btn:hover { border-color: var(--cyan); color: var(--cyan); }
        .time-btn.active { background: var(--cyan); color: var(--bg-dark); border-color: var(--cyan); }
        
        /* Main Container */
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        /* Stats Overview */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }
        
        .stat-card.unauthorized::before { background: linear-gradient(90deg, var(--red), var(--orange)); }
        .stat-card.restricted::before { background: linear-gradient(90deg, var(--orange), #ffcc00); }
        .stat-card.ppe::before { background: linear-gradient(90deg, var(--cyan), var(--blue)); }
        .stat-card.total::before { background: linear-gradient(90deg, var(--magenta), var(--purple)); }
        
        .stat-card:hover {
            border-color: var(--cyan);
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 240, 255, 0.1);
        }
        
        .stat-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        
        .stat-icon {
            font-size: 2.5rem;
            opacity: 0.8;
        }
        
        .stat-badge {
            font-size: 0.7rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-muted);
        }
        
        .stat-value {
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
            margin-bottom: 0.5rem;
        }
        
        .stat-card.unauthorized .stat-value { color: var(--red); }
        .stat-card.restricted .stat-value { color: var(--orange); }
        .stat-card.ppe .stat-value { color: var(--cyan); }
        .stat-card.total .stat-value { color: var(--magenta); }
        
        .stat-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .stat-trend {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
            font-size: 0.8rem;
        }
        
        .trend-up { color: var(--red); }
        .trend-down { color: var(--green); }
        
        /* Charts Section */
        .charts-section {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        @media (max-width: 1200px) {
            .charts-section { grid-template-columns: 1fr; }
        }
        
        .chart-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
        }
        
        .chart-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
        }
        
        /* Camera Stats */
        .camera-stats {
            display: grid;
            gap: 0.75rem;
        }
        
        .camera-stat-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1rem;
            background: var(--bg-hover);
            border-radius: 8px;
            transition: all 0.2s;
        }
        
        .camera-stat-item:hover {
            background: rgba(0, 240, 255, 0.1);
        }
        
        .camera-name {
            font-weight: 500;
            font-size: 0.9rem;
        }
        
        .camera-count {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--cyan);
            background: rgba(0, 240, 255, 0.15);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
        }
        
        /* Events Section */
        .events-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
        }
        
        @media (max-width: 900px) {
            .events-section { grid-template-columns: 1fr; }
        }
        
        .events-panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            max-height: 600px;
            display: flex;
            flex-direction: column;
        }
        
        .panel-header {
            padding: 1rem 1.5rem;
            background: var(--bg-hover);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-title {
            font-size: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .panel-title.unauthorized { color: var(--red); }
        .panel-title.restricted { color: var(--orange); }
        .panel-title.ppe { color: var(--cyan); }
        
        .panel-count {
            font-size: 0.85rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .events-list {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
        }
        
        .event-item {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: var(--bg-dark);
            border-radius: 12px;
            margin-bottom: 0.5rem;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .event-item:hover {
            background: var(--bg-hover);
            transform: scale(1.01);
        }
        
        .event-thumb {
            width: 80px;
            height: 60px;
            background: var(--border);
            border-radius: 8px;
            overflow: hidden;
            flex-shrink: 0;
        }
        
        .event-thumb img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .event-thumb .no-img {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            font-size: 1.5rem;
            color: var(--text-muted);
        }
        
        .event-info {
            flex: 1;
            min-width: 0;
        }
        
        .event-camera {
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .event-details {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }
        
        .event-time {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .event-severity {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            margin-left: 0.5rem;
        }
        
        .severity-low { background: rgba(0, 255, 136, 0.2); color: var(--green); }
        .severity-medium { background: rgba(255, 149, 0, 0.2); color: var(--orange); }
        .severity-high { background: rgba(255, 68, 68, 0.2); color: var(--red); }
        .severity-critical { background: rgba(255, 0, 170, 0.3); color: var(--magenta); }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-dark); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--cyan); }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
        }
        
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }
        
        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            color: var(--text-muted);
        }
        
        .spinner {
            width: 24px;
            height: 24px;
            border: 2px solid var(--border);
            border-top-color: var(--cyan);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 0.75rem;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(5px);
        }
        
        .modal.active { display: flex; }
        
        .modal-content {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            max-width: 800px;
            width: 90%;
            max-height: 90vh;
            overflow: auto;
        }
        
        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-title {
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.2s;
        }
        
        .modal-close:hover { color: var(--red); }
        
        .modal-body {
            padding: 1.5rem;
        }
        
        .modal-image {
            width: 100%;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }
        
        .modal-details {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        
        .detail-item {
            padding: 1rem;
            background: var(--bg-hover);
            border-radius: 8px;
        }
        
        .detail-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        
        .detail-value {
            font-weight: 600;
            font-size: 1rem;
        }
        
        /* Refresh Button */
        .refresh-btn {
            background: transparent;
            border: 1px solid var(--cyan);
            color: var(--cyan);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s;
        }
        
        .refresh-btn:hover {
            background: var(--cyan);
            color: var(--bg-dark);
        }
        
        .refresh-btn.loading .refresh-icon {
            animation: spin 1s linear infinite;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <a href="/demo" class="back-link">← Back to Demo</a>
            <div class="logo">UNIface360 Analytics</div>
        </div>
        <div class="header-right" style="display: flex; gap: 1rem; align-items: center;">
            <div class="time-filter">
                <button class="time-btn" data-hours="1">1H</button>
                <button class="time-btn" data-hours="6">6H</button>
                <button class="time-btn active" data-hours="24">24H</button>
                <button class="time-btn" data-hours="168">7D</button>
            </div>
            <button class="refresh-btn" onclick="refreshAll()">
                <span class="refresh-icon">⟳</span> Refresh
            </button>
        </div>
    </header>
    
    <main class="container">
        <!-- Stats Overview -->
        <div class="stats-grid">
            <a href="/analytics" class="stat-card total" style="text-decoration: none; color: inherit;">
                <div class="stat-header">
                    <span class="stat-icon">📊</span>
                    <span class="stat-badge" id="periodBadge">Last 24h</span>
                </div>
                <div class="stat-value" id="totalEvents">0</div>
                <div class="stat-label">Total Hazards Detected</div>
            </a>
            
            <a href="/analytics/unauthorized" class="stat-card unauthorized" style="text-decoration: none; color: inherit;">
                <div class="stat-header">
                    <span class="stat-icon">🚫</span>
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Click for details →</span>
                </div>
                <div class="stat-value" id="unauthorizedCount">0</div>
                <div class="stat-label">Unauthorized Persons</div>
            </a>
            
            <a href="/analytics/restricted" class="stat-card restricted" style="text-decoration: none; color: inherit;">
                <div class="stat-header">
                    <span class="stat-icon">⚠️</span>
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Click for details →</span>
                </div>
                <div class="stat-value" id="restrictedCount">0</div>
                <div class="stat-label">Restricted Area Breaches</div>
            </a>
            
            <a href="/analytics/ppe" class="stat-card ppe" style="text-decoration: none; color: inherit;">
                <div class="stat-header">
                    <span class="stat-icon">🦺</span>
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Click for details →</span>
                </div>
                <div class="stat-value" id="ppeCount">0</div>
                <div class="stat-label">PPE Violations</div>
            </a>
        </div>
        
        <!-- Quick Navigation -->
        <div style="display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap;">
            <a href="/analytics/unauthorized" style="flex: 1; min-width: 200px; padding: 1rem 1.5rem; background: linear-gradient(135deg, rgba(255, 68, 68, 0.1), rgba(255, 68, 68, 0.05)); border: 1px solid rgba(255, 68, 68, 0.3); border-radius: 12px; text-decoration: none; color: #ff4444; display: flex; align-items: center; gap: 0.75rem; transition: all 0.2s;">
                <span style="font-size: 1.5rem;">🚫</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem;">Unauthorized Dashboard</div>
                    <div style="font-size: 0.8rem; color: #888;">View detailed analytics</div>
                </div>
            </a>
            <a href="/analytics/restricted" style="flex: 1; min-width: 200px; padding: 1rem 1.5rem; background: linear-gradient(135deg, rgba(255, 149, 0, 0.1), rgba(255, 149, 0, 0.05)); border: 1px solid rgba(255, 149, 0, 0.3); border-radius: 12px; text-decoration: none; color: #ff9500; display: flex; align-items: center; gap: 0.75rem; transition: all 0.2s;">
                <span style="font-size: 1.5rem;">⚠️</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem;">Restricted Area Dashboard</div>
                    <div style="font-size: 0.8rem; color: #888;">View detailed analytics</div>
                </div>
            </a>
            <a href="/analytics/ppe" style="flex: 1; min-width: 200px; padding: 1rem 1.5rem; background: linear-gradient(135deg, rgba(0, 240, 255, 0.1), rgba(0, 240, 255, 0.05)); border: 1px solid rgba(0, 240, 255, 0.3); border-radius: 12px; text-decoration: none; color: #00f0ff; display: flex; align-items: center; gap: 0.75rem; transition: all 0.2s;">
                <span style="font-size: 1.5rem;">🦺</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem;">PPE Violations Dashboard</div>
                    <div style="font-size: 0.8rem; color: #888;">View detailed analytics</div>
                </div>
            </a>
            <a href="/analytics/evacuation" style="flex: 1; min-width: 200px; padding: 1rem 1.5rem; background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 0.05)); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; text-decoration: none; color: #10b981; display: flex; align-items: center; gap: 0.75rem; transition: all 0.2s;">
                <span style="font-size: 1.5rem;">🏃</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem;">Evacuation Dashboard</div>
                    <div style="font-size: 0.8rem; color: #888;">View detailed analytics</div>
                </div>
            </a>
        </div>
        
        <!-- Charts Section -->
        <div class="charts-section">
            <div class="chart-card">
                <div class="chart-title">📈 Hazards Over Time</div>
                <div class="chart-container">
                    <canvas id="timelineChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">📹 Hazards by Camera</div>
                <div id="cameraStats" class="camera-stats">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading...
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Events Section -->
        <div class="events-section">
            <!-- Unauthorized Events -->
            <div class="events-panel">
                <div class="panel-header">
                    <div class="panel-title unauthorized">🚫 Unauthorized Person Events</div>
                    <span class="panel-count" id="unauthorizedPanelCount">0 events</span>
                </div>
                <div class="events-list" id="unauthorizedEvents">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading events...
                    </div>
                </div>
            </div>
            
            <!-- Restricted Area Events -->
            <div class="events-panel">
                <div class="panel-header">
                    <div class="panel-title restricted">⚠️ Restricted Area Events</div>
                    <span class="panel-count" id="restrictedPanelCount">0 events</span>
                </div>
                <div class="events-list" id="restrictedEvents">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading events...
                    </div>
                </div>
            </div>
            
            <!-- PPE Events -->
            <div class="events-panel">
                <div class="panel-header">
                    <div class="panel-title ppe">🦺 PPE Violation Events</div>
                    <span class="panel-count" id="ppePanelCount">0 events</span>
                </div>
                <div class="events-list" id="ppeEvents">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading events...
                    </div>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Event Detail Modal -->
    <div class="modal" id="eventModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title" id="modalTitle">Event Details</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <img class="modal-image" id="modalImage" src="" alt="Event snapshot">
                <div class="modal-details" id="modalDetails"></div>
            </div>
        </div>
    </div>
    
    <script>
        let currentHours = 24;
        let timelineChart = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initChart();
            refreshAll();
            
            // Time filter buttons
            document.querySelectorAll('.time-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentHours = parseInt(btn.dataset.hours);
                    updatePeriodBadge();
                    refreshAll();
                });
            });
            
            // Auto-refresh every 30 seconds
            setInterval(refreshAll, 30000);
        });
        
        function updatePeriodBadge() {
            const badge = document.getElementById('periodBadge');
            if (currentHours === 1) badge.textContent = 'Last hour';
            else if (currentHours === 6) badge.textContent = 'Last 6 hours';
            else if (currentHours === 24) badge.textContent = 'Last 24h';
            else if (currentHours === 168) badge.textContent = 'Last 7 days';
            else badge.textContent = `Last ${currentHours}h`;
        }
        
        function initChart() {
            const ctx = document.getElementById('timelineChart').getContext('2d');
            timelineChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Hazards',
                        data: [],
                        borderColor: '#00f0ff',
                        backgroundColor: 'rgba(0, 240, 255, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#00f0ff',
                        pointBorderColor: '#0a0a0f',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(42, 42, 58, 0.5)' },
                            ticks: { color: '#888899', maxRotation: 45 }
                        },
                        y: {
                            grid: { color: 'rgba(42, 42, 58, 0.5)' },
                            ticks: { color: '#888899', stepSize: 1 },
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        async function refreshAll() {
            const btn = document.querySelector('.refresh-btn');
            btn.classList.add('loading');
            
            try {
                await Promise.all([
                    loadStats(),
                    loadEvents('unauthorized'),
                    loadEvents('restricted'),
                    loadEvents('ppe')
                ]);
            } catch (err) {
                console.error('Failed to refresh:', err);
            } finally {
                btn.classList.remove('loading');
            }
        }
        
        async function loadStats() {
            try {
                const response = await fetch(`/api/analytics/stats?hours=${currentHours}`);
                const data = await response.json();
                
                if (data.ok) {
                    const stats = data.stats;
                    
                    // Update stat cards
                    document.getElementById('totalEvents').textContent = stats.total;
                    document.getElementById('unauthorizedCount').textContent = stats.by_type.unauthorized || 0;
                    document.getElementById('restrictedCount').textContent = stats.by_type.restricted || 0;
                    document.getElementById('ppeCount').textContent = stats.by_type.ppe || 0;
                    
                    // Update timeline chart
                    const hours = Object.keys(stats.by_hour).sort();
                    const values = hours.map(h => stats.by_hour[h]);
                    
                    timelineChart.data.labels = hours.map(h => {
                        const date = new Date(h);
                        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    });
                    timelineChart.data.datasets[0].data = values;
                    timelineChart.update();
                    
                    // Update camera stats
                    const cameraStats = document.getElementById('cameraStats');
                    if (Object.keys(stats.by_camera).length === 0) {
                        cameraStats.innerHTML = '<div class="empty-state"><div class="empty-icon">📹</div>No camera data yet</div>';
                    } else {
                        const sorted = Object.entries(stats.by_camera).sort((a, b) => b[1] - a[1]);
                        cameraStats.innerHTML = sorted.map(([name, count]) => `
                            <div class="camera-stat-item">
                                <span class="camera-name">${name}</span>
                                <span class="camera-count">${count}</span>
                            </div>
                        `).join('');
                    }
                }
            } catch (err) {
                console.error('Failed to load stats:', err);
            }
        }
        
        async function loadEvents(type) {
            try {
                const response = await fetch(`/api/analytics/events?type=${type}&hours=${currentHours}&limit=50`);
                const data = await response.json();
                
                const listEl = document.getElementById(`${type}Events`);
                const countEl = document.getElementById(`${type}PanelCount`);
                
                if (data.ok) {
                    const events = data.events;
                    countEl.textContent = `${events.length} events`;
                    
                    if (events.length === 0) {
                        listEl.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-icon">✓</div>
                                No events in this period
                            </div>
                        `;
                    } else {
                        listEl.innerHTML = events.map(event => renderEventItem(event)).join('');
                    }
                }
            } catch (err) {
                console.error(`Failed to load ${type} events:`, err);
            }
        }
        
        function renderEventItem(event) {
            const time = new Date(event.timestamp);
            const timeStr = time.toLocaleString();
            const hasImage = event.snapshot_path;
            const severityClass = `severity-${event.severity}`;
            
            let detailsStr = '';
            if (event.details) {
                // Handle persons array for restricted area
                if (event.details.persons && Array.isArray(event.details.persons)) {
                    const names = event.details.persons.map(p => p.name).join(', ');
                    detailsStr = `Persons: ${names}`;
                }
                else if (event.details.person_name) detailsStr = `Person: ${event.details.person_name}`;
                else if (event.details.violation_type) detailsStr = event.details.violation_type;
                else if (event.details.message) detailsStr = event.details.message;
            }
            
            return `
                <div class="event-item" onclick='showEventDetails(${JSON.stringify(event).replace(/'/g, "&#39;")})'>
                    <div class="event-thumb">
                        ${hasImage ? `<img src="${event.snapshot_path}" alt="Snapshot">` : '<div class="no-img">📷</div>'}
                    </div>
                    <div class="event-info">
                        <div class="event-camera">${event.camera_name}</div>
                        <div class="event-details">${detailsStr || 'Detection event'}</div>
                        <div class="event-time">
                            ${timeStr}
                            <span class="event-severity ${severityClass}">${event.severity}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function showEventDetails(event) {
            const modal = document.getElementById('eventModal');
            const title = document.getElementById('modalTitle');
            const image = document.getElementById('modalImage');
            const details = document.getElementById('modalDetails');
            
            const typeNames = {
                'unauthorized': '🚫 Unauthorized Person',
                'restricted': '⚠️ Restricted Area Breach',
                'ppe': '🦺 PPE Violation'
            };
            
            title.textContent = typeNames[event.event_type] || 'Event Details';
            
            if (event.snapshot_path) {
                image.src = event.snapshot_path;
                image.style.display = 'block';
            } else {
                image.style.display = 'none';
            }
            
            const time = new Date(event.timestamp);
            details.innerHTML = `
                <div class="detail-item">
                    <div class="detail-label">Camera</div>
                    <div class="detail-value">${event.camera_name}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Time</div>
                    <div class="detail-value">${time.toLocaleString()}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Severity</div>
                    <div class="detail-value">${event.severity.toUpperCase()}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Event ID</div>
                    <div class="detail-value">${event.id}</div>
                </div>
                ${event.details ? Object.entries(event.details).map(([key, val]) => {
                    let displayVal = val;
                    if (key === 'persons' && Array.isArray(val)) {
                        displayVal = val.map(p => p.name + ' (' + p.confidence + '%)').join(', ');
                    } else if (typeof val === 'object') {
                        displayVal = JSON.stringify(val);
                    }
                    return `
                    <div class="detail-item">
                        <div class="detail-label">${key.replace(/_/g, ' ')}</div>
                        <div class="detail-value">${displayVal}</div>
                    </div>
                `}).join('') : ''}
            `;
            
            modal.classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('eventModal').classList.remove('active');
        }
        
        // Close modal on click outside
        document.getElementById('eventModal').addEventListener('click', (e) => {
            if (e.target.id === 'eventModal') closeModal();
        });
        
        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
    </script>
</body>
</html>
"""



# ---------------------------------------------------------------------------
# Individual Feature Dashboard Templates
# ---------------------------------------------------------------------------

def generate_feature_dashboard(feature_type: str, feature_config: dict) -> str:
    """Generate a professional dashboard template for a specific feature."""
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNIface360 - {feature_config["title"]} Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-card-alt: #161622;
            --bg-hover: #1a1a24;
            --border: #2a2a3a;
            --text: #ffffff;
            --text-muted: #888899;
            --text-soft: #b0b0c0;
            --accent: {feature_config["color"]};
            --accent-glow: {feature_config["glow"]};
            --accent-bg: {feature_config["bg"]};
            --green: #00ff88;
            --red: #ff4444;
            --orange: #ff9500;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 10% 10%, var(--accent-bg) 0%, transparent 40%),
                radial-gradient(ellipse at 90% 90%, rgba(255, 255, 255, 0.02) 0%, transparent 40%);
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(180deg, var(--bg-card) 0%, rgba(18, 18, 26, 0.95) 100%);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(20px);
        }}
        
        .header-left {{
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }}
        
        .back-link {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
            transition: color 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .back-link:hover {{ color: var(--accent); }}
        
        .logo {{
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .logo-icon {{
            font-size: 1.8rem;
        }}
        
        .feature-badge {{
            padding: 0.35rem 0.75rem;
            background: var(--accent-bg);
            border: 1px solid var(--accent);
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .header-right {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}
        
        .time-filter {{
            display: flex;
            gap: 0.35rem;
            background: var(--bg-hover);
            padding: 0.25rem;
            border-radius: 10px;
        }}
        
        .time-btn {{
            padding: 0.5rem 1rem;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-family: inherit;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
            font-weight: 500;
        }}
        
        .time-btn:hover {{ color: var(--text); background: rgba(255,255,255,0.05); }}
        .time-btn.active {{ background: var(--accent); color: var(--bg-dark); font-weight: 600; }}
        
        .refresh-btn {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s;
        }}
        
        .refresh-btn:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}
        
        /* Main Container */
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* Hero Stats */
        .hero-stats {{
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        @media (max-width: 1200px) {{
            .hero-stats {{ grid-template-columns: 1fr 1fr; }}
        }}
        
        @media (max-width: 768px) {{
            .hero-stats {{ grid-template-columns: 1fr; }}
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
        }}
        
        .stat-card:hover {{
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 10px 40px var(--accent-glow);
        }}
        
        .stat-card.main {{
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--accent-bg) 100%);
            border-color: var(--accent);
        }}
        
        .stat-card.main::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent), transparent);
        }}
        
        .stat-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }}
        
        .stat-icon {{
            font-size: 2rem;
        }}
        
        .stat-badge {{
            font-size: 0.65rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .stat-value {{
            font-size: 3.5rem;
            font-weight: 800;
            line-height: 1;
            margin-bottom: 0.5rem;
            color: var(--accent);
        }}
        
        .stat-card.main .stat-value {{
            font-size: 4.5rem;
        }}
        
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9rem;
            font-weight: 500;
        }}
        
        .stat-trend {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
            font-size: 0.8rem;
            padding: 0.5rem 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            width: fit-content;
        }}
        
        .trend-up {{ color: var(--red); }}
        .trend-down {{ color: var(--green); }}
        .trend-neutral {{ color: var(--text-muted); }}
        
        /* Charts Grid */
        .charts-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        @media (max-width: 1200px) {{
            .charts-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
        }}
        
        .chart-card:hover {{
            border-color: rgba(255,255,255,0.1);
        }}
        
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }}
        
        .chart-title {{
            font-size: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        
        /* Camera Breakdown */
        .camera-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            max-height: 350px;
            overflow-y: auto;
        }}
        
        .camera-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: var(--bg-hover);
            border-radius: 10px;
            transition: all 0.2s;
        }}
        
        .camera-item:hover {{
            background: var(--accent-bg);
            transform: translateX(4px);
        }}
        
        .camera-info {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .camera-icon {{
            width: 40px;
            height: 40px;
            background: var(--accent-bg);
            border: 1px solid var(--accent);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }}
        
        .camera-name {{
            font-weight: 600;
            font-size: 0.9rem;
        }}
        
        .camera-id {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .camera-count {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.1rem;
            color: var(--accent);
            background: var(--accent-bg);
            padding: 0.5rem 1rem;
            border-radius: 8px;
        }}
        
        /* Events Table */
        .events-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }}
        
        .events-header {{
            padding: 1.25rem 1.5rem;
            background: var(--bg-card-alt);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .events-title {{
            font-size: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .events-count {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .events-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .events-table th {{
            text-align: left;
            padding: 1rem 1.5rem;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            background: var(--bg-hover);
            border-bottom: 1px solid var(--border);
            font-weight: 600;
        }}
        
        .events-table td {{
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
            vertical-align: middle;
        }}
        
        .events-table tr:hover {{
            background: var(--bg-hover);
        }}
        
        .events-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .event-snapshot {{
            width: 80px;
            height: 50px;
            background: var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .event-snapshot img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        
        .event-snapshot .no-img {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            font-size: 1.2rem;
            color: var(--text-muted);
        }}
        
        .event-camera {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .event-camera-dot {{
            width: 8px;
            height: 8px;
            background: var(--accent);
            border-radius: 50%;
        }}
        
        .event-time {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-soft);
        }}
        
        .severity-badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .severity-low {{ background: rgba(0, 255, 136, 0.15); color: var(--green); }}
        .severity-medium {{ background: rgba(255, 149, 0, 0.15); color: var(--orange); }}
        .severity-high {{ background: rgba(255, 68, 68, 0.15); color: var(--red); }}
        .severity-critical {{ background: rgba(255, 0, 100, 0.2); color: #ff0066; }}
        
        .event-details {{
            max-width: 300px;
            color: var(--text-soft);
            font-size: 0.85rem;
        }}
        
        .view-btn {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }}
        
        .view-btn:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
        }}
        
        .empty-icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
        
        .empty-text {{
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }}
        
        .empty-subtext {{
            font-size: 0.9rem;
            opacity: 0.7;
        }}
        
        /* Modal */
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(10px);
        }}
        
        .modal.active {{ display: flex; }}
        
        .modal-content {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            max-width: 900px;
            width: 95%;
            max-height: 90vh;
            overflow: auto;
        }}
        
        .modal-header {{
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-card-alt);
        }}
        
        .modal-title {{
            font-size: 1.2rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .modal-close {{
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.2s;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
        }}
        
        .modal-close:hover {{ color: var(--red); background: rgba(255,68,68,0.1); }}
        
        .modal-body {{
            padding: 2rem;
        }}
        
        .modal-image {{
            width: 100%;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}
        
        .modal-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }}
        
        .modal-item {{
            padding: 1rem;
            background: var(--bg-hover);
            border-radius: 10px;
        }}
        
        .modal-label {{
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.35rem;
        }}
        
        .modal-value {{
            font-weight: 600;
            font-size: 1rem;
        }}
        
        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-dark); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}
        
        /* Loading */
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            color: var(--text-muted);
        }}
        
        .spinner {{
            width: 30px;
            height: 30px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 1rem;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Hourly Breakdown */
        .hourly-grid {{
            display: grid;
            grid-template-columns: repeat(24, 1fr);
            gap: 2px;
            margin-top: 1rem;
        }}
        
        .hour-cell {{
            height: 40px;
            background: var(--bg-hover);
            border-radius: 4px;
            position: relative;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .hour-cell:hover {{
            transform: scaleY(1.1);
        }}
        
        .hour-bar {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--accent);
            border-radius: 4px 4px 0 0;
            transition: height 0.3s;
        }}
        
        .hour-label {{
            position: absolute;
            bottom: -20px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.65rem;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <a href="/analytics" class="back-link">← All Dashboards</a>
            <div class="logo">
                <span class="logo-icon">{feature_config["icon"]}</span>
                {feature_config["title"]}
            </div>
            <span class="feature-badge">Live Monitoring</span>
        </div>
        <div class="header-right">
            <div class="time-filter">
                <button class="time-btn" data-hours="1">1H</button>
                <button class="time-btn" data-hours="6">6H</button>
                <button class="time-btn active" data-hours="24">24H</button>
                <button class="time-btn" data-hours="168">7D</button>
            </div>
            <button class="refresh-btn" onclick="refreshData()">
                <span class="refresh-icon">⟳</span> Refresh
            </button>
        </div>
    </header>
    
    <main class="container">
        <!-- Hero Stats -->
        <div class="hero-stats">
            <div class="stat-card main">
                <div class="stat-header">
                    <span class="stat-icon">{feature_config["icon"]}</span>
                    <span class="stat-badge" id="periodBadge">Last 24h</span>
                </div>
                <div class="stat-value" id="totalEvents">0</div>
                <div class="stat-label">Total {feature_config["event_name"]} Events</div>
                <div class="stat-trend" id="trendIndicator">
                    <span>Loading trend...</span>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-icon">📹</span>
                </div>
                <div class="stat-value" id="cameraCount">0</div>
                <div class="stat-label">Cameras Affected</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-icon">⚡</span>
                </div>
                <div class="stat-value" id="peakHour">--</div>
                <div class="stat-label">Peak Hour</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-icon">🔴</span>
                </div>
                <div class="stat-value" id="criticalCount">0</div>
                <div class="stat-label">Critical Alerts</div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">📈 Events Over Time</div>
                </div>
                <div class="chart-container">
                    <canvas id="timelineChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">📹 By Camera</div>
                </div>
                <div class="camera-list" id="cameraList">
                    <div class="loading">
                        <div class="spinner"></div>
                        Loading...
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Events Table -->
        <div class="events-section">
            <div class="events-header">
                <div class="events-title">{feature_config["icon"]} Recent {feature_config["event_name"]} Events</div>
                <div class="events-count" id="eventsCount">0 events</div>
            </div>
            <div id="eventsTableContainer">
                <table class="events-table">
                    <thead>
                        <tr>
                            <th>Snapshot</th>
                            <th>Camera</th>
                            <th>Time</th>
                            <th>Severity</th>
                            <th>Details</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="eventsTableBody">
                        <tr>
                            <td colspan="6">
                                <div class="loading">
                                    <div class="spinner"></div>
                                    Loading events...
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>
    
    <!-- Event Detail Modal -->
    <div class="modal" id="eventModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">
                    <span>{feature_config["icon"]}</span>
                    Event Details
                </div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <img class="modal-image" id="modalImage" src="" alt="Event snapshot">
                <div class="modal-grid" id="modalDetails"></div>
            </div>
        </div>
    </div>
    
    <script>
        const FEATURE_TYPE = '{feature_type}';
        let currentHours = 24;
        let timelineChart = null;
        let allEvents = [];
        
        document.addEventListener('DOMContentLoaded', () => {{
            initChart();
            refreshData();
            
            document.querySelectorAll('.time-btn').forEach(btn => {{
                btn.addEventListener('click', () => {{
                    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentHours = parseInt(btn.dataset.hours);
                    updatePeriodBadge();
                    refreshData();
                }});
            }});
            
            setInterval(refreshData, 30000);
        }});
        
        function updatePeriodBadge() {{
            const badge = document.getElementById('periodBadge');
            if (currentHours === 1) badge.textContent = 'Last hour';
            else if (currentHours === 6) badge.textContent = 'Last 6 hours';
            else if (currentHours === 24) badge.textContent = 'Last 24h';
            else if (currentHours === 168) badge.textContent = 'Last 7 days';
        }}
        
        function initChart() {{
            const ctx = document.getElementById('timelineChart').getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, '{feature_config["color"]}33');
            gradient.addColorStop(1, 'transparent');
            
            timelineChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Events',
                        data: [],
                        borderColor: '{feature_config["color"]}',
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '{feature_config["color"]}',
                        pointBorderColor: '#0a0a0f',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: 'rgba(42, 42, 58, 0.5)', drawBorder: false }},
                            ticks: {{ color: '#888899', maxRotation: 45 }}
                        }},
                        y: {{
                            grid: {{ color: 'rgba(42, 42, 58, 0.5)', drawBorder: false }},
                            ticks: {{ color: '#888899', stepSize: 1 }},
                            beginAtZero: true
                        }}
                    }},
                    interaction: {{
                        intersect: false,
                        mode: 'index'
                    }}
                }}
            }});
        }}
        
        async function refreshData() {{
            const btn = document.querySelector('.refresh-btn');
            btn.classList.add('loading');
            
            try {{
                await Promise.all([loadStats(), loadEvents()]);
            }} catch (err) {{
                console.error('Failed to refresh:', err);
            }} finally {{
                btn.classList.remove('loading');
            }}
        }}
        
        async function loadStats() {{
            try {{
                const response = await fetch(`/api/analytics/stats?hours=${{currentHours}}`);
                const data = await response.json();
                
                if (data.ok) {{
                    const stats = data.stats;
                    const typeCount = stats.by_type[FEATURE_TYPE] || 0;
                    
                    document.getElementById('totalEvents').textContent = typeCount;
                    document.getElementById('cameraCount').textContent = Object.keys(stats.by_camera).length;
                    
                    // Critical count
                    const criticalCount = stats.by_severity.critical || stats.by_severity.high || 0;
                    document.getElementById('criticalCount').textContent = criticalCount;
                    
                    // Peak hour
                    const hours = Object.entries(stats.by_hour);
                    if (hours.length > 0) {{
                        const peak = hours.reduce((a, b) => b[1] > a[1] ? b : a);
                        const peakDate = new Date(peak[0]);
                        document.getElementById('peakHour').textContent = peakDate.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
                    }}
                    
                    // Trend indicator
                    const trend = document.getElementById('trendIndicator');
                    if (typeCount > 5) {{
                        trend.innerHTML = '<span class="trend-up">↑ High activity detected</span>';
                    }} else if (typeCount > 0) {{
                        trend.innerHTML = '<span class="trend-neutral">~ Normal activity</span>';
                    }} else {{
                        trend.innerHTML = '<span class="trend-down">↓ No incidents</span>';
                    }}
                    
                    // Update chart
                    const chartHours = Object.keys(stats.by_hour).sort();
                    const chartValues = chartHours.map(h => stats.by_hour[h]);
                    
                    timelineChart.data.labels = chartHours.map(h => {{
                        const date = new Date(h);
                        return date.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
                    }});
                    timelineChart.data.datasets[0].data = chartValues;
                    timelineChart.update();
                    
                    // Camera breakdown
                    renderCameraList(stats.by_camera);
                }}
            }} catch (err) {{
                console.error('Failed to load stats:', err);
            }}
        }}
        
        function renderCameraList(byCamera) {{
            const list = document.getElementById('cameraList');
            const entries = Object.entries(byCamera).sort((a, b) => b[1] - a[1]);
            
            if (entries.length === 0) {{
                list.innerHTML = '<div class="empty-state"><div class="empty-icon">📹</div><div class="empty-text">No camera data</div></div>';
                return;
            }}
            
            list.innerHTML = entries.map(([name, count]) => `
                <div class="camera-item">
                    <div class="camera-info">
                        <div class="camera-icon">📹</div>
                        <div>
                            <div class="camera-name">${{name}}</div>
                            <div class="camera-id">${{count}} event${{count !== 1 ? 's' : ''}}</div>
                        </div>
                    </div>
                    <div class="camera-count">${{count}}</div>
                </div>
            `).join('');
        }}
        
        async function loadEvents() {{
            try {{
                const response = await fetch(`/api/analytics/events?type=${{FEATURE_TYPE}}&hours=${{currentHours}}&limit=50`);
                const data = await response.json();
                
                if (data.ok) {{
                    allEvents = data.events;
                    document.getElementById('eventsCount').textContent = `${{allEvents.length}} events`;
                    renderEventsTable();
                }}
            }} catch (err) {{
                console.error('Failed to load events:', err);
            }}
        }}
        
        function formatEventDetails(details) {{
            if (!details) return 'Detection event';
            
            let parts = [];
            
            // Handle persons array (for restricted area)
            if (details.persons && Array.isArray(details.persons)) {{
                const names = details.persons.map(p => p.name).join(', ');
                parts.push(`Persons: ${{names}}`);
            }}
            
            // Handle person_name (for unauthorized)
            if (details.person_name) {{
                parts.push(`Person: ${{details.person_name}}`);
            }}
            
            // Handle persons_count
            if (details.persons_count) {{
                parts.push(`Count: ${{details.persons_count}}`);
            }}
            
            // Handle message
            if (details.message && parts.length === 0) {{
                parts.push(details.message);
            }}
            
            return parts.length > 0 ? parts.join(' | ') : 'Detection event';
        }}
        
        function renderEventsTable() {{
            const tbody = document.getElementById('eventsTableBody');
            
            if (allEvents.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <div class="empty-icon">✓</div>
                                <div class="empty-text">No events in this period</div>
                                <div class="empty-subtext">The system is monitoring. Events will appear here when detected.</div>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }}
            
            tbody.innerHTML = allEvents.map((event, idx) => {{
                const time = new Date(event.timestamp);
                const hasImage = event.snapshot_path;
                const details = formatEventDetails(event.details);
                
                return `
                    <tr>
                        <td>
                            <div class="event-snapshot">
                                ${{hasImage ? `<img src="${{event.snapshot_path}}" alt="Snapshot">` : '<div class="no-img">📷</div>'}}
                            </div>
                        </td>
                        <td>
                            <div class="event-camera">
                                <span class="event-camera-dot"></span>
                                ${{event.camera_name}}
                            </div>
                        </td>
                        <td>
                            <div class="event-time">${{time.toLocaleDateString()}}</div>
                            <div class="event-time">${{time.toLocaleTimeString()}}</div>
                        </td>
                        <td>
                            <span class="severity-badge severity-${{event.severity}}">${{event.severity}}</span>
                        </td>
                        <td>
                            <div class="event-details">${{details.substring(0, 50)}}${{details.length > 50 ? '...' : ''}}</div>
                        </td>
                        <td>
                            <button class="view-btn" onclick='showEventModal(${{idx}})'>View</button>
                        </td>
                    </tr>
                `;
            }}).join('');
        }}
        
        function showEventModal(idx) {{
            const event = allEvents[idx];
            if (!event) return;
            
            const modal = document.getElementById('eventModal');
            const image = document.getElementById('modalImage');
            const details = document.getElementById('modalDetails');
            
            if (event.snapshot_path) {{
                image.src = event.snapshot_path;
                image.style.display = 'block';
            }} else {{
                image.style.display = 'none';
            }}
            
            const time = new Date(event.timestamp);
            let detailsHtml = `
                <div class="modal-item">
                    <div class="modal-label">Camera</div>
                    <div class="modal-value">${{event.camera_name}}</div>
                </div>
                <div class="modal-item">
                    <div class="modal-label">Time</div>
                    <div class="modal-value">${{time.toLocaleString()}}</div>
                </div>
                <div class="modal-item">
                    <div class="modal-label">Severity</div>
                    <div class="modal-value">${{event.severity.toUpperCase()}}</div>
                </div>
                <div class="modal-item">
                    <div class="modal-label">Event ID</div>
                    <div class="modal-value">${{event.id}}</div>
                </div>
            `;
            
            if (event.details) {{
                for (const [key, val] of Object.entries(event.details)) {{
                    let displayVal = val;
                    
                    // Format persons array nicely
                    if (key === 'persons' && Array.isArray(val)) {{
                        displayVal = val.map(p => `${{p.name}} (${{p.confidence}}%)`).join(', ');
                    }} else if (typeof val === 'object') {{
                        displayVal = JSON.stringify(val);
                    }}
                    
                    detailsHtml += `
                        <div class="modal-item">
                            <div class="modal-label">${{key.replace(/_/g, ' ')}}</div>
                            <div class="modal-value">${{displayVal}}</div>
                        </div>
                    `;
                }}
            }}
            
            details.innerHTML = detailsHtml;
            modal.classList.add('active');
        }}
        
        function closeModal() {{
            document.getElementById('eventModal').classList.remove('active');
        }}
        
        document.getElementById('eventModal').addEventListener('click', (e) => {{
            if (e.target.id === 'eventModal') closeModal();
        }});
        
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
'''


# Feature configurations
FEATURE_CONFIGS = {
    "unauthorized": {
        "title": "Unauthorized Person",
        "icon": "🚫",
        "event_name": "Unauthorized",
        "color": "#ff4444",
        "glow": "rgba(255, 68, 68, 0.15)",
        "bg": "rgba(255, 68, 68, 0.1)"
    },
    "restricted": {
        "title": "Restricted Area",
        "icon": "⚠️",
        "event_name": "Breach",
        "color": "#ff9500",
        "glow": "rgba(255, 149, 0, 0.15)",
        "bg": "rgba(255, 149, 0, 0.1)"
    },
    "ppe": {
        "title": "PPE Violations",
        "icon": "🦺",
        "event_name": "Violation",
        "color": "#00f0ff",
        "glow": "rgba(0, 240, 255, 0.15)",
        "bg": "rgba(0, 240, 255, 0.1)"
    },
    "evacuation": {
        "title": "Evacuation System",
        "icon": "🏃",
        "event_name": "Tracking",
        "color": "#10b981",
        "glow": "rgba(16, 185, 129, 0.15)",
        "bg": "rgba(16, 185, 129, 0.1)"
    },
    "live_tracking": {
        "title": "Live Tracking",
        "icon": "🎯",
        "event_name": "Identification",
        "color": "#22d3ee",
        "glow": "rgba(34, 211, 238, 0.15)",
        "bg": "rgba(34, 211, 238, 0.1)"
    }
}


# ---------------------------------------------------------------------------
# Page routes for the four dedicated demos
# ---------------------------------------------------------------------------

@app.route("/demo/evacuation")
def demo_evacuation() -> str:
    return render_template("demo_evacuation.html")


@app.route("/demo/unauthorized")
def demo_unauthorized() -> str:
    return render_template("demo_unauthorized.html")


@app.route("/demo/restricted")
def demo_restricted() -> str:
    return render_template("demo_restricted.html")


@app.route("/demo/ppe")
def demo_ppe() -> str:
    return render_template("demo_ppe.html")


@app.route("/demo/live-tracking")
def demo_live_tracking() -> str:
    """Live Tracking System - Face recognition with person logs."""
    return render_template("demo_live_tracking.html")


@app.route("/analytics/live-tracking")
def analytics_live_tracking() -> str:
    """Live Tracking analytics dashboard."""
    config = {
        "title": "Live Tracking",
        "icon": "📍",
        "event_name": "Detection",
        "color": "#00D9A5",
        "glow": "rgba(0, 217, 165, 0.15)",
        "bg": "rgba(0, 217, 165, 0.1)"
    }
    return render_template("feature_analytics.html", feature_type="live_tracking", config=config)


# ---------------------------------------------------------------------------
# Feature Analytics Configuration
# ---------------------------------------------------------------------------

FEATURE_CONFIGS = {
    "unauthorized": {
        "title": "Unauthorized Person",
        "icon": "🚫",
        "event_name": "Unauthorized",
        "color": "#EF4444",
        "glow": "rgba(239, 68, 68, 0.15)",
        "bg": "rgba(239, 68, 68, 0.1)"
    },
    "restricted": {
        "title": "Restricted Area",
        "icon": "⚠️",
        "event_name": "Breach",
        "color": "#F59E0B",
        "glow": "rgba(245, 158, 11, 0.15)",
        "bg": "rgba(245, 158, 11, 0.1)"
    },
    "ppe": {
        "title": "PPE Violations",
        "icon": "🦺",
        "event_name": "Violation",
        "color": "#22C55E",
        "glow": "rgba(34, 197, 94, 0.15)",
        "bg": "rgba(34, 197, 94, 0.1)"
    },
    "evacuation": {
        "title": "Evacuation System",
        "icon": "🚨",
        "event_name": "Alert",
        "color": "#6366F1",
        "glow": "rgba(99, 102, 241, 0.15)",
        "bg": "rgba(99, 102, 241, 0.1)"
    }
}


@app.route("/analytics")
def analytics_main() -> str:
    """Main Analytics Dashboard."""
    return render_template("analytics_dashboard.html")


@app.route("/analytics/unauthorized")
def analytics_unauthorized() -> str:
    """Unauthorized person analytics dashboard."""
    return render_template("feature_analytics.html", feature_type="unauthorized", config=FEATURE_CONFIGS["unauthorized"])


@app.route("/analytics/restricted")
def analytics_restricted() -> str:
    """Restricted area analytics dashboard."""
    return render_template("feature_analytics.html", feature_type="restricted", config=FEATURE_CONFIGS["restricted"])


@app.route("/analytics/ppe")
def analytics_ppe() -> str:
    """PPE violations analytics dashboard."""
    return render_template("feature_analytics.html", feature_type="ppe", config=FEATURE_CONFIGS["ppe"])


@app.route("/analytics/evacuation")
def analytics_evacuation() -> str:
    """Evacuation system analytics dashboard."""
    return render_template("feature_analytics.html", feature_type="evacuation", config=FEATURE_CONFIGS["evacuation"])


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("UNIface360 Realtime Safety Demo - RTSP Version")
    print("=" * 60)
    print()
    print("RTSP Cameras configured:")
    for idx, info in RTSP_CAMERAS.items():
        status = "enabled" if info.get('enabled', True) else "disabled"
        print(f"  Camera {idx}: {info['name']} [{status}]")
        print(f"            {info['url']}")
    print()
    print("Starting web server on http://0.0.0.0:5001/")
    print("Configuration page: http://0.0.0.0:5001/config")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    # Initialize streams before starting
    _stream_manager.initialize()
    
    try:
        app.run(debug=False, host="0.0.0.0", port=5001, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        _stream_manager.stop_all()
        print("Goodbye!")
