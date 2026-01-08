#!/usr/bin/env python3
"""
Test script to check if the specific RTSP cameras are working
"""

import cv2
import time
import threading

# Test camera URLs
CAMERA_STREAMS = {
    "rtsp://admin:UNIface360@192.168.1.168:554/Streaming/Channels/301": "Finance Room",
    "rtsp://admin:UNIface360@192.168.1.168:554/Streaming/Channels/401": "AI Room"
}

def test_camera(rtsp_url, location):
    """Test a single camera connection"""
    print(f"[INFO] Testing camera: {location}")
    print(f"[INFO] URL: {rtsp_url}")
    
    try:
        # Try to connect to the camera
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        if not cap.isOpened():
            print(f"[ERROR] Cannot connect to {location}")
            print(f"[ERROR] URL: {rtsp_url}")
            return False
        
        print(f"[SUCCESS] Connected to {location}")
        
        # Try to read a few frames
        for i in range(5):
            ret, frame = cap.read()
            if not ret:
                print(f"[ERROR] Cannot read frame {i+1} from {location}")
                cap.release()
                return False
            else:
                print(f"[SUCCESS] Frame {i+1} from {location}: {frame.shape}")
                
                # Show the frame
                cv2.putText(frame, f"{location} - Frame {i+1}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow(f"Test - {location}", frame)
                
                # Wait a bit and check for key press
                if cv2.waitKey(1000) & 0xFF == ord('q'):
                    break
        
        cap.release()
        cv2.destroyWindow(f"Test - {location}")
        print(f"[SUCCESS] {location} test completed successfully")
        return True
        
    except Exception as e:
        print(f"[ERROR] Exception testing {location}: {e}")
        return False

def main():
    """Test all cameras"""
    print("=== RTSP Camera Connection Test ===")
    print("Press 'q' in any window to skip to next camera")
    print()
    
    results = {}
    
    for rtsp_url, location in CAMERA_STREAMS.items():
        results[location] = test_camera(rtsp_url, location)
        print("-" * 50)
    
    print("\n=== TEST RESULTS ===")
    for location, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{location}: {status}")
    
    cv2.destroyAllWindows()
    
    # Summary
    successful = sum(results.values())
    total = len(results)
    print(f"\nSummary: {successful}/{total} cameras working")
    
    if successful == total:
        print("🎉 All cameras are working! You can now run main_app.py")
    else:
        print("⚠️  Some cameras failed. Check network connection and credentials.")

if __name__ == "__main__":
    main()
