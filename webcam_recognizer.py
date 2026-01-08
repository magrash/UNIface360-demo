"""webcam_recognizer.py

Open the system webcam, run face recognition using saved encodings (face_encodings.pkl),
draw boxes and names on the live video, optionally save evidence images and log to tracking.db.

Usage:
    python webcam_recognizer.py --camera 0 --tolerance 0.6
"""
import os
import time
import pickle
import argparse
from datetime import datetime

import cv2
import numpy as np
import sqlite3
from concurrent.futures import ThreadPoolExecutor

# Optional torch to check GPU availability
_HAS_TORCH = False
try:
    import torch
    _HAS_TORCH = True
except Exception:
    torch = None

_HAS_FR = False
try:
    import face_recognition
    _HAS_FR = True
except Exception:
    face_recognition = None

def load_encodings(enc_file='face_encodings.pkl'):
    if not os.path.exists(enc_file):
        print(f'Encodings file not found: {enc_file}')
        return {}
    with open(enc_file, 'rb') as f:
        data = pickle.load(f)
    # ensure numpy arrays
    return {k: np.array(v) for k, v in data.items()}

executor = ThreadPoolExecutor(max_workers=2)


def save_and_log(image, name, evidence_dir, db_path):
    try:
        now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        safe_name = name.replace(' ', '_')
        fname = f"{safe_name}_{now}.jpg"
        path = os.path.join(evidence_dir, fname)
        cv2.imwrite(path, image)
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("INSERT INTO logs (name, location, time, image_path) VALUES (?, ?, ?, ?)",
                            (name, 'Webcam', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), path))
                conn.commit()
                conn.close()
            except Exception as e:
                print('DB write failed:', e)
        return path
    except Exception as e:
        print('Failed to save evidence in background:', e)
        return ''


def main(camera_index=0, tolerance=0.6, save_evidence=True, scale=0.5, process_every=2, model='hog'):
    encodings = load_encodings()
    names = list(encodings.keys())
    encs = list(encodings.values())

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print('Failed to open camera', camera_index)
        return

    evidence_dir = os.path.join(os.getcwd(), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)

    print('Starting webcam. Press q to quit.')
    # Print GPU / dlib info
    try:
        import dlib
        has_cuda_attr = hasattr(dlib, 'cuda')
        if has_cuda_attr:
            try:
                num = dlib.cuda.get_num_devices()
            except Exception:
                num = 0
            print(f'dlib version: {dlib.__version__}, dlib.cuda present, devices: {num}')
        else:
            print(f'dlib version: {dlib.__version__}, no dlib.cuda attribute (no CUDA support)')
    except Exception:
        print('dlib not importable; face_recognition may be using a different backend or is missing')
    frame_count = 0
    db_path = 'tracking.db'
    # trackers: id -> {tracker, name, confidence, bbox [x,y,w,h], last_seen}
    trackers = {}
    next_tracker_id = 0
    tracker_timeout = 3.0  # seconds to keep tracker without updates

    def create_tracker():
        # Prefer CSRT for accuracy, fallback to KCF
        try:
            return cv2.TrackerCSRT_create()
        except Exception:
            try:
                return cv2.legacy.TrackerCSRT_create()
            except Exception:
                try:
                    return cv2.TrackerKCF_create()
                except Exception:
                    return cv2.legacy.TrackerKCF_create()

    def iou(boxA, boxB):
        # boxes in [x,y,w,h]
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0]+boxA[2], boxB[0]+boxB[2])
        yB = min(boxA[1]+boxA[3], boxB[1]+boxB[3])
        interW = max(0, xB - xA)
        interH = max(0, yB - yA)
        interArea = interW * interH
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        if boxAArea + boxBArea - interArea == 0:
            return 0.0
        return interArea / float(boxAArea + boxBArea - interArea)
    while True:
        ret, frame = cap.read()
        if not ret:
            print('Frame read failed, retrying...')
            time.sleep(0.1)
            continue
        frame_count += 1
        # Show the frame immediately (we will draw detections later)
        display_frame = frame.copy()

        # Update existing trackers every frame so boxes persist
        remove_ids = []
        for tid, info in list(trackers.items()):
            tr = info['tracker']
            ok, bbox = tr.update(frame)
            if ok:
                x, y, w, h = [int(v) for v in bbox]
                info['bbox'] = [x, y, w, h]
                info['last_seen'] = time.time()
                # draw persistent box and label
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                label = f"{info.get('name','Unknown')} ({info.get('confidence',0.0):.2f})"
                cv2.putText(display_frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)
            else:
                # If tracker fails to update, check timeout later
                if time.time() - info.get('last_seen', 0) > tracker_timeout:
                    remove_ids.append(tid)
        for rid in remove_ids:
            try:
                del trackers[rid]
            except Exception:
                pass

        # Only process every N frames to save CPU
        if frame_count % process_every != 0:
            cv2.imshow('Webcam Recognition', display_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = []
        face_encs = []

        # Resize for faster processing
        if scale and scale < 1.0:
            small_rgb = cv2.resize(rgb, (0, 0), fx=scale, fy=scale)
        else:
            small_rgb = rgb

        if _HAS_FR:
            # detect faces on smaller image using chosen model
            try:
                small_boxes = face_recognition.face_locations(small_rgb, model=model)
            except Exception as e:
                print(f'[webcam_recognizer] face_recognition.face_locations error: {e} - falling back to hog')
                small_boxes = face_recognition.face_locations(small_rgb, model='hog')
            if small_boxes:
                face_encs_small = face_recognition.face_encodings(small_rgb, small_boxes)
                # scale boxes back to original frame coordinates
                for (top, right, bottom, left) in small_boxes:
                    top = int(top / scale)
                    right = int(right / scale)
                    bottom = int(bottom / scale)
                    left = int(left / scale)
                    boxes.append((top, right, bottom, left))
                face_encs = face_encs_small
            else:
                boxes = []
                face_encs = []
        else:
            # fallback: use OpenCV cascade on grayscale scaled image
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if scale and scale < 1.0:
                small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
            else:
                small_gray = gray
            cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
            faces = cascade.detectMultiScale(small_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30,30))
            # convert to (top,right,bottom,left) format and scale up
            for (x, y, w, h) in faces:
                x_orig = int(x / scale)
                y_orig = int(y / scale)
                w_orig = int(w / scale)
                h_orig = int(h / scale)
                boxes.append((y_orig, x_orig + w_orig, y_orig + h_orig, x_orig))
            face_encs = []

        # On detection frames, match detections to existing trackers or create new ones
        for idx, box in enumerate(boxes):
            top, right, bottom, left = box
            x, y, w, h = left, top, right-left, bottom-top
            name = 'Unknown'
            confidence = 0.0

            if _HAS_FR and len(encs) > 0 and idx < len(face_encs):
                enc = face_encs[idx]
                distances = face_recognition.face_distance(encs, enc)
                best_idx = int(np.argmin(distances))
                min_dist = float(distances[best_idx])
                confidence = max(0.0, min(1.0, 1.0 - min_dist))
                matches = face_recognition.compare_faces(encs, enc, tolerance=tolerance)
                if True in matches:
                    match_idx = matches.index(True)
                    name = names[match_idx]

            # Try to find matching existing tracker by IoU
            matched_id = None
            best_iou = 0.0
            for tid, info in trackers.items():
                i = iou(info['bbox'], [x, y, w, h])
                if i > best_iou:
                    best_iou = i
                    matched_id = tid

            if matched_id is not None and best_iou > 0.3:
                # update existing tracker: re-init to reduce drift
                try:
                    tr = create_tracker()
                    tr.init(frame, (x, y, w, h))
                    trackers[matched_id]['tracker'] = tr
                    trackers[matched_id]['name'] = name
                    trackers[matched_id]['confidence'] = confidence
                    trackers[matched_id]['bbox'] = [x, y, w, h]
                    trackers[matched_id]['last_seen'] = time.time()
                except Exception as e:
                    print('Failed to reinit tracker:', e)
            else:
                # create new tracker
                try:
                    tr = create_tracker()
                    tr.init(frame, (x, y, w, h))
                    trackers[next_tracker_id] = {
                        'tracker': tr,
                        'name': name,
                        'confidence': confidence,
                        'bbox': [x, y, w, h],
                        'last_seen': time.time()
                    }
                    # save evidence asynchronously for new faces
                    if save_evidence:
                        try:
                            crop = frame[y:y+h, x:x+w]
                            executor.submit(save_and_log, crop, name, evidence_dir, db_path)
                        except Exception as e:
                            print('Failed to queue evidence save for new face:', e)
                    next_tracker_id += 1
                except Exception as e:
                    print('Failed to create tracker:', e)

        cv2.imshow('Webcam Recognition', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--tolerance', type=float, default=0.6)
    parser.add_argument('--no-save', dest='save', action='store_false')
    parser.add_argument('--scale', type=float, default=0.5, help='Scale factor for faster processing (0.3-1.0)')
    parser.add_argument('--process_every', type=int, default=2, help='Process every N frames')
    parser.add_argument('--model', choices=['hog','cnn'], default='hog', help='face_recognition model to use')
    args = parser.parse_args()
    if _HAS_TORCH:
        print(f"Torch available. CUDA available: {torch.cuda.is_available()}")
    else:
        print('Torch not available')
    main(camera_index=args.camera, tolerance=args.tolerance, save_evidence=args.save, scale=args.scale, process_every=args.process_every, model=args.model)
