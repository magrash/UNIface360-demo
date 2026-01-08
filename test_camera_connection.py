import cv2
import sqlite3
import os
import yaml

# Load config
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()

# Get RTSP URLs and floor names
CAMERA_FLOORS = config["camera_floors"]
rtsp_urls = list(CAMERA_FLOORS.keys())
floor_names = list(CAMERA_FLOORS.values())

print(f"Configured cameras: {len(rtsp_urls)}")
for i, (url, floor) in enumerate(zip(rtsp_urls, floor_names)):
    print(f"Camera {i+1}: {floor} - {url}")
    # Try to connect to camera
    cap = cv2.VideoCapture(url)
    if cap.isOpened():
        print(f"  ✓ Connection successful!")
        ret, frame = cap.read()
        if ret:
            print(f"  ✓ Frame received: {frame.shape}")
        else:
            print(f"  ✗ No frame received")
        cap.release()
    else:
        print(f"  ✗ Failed to connect")

# Check database status
DB_FILE = config["database"]
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM logs")
log_count = cursor.fetchone()[0]
print(f"\nDatabase contains {log_count} log entries")

if log_count > 0:
    cursor.execute("SELECT name, time, floor, image_path FROM logs ORDER BY id DESC LIMIT 5")
    print("\nLast 5 entries:")
    for row in cursor.fetchall():
        print(f"  {row[0]} at {row[2]} on {row[1]}")

conn.close()

# Check for evidence files
EVIDENCE_DIR = config["evidence_dir"]
if os.path.exists(EVIDENCE_DIR):
    evidence_files = os.listdir(EVIDENCE_DIR)
    print(f"\nEvidence directory contains {len(evidence_files)} files")
    if len(evidence_files) > 0:
        print("Last 5 evidence files:")
        for file in sorted(evidence_files)[-5:]:
            print(f"  {file}")
else:
    print("\nEvidence directory doesn't exist")
