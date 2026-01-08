#!/usr/bin/env python3
"""
Demo Face Recognition Script
----------------------------
- Uses the same encodings as the attendance system (face_encodings.pkl)
- Opens webcam index 0
- Draws bounding boxes with the recognized name
- Prints the recognized name (and confidence) to the terminal

Press 'q' to quit.
"""

import os
import sys
import pickle
from typing import List, Tuple

import cv2
import face_recognition
import numpy as np


def load_encodings() -> Tuple[List[np.ndarray], List[str]]:
    """
    Load face encodings and labels from face_encodings.pkl
    (same file used by the attendance system).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    enc_path = os.path.join(base_dir, "face_encodings.pkl")

    if not os.path.exists(enc_path):
        print(f"[ERROR] face_encodings.pkl not found at: {enc_path}")
        print("Make sure you run this script from the same folder where encodings are saved.")
        sys.exit(1)

    # Compatibility shim: older encodings may have been created with
    # NumPy 1.x where objects referenced internal modules like
    # "numpy._core" and "numpy._core.multiarray". NumPy 2.x removed
    # those modules, which breaks unpickling. We alias them back to
    # the public numpy module so the pickle can be loaded without
    # downgrading NumPy.
    if "numpy._core" not in sys.modules:  # type: ignore[attr-defined]
        sys.modules["numpy._core"] = np  # type: ignore[assignment]
    try:
        core = np.core  # type: ignore[attr-defined]
        if "numpy._core.multiarray" not in sys.modules:
            sys.modules["numpy._core.multiarray"] = core.multiarray  # type: ignore[attr-defined]
    except Exception:
        # If np.core is not present for some reason, we still have the
        # top-level alias which is enough for many pickles.
        pass

    with open(enc_path, "rb") as f:
        data = pickle.load(f)

    encodings: List[np.ndarray] = []
    names: List[str] = []

    # Preferred format used by the latest tools: {'encodings': [...], 'names': [...]}
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

    if not encodings or not names:
        print("[ERROR] Encodings file is empty or invalid.")
        sys.exit(1)

    print(f"[INFO] Loaded {len(encodings)} known face encodings.")
    return encodings, names


def get_name_mapping() -> dict:
    """
    Mapping from folder names to display names.
    This mirrors the logic used by the Laravel integration.
    """
    return {
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


def open_webcam() -> cv2.VideoCapture:
    """
    Try to open the webcam in a robust way on Windows:
    - Prefer DirectShow backend (CAP_DSHOW) to avoid MSMF errors.
    - Try index 0 then 1.
    """
    preferred_backends = []

    # CAP_DSHOW is more stable than MSMF on many Windows setups
    if hasattr(cv2, "CAP_DSHOW"):
        preferred_backends.append(cv2.CAP_DSHOW)
    # Fallback to default backend (pass no API preference)
    preferred_backends.append(None)

    for backend in preferred_backends:
        for index in (0, 1):
            if backend is None:
                print(f"[INFO] Trying webcam index {index} with default backend...")
                cap = cv2.VideoCapture(index)
            else:
                print(f"[INFO] Trying webcam index {index} with backend {backend}...")
                cap = cv2.VideoCapture(index, backend)

            if cap.isOpened():
                print(f"[INFO] Opened webcam index {index} successfully.")
                return cap

            cap.release()

    print("[ERROR] Could not open any webcam (tried indices 0 and 1 with multiple backends).")
    sys.exit(1)


def main():
    known_face_encodings, known_face_names = load_encodings()
    name_mappings = get_name_mapping()

    # Open webcam robustly
    video_capture = open_webcam()

    print("[INFO] Press 'q' to quit.")

    last_printed_name = None

    try:
        while True:
            ret, frame = video_capture.read()
            if not ret:
                print("[WARN] Failed to grab frame from webcam.")
                break

            # Resize frame for faster processing (optional)
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

            # Convert BGR (OpenCV) to RGB (face_recognition)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Detect faces and encodings
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            face_names = []
            confidences = []

            for face_encoding in face_encodings:
                # Compare face to known encodings
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

                name = "Unknown"
                confidence = 0.0

                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        confidence = 1.0 - face_distances[best_match_index]
                        folder_name = known_face_names[best_match_index]
                        name = name_mappings.get(folder_name, folder_name)

                face_names.append(name)
                confidences.append(confidence)

            # Draw bounding boxes and labels
            for (top, right, bottom, left), name, conf in zip(face_locations, face_names, confidences):
                # Scale coordinates back up since we resized the frame to 0.5
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2

                # Bounding box
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

                # Label background
                label = f"{name}"
                if name != "Unknown":
                    label += f" ({conf:.2f})"

                (text_width, text_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1
                )
                cv2.rectangle(
                    frame,
                    (left, bottom - text_height - baseline - 6),
                    (left + text_width + 6, bottom),
                    color,
                    cv2.FILLED,
                )
                cv2.putText(
                    frame,
                    label,
                    (left + 3, bottom - baseline - 3),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                )

                # Print to terminal (only when it changes to avoid spamming)
                if name != last_printed_name:
                    if name == "Unknown":
                        print("[INFO] Detected: Unknown person")
                    else:
                        print(f"[INFO] Detected: {name} (confidence={conf:.3f})")
                    last_printed_name = name

            # Show the resulting image
            cv2.imshow("Face Recognition Demo", frame)

            # Quit with 'q'
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        video_capture.release()
        cv2.destroyAllWindows()
        print("[INFO] Webcam released, window closed.")


if __name__ == "__main__":
    main()