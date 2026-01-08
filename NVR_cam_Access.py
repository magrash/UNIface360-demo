# import subprocess
# import cv2
# import numpy as np

# rtsp_url = 'rtsp://admin:Admin123@192.168.1.2:554/Streaming/Channels/101'

# ffmpeg_command = [
#     'ffmpeg',
#     '-i', rtsp_url,
#     '-f', 'rawvideo',
#     '-pix_fmt', 'bgr24',
#     '-'
# ]

# pipe = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, bufsize=10**8)

# while True:
#     raw_frame = pipe.stdout.read(1920*1080*3)  # Adjust for your resolution!
#     if len(raw_frame) != (1920*1080*3):
#         print("Incomplete frame or end of stream.")
#         break

#     frame = np.frombuffer(raw_frame, np.uint8).reshape((1080, 1920, 3))
#     cv2.imshow('Frame', frame)

#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# pipe.stdout.close()
# pipe.wait()
# cv2.destroyAllWindows()


# second attempt---------------------------------------------------------

# import cv2

# # RTSP URL for sub-stream (lower resolution, simpler decoding)
# rtsp_url = "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/102?tcp"

# # Create OpenCV VideoCapture object
# cap = cv2.VideoCapture(rtsp_url)

# if not cap.isOpened():
#     print("Failed to open RTSP stream.")
# else:
#     print("RTSP stream opened successfully.")
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             print("Failed to read frame from stream.")
#             break

#         # Show the video frame
#         cv2.imshow("NVR Sub-stream (Channel 102)", frame)

#         # Press 'q' to exit
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

# # Clean up
# cap.release()
# cv2.destroyAllWindows()


# Third attempt---------------------------------------------------------


# import cv2

# # Replace with your actual RTSP URL
# rtsp_url = "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/101"

# # Create the VideoCapture object
# cap = cv2.VideoCapture(rtsp_url)

# # Check if the stream opened successfully
# if not cap.isOpened():
#     print("Failed to open RTSP stream.")
# else:
#     print("Stream opened successfully.")
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             print("Failed to read frame.")
#             break

#         # Display the resulting frame
#         cv2.imshow("RTSP Stream", frame)

#         # Break the loop on 'q' key press
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

# # Release the VideoCapture object and close the window
# cap.release()
# cv2.destroyAllWindows()




# 7 cams stream put there is delay of 20-40 sec---------------------------------------------------------
# import cv2
# import numpy as np

# # RTSP URLs for the 7 channels
# rtsp_urls = [
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/102",  # Camera 1
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/202",  # Camera 2
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/302",  # Camera 3
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/402",  # Camera 4
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/502",  # Camera 5
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/602",  # Camera 6
#     "rtsp://admin:Admin123@192.168.0.101:554/Streaming/Channels/702"   # Camera 7
# ]

# # Create VideoCapture objects for each stream
# caps = [cv2.VideoCapture(url) for url in rtsp_urls]

# # Desired resolution for each small stream (you can tweak)
# frame_width, frame_height = 320, 240

# while True:
#     frames = []

#     for idx, cap in enumerate(caps):
#         ret, frame = cap.read()
#         if not ret:
#             # Use a blank image as a placeholder
#             frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
#             cv2.putText(frame, f"Channel {idx+1} - No Signal", (10, frame_height//2),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
#         else:
#             # Resize the frame for mosaic layout
#             frame = cv2.resize(frame, (frame_width, frame_height))
#         frames.append(frame)

#     # Create the grid layout (3x3 for 7 cameras + 2 empty slots)
#     row1 = np.hstack(frames[0:3])
#     row2 = np.hstack(frames[3:6])
    
#     # For row3, only camera 7 + 2 black frames
#     black_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
#     row3 = np.hstack([frames[6], black_frame, black_frame])

#     # Stack the rows vertically
#     mosaic = np.vstack([row1, row2, row3])

#     cv2.imshow("Multi-Camera View", mosaic)

#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# # Release resources
# for cap in caps:
#     cap.release()
# cv2.destroyAllWindows()



# 7 cam stream to avoid delay---------------------------------------------------------
import cv2
import numpy as np
import threading

# RTSP URLs for each channel's sub-stream (more lightweight)
rtsp_urls = [
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/102",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/202",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/302",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/402",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/502",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/602",
    "rtsp://admin:Admin123@192.168.0.103:554/Streaming/Channels/702"
]

# Desired frame size for each camera in the mosaic
frame_width, frame_height = 320, 240

# Shared dictionary to store the latest frame of each camera
frames_dict = {}
lock = threading.Lock()

def camera_thread(rtsp_url, cam_idx):
    global frames_dict
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"[!] Failed to open stream for camera {cam_idx}")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
            cv2.putText(frame, f"Cam {cam_idx} - No Signal", (10, frame_height//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            frame = cv2.resize(frame, (frame_width, frame_height))

        # Update the shared dictionary
        with lock:
            frames_dict[cam_idx] = frame

    cap.release()

# Start threads for each camera
for idx, url in enumerate(rtsp_urls):
    t = threading.Thread(target=camera_thread, args=(url, idx))
    t.daemon = True
    t.start()

# Main loop to display the mosaic
while True:
    # Prepare frames list with black placeholders initially
    frames = [np.zeros((frame_height, frame_width, 3), dtype=np.uint8) for _ in range(9)]

    # Fill in the frames we have
    with lock:
        for idx, frame in frames_dict.items():
            frames[idx] = frame

    # Arrange frames into a 3x3 grid (two black placeholders)
    row1 = np.hstack(frames[0:3])
    row2 = np.hstack(frames[3:6])
    row3 = np.hstack([frames[6], frames[7] if len(frames) > 7 else frames[0]*0, frames[8] if len(frames) > 8 else frames[0]*0])

    # Stack rows vertically
    mosaic = np.vstack([row1, row2, row3])

    cv2.imshow("Multi-Camera Mosaic (Threaded)", mosaic)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()