import cv2

def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # CAP_DSHOW avoids lag on Windows
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        print(f"[ERROR] Camera {index} could not be opened.")
        return None
    print(f"[INFO] Camera {index} opened successfully.")
    return cap

def main():
    # Open both cameras
    cam0 = open_camera(0)
    cam1 = open_camera(1)

    if cam0 is None or cam1 is None:
        print("Could not initialize both cameras. Exiting.")
        return

    while True:
        ret0, frame0 = cam0.read()
        ret1, frame1 = cam1.read()

        if not ret0:
            print("[ERROR] Failed to read frame from camera 0")
            break
        if not ret1:
            print("[ERROR] Failed to read frame from camera 1")
            break

        cv2.imshow("Camera 0", frame0)
        cv2.imshow("Camera 1", frame1)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam0.release()
    cam1.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()