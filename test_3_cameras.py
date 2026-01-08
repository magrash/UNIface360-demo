import cv2
import numpy as np

# Initialize the three camera captures
cap1 = cv2.VideoCapture(0)  # First camera (default webcam)
cap2 = cv2.VideoCapture(1)  # Second camera
cap3 = cv2.VideoCapture(2)  # Third camera

# Check if cameras opened successfully
if not (cap1.isOpened() and cap2.isOpened() and cap3.isOpened()):
    print("Error: One or more cameras failed to open")
    exit()

# Set resolution (optional) - adjust as needed
width = 640
height = 480
cap1.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap2.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap3.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap3.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

while True:
    # Read frames from all three cameras
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()
    ret3, frame3 = cap3.read()

    # Check if frames were captured successfully
    if not (ret1 and ret2 and ret3):
        print("Error: Failed to capture frames")
        break

    # Display the frames in separate windows
    cv2.imshow('Camera 1', frame1)
    cv2.imshow('Camera 2', frame2)
    cv2.imshow('Camera 3', frame3)

    # Optional: Combine frames horizontally into one window
    # combined = np.hstack((frame1, frame2, frame3))
    # cv2.imshow('All Cameras', combined)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera captures and close windows
cap1.release()
cap2.release()
cap3.release()
cv2.destroyAllWindows()