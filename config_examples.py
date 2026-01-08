# config_examples.py
# 
# This file contains example configurations for different scenarios.
# Copy any of these configurations to your config.py file to test different setups.

# === Example 1: Single Camera Testing ===
SINGLE_CAMERA = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room"
}

# === Example 2: Two Cameras (2x2 Grid) ===
TWO_CAMERAS = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room"
}

# === Example 3: Four Cameras (2x2 Grid) ===
FOUR_CAMERAS = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/102": "Finance Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/502": "Corridor"
}

# === Example 4: Six Cameras (3x2 Grid) ===
SIX_CAMERAS = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/102": "Finance Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/302": "Outdoor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/502": "Corridor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/602": "Reception"
}

# === Example 5: All Seven Cameras (3x3 Grid) ===
ALL_CAMERAS = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/102": "Finance Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/302": "Outdoor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/502": "Corridor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/602": "Reception",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/702": "Ops Room"
}

# === Example 6: Webcam Testing ===
WEBCAM_ONLY = {
    0: "Primary Webcam"
}

# === Example 7: Mixed Webcam and RTSP ===
MIXED_CAMERAS = {
    0: "Webcam",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room"
}

# === Example 8: Large Setup (12 Cameras - 4x3 Grid) ===
LARGE_SETUP = {
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/102": "Finance Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/202": "AI Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/302": "Outdoor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/402": "Meeting Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/502": "Corridor",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/602": "Reception",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/702": "Ops Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/802": "Storage Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/902": "Break Room",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/1002": "Parking",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/1102": "Main Entrance",
    "rtsp://admin:Admin123@192.168.0.100:554/Streaming/Channels/1202": "Back Exit"
}

# === How to Use These Examples ===
"""
To use any of these configurations:

1. Open your config.py file
2. Replace the CAMERA_STREAMS dictionary with one of the examples above
3. Save the file
4. Run the main application

Example:
# In config.py, replace:
CAMERA_STREAMS = { ... }

# With:
CAMERA_STREAMS = {
    0: "Webcam"
}

The application will automatically:
- Calculate the optimal grid layout
- Adjust the display window size
- Handle camera connections and reconnections
- Show connection status for each camera
"""
