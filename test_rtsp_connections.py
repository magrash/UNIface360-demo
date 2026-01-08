import cv2
import yaml
import time
import os

# Load config
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()
CAMERA_FLOORS = config["camera_floors"]

# Test each RTSP connection
print("Testing RTSP connections...")
for rtsp_url, floor_name in CAMERA_FLOORS.items():
    print(f"\nTesting connection to {floor_name} ({rtsp_url})")
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print(f"❌ FAILED to connect to {floor_name}")
    else:
        print(f"✅ SUCCESS: Connected to {floor_name}")
        
        # Test reading frames
        ret, frame = cap.read()
        if ret:
            print(f"✅ SUCCESS: Received frame from {floor_name}")
            # Save sample frame
            sample_dir = "camera_tests"
            if not os.path.exists(sample_dir):
                os.makedirs(sample_dir)
            cv2.imwrite(os.path.join(sample_dir, f"{floor_name.replace(' ', '_')}_sample.jpg"), frame)
        else:
            print(f"❌ FAILED to read frame from {floor_name}")
    
    cap.release()
    # Wait a bit before testing next camera
    time.sleep(1)

print("\nRTSP connection test complete")
