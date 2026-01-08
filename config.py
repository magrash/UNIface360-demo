# config.py

# ... (all your existing settings) ...

# === Processing Configuration ===
# Set to True to process only a vertical slice of the frame
CROP_FRAME = True 
# Define the start and end of the slice as a percentage of the frame's width
# (0.33, 0.66) corresponds to the middle third.
CROP_HORIZONTAL_REGION_PERCENT = (0.33, 0.66)


# === System Configuration ===
# Set to False to run in "headless" mode without displaying camera windows
SHOW_WINDOWS = True 
# Model for face detection: 'hog' is faster, 'cnn' is more accurate but CPU-intensive
FACE_DETECTION_MODEL = "hog" 
# Process every Nth frame from the central queue to save CPU (increased for RTSP)
PROCESS_EVERY_N_FRAMES = 15  # Increased from 5 to 15 for better performance
# Time in seconds to wait before logging the same person again
DEBOUNCE_SECONDS = 10 
# Time in seconds for a camera thread to wait before attempting to reconnect
RECONNECT_DELAY_SECONDS = 5

# === File & Directory Paths ===
ENCODINGS_FILE = "face_encodings.pkl"
DB_FILE = "tracking.db"
EVIDENCE_DIR = "evidence"

# === Camera Configuration ===
# Dictionary mapping RTSP URLs to their location names
# The application will automatically adapt to any number of cameras configured here.
# Grid layout is calculated automatically based on the number of cameras.
# 
# Examples:
# - 1 camera: 1x1 grid
# - 2-4 cameras: 2x2 grid  
# - 5-6 cameras: 3x2 grid
# - 7-9 cameras: 3x3 grid
# - 10-12 cameras: 4x3 grid
# - etc.
#
# To add more cameras, simply add more entries to this dictionary.
# To remove cameras, comment out or delete the entries.
# To disable all cameras for testing, set CAMERA_STREAMS = {}

CAMERA_STREAMS = {
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/102": "Finance Room",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/302": "Outdoor",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/502": "Corridor",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/602": "Reception",
  "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/702": "Ops Room"
}

# Example configurations for different scenarios:
#
# # Single camera testing:
# CAMERA_STREAMS = {
#     "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room"
# }
#
# # Two cameras:
# CAMERA_STREAMS = {
#     "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
#     "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room"
# }
#
# # Webcam testing (replace 0 with your webcam index):
# CAMERA_STREAMS = {
#     0: "Webcam"
# }