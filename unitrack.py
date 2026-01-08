from flask import Flask, render_template, request, jsonify
import base64
import io
import sys
import os
import pickle
import cv2
import numpy as np
import yaml
# Optional face_recognition: try to import, set a flag so detection can fall back
_HAS_FACE_RECOGNITION = False
try:
    import face_recognition
    _HAS_FACE_RECOGNITION = True
except Exception:
    face_recognition = None

import sqlite3
from datetime import datetime

# Create Flask app
app = Flask(__name__)

# helper to get face cascade
_face_cascade = None
def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if os.path.exists(cascade_path):
            _face_cascade = cv2.CascadeClassifier(cascade_path)
        else:
            _face_cascade = None
    return _face_cascade

# Load config
def load_config():
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
            print('[unitrack] Loaded config.yaml')
            return config
    except Exception as e:
        print(f'[unitrack] Warning: Could not load config.yaml: {e}')
        return {
            'encodings_file': 'face_encodings.pkl',
            'database': 'tracking.db',
            'evidence_dir': 'evidence',
            'debounce_seconds': 5
        }

config = load_config()

# Load known face encodings
def load_known_faces():
    enc_file = config['encodings_file']
    if not os.path.exists(enc_file):
        print(f'[unitrack] Warning: Encodings file not found: {enc_file}')
        return {}
    
    try:
        with open(enc_file, 'rb') as f:
            data = pickle.load(f)
        print(f'[unitrack] Loaded {len(data)} known face encodings')
        print(f'[unitrack] Known names: {", ".join(data.keys())}')
        return data
    except Exception as e:
        print(f'[unitrack] Error loading encodings: {e}')
        return {}

known_faces = load_known_faces()

# Initialize OpenCV face cascade as fallback
cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(cascade_path) if os.path.exists(cascade_path) else None

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


# Load known face encodings (from config.yaml if present, else fallback to face_encodings.pkl)
def load_known_encodings():
    enc_file = 'face_encodings.pkl'
    # try config.yaml
    try:
        if os.path.exists('config.yaml'):
            with open('config.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
            if cfg and isinstance(cfg, dict) and cfg.get('encodings_file'):
                enc_file = cfg.get('encodings_file')
    except Exception:
        pass

    if not os.path.exists(enc_file):
        print(f"[unitrack] Encodings file not found: {enc_file}. No known faces loaded.")
        return {}

    try:
        with open(enc_file, 'rb') as f:
            data = pickle.load(f)
        # ensure values are numpy arrays
        cleaned = {k: np.array(v) for k, v in data.items()}
        print(f"[unitrack] Loaded {len(cleaned)} known face encodings from {enc_file}")
        return cleaned
    except Exception as e:
        print(f"[unitrack] Failed to load encodings file {enc_file}: {e}", file=sys.stderr)
        return {}


# Load at import time; this can be reloaded later if desired
known_faces = load_known_encodings()


@app.route('/')
def index():
    return render_template('unitrack.html')


@app.route('/detect', methods=['POST'])
def detect():
    # Expect form field 'image' containing a data URL (data:image/png;base64,...)
    data = request.form.get('image') or request.files.get('image')
    if not data:
        return jsonify({'success': False, 'error': 'no image data provided'}), 400

    # If the client sent a data URL string
    if isinstance(data, str) and data.startswith('data:'):
        try:
            header, encoded = data.split(',', 1)
        except ValueError:
            return jsonify({'success': False, 'error': 'invalid data url'}), 400
        try:
            img_bytes = base64.b64decode(encoded)
        except Exception as e:
            print('base64 decode error:', e, file=sys.stderr)
            return jsonify({'success': False, 'error': 'base64 decode failed'}), 400
    else:
        # Could be a FileStorage from a file input
        try:
            img_bytes = data.read()
        except Exception:
            return jsonify({'success': False, 'error': 'unsupported image payload'}), 400

    # Convert bytes to OpenCV image
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if cv_img is None:
            raise ValueError('Could not decode image')
        print(f"[unitrack] Received image: shape={cv_img.shape}")

        # Detect faces using face_recognition if available, otherwise OpenCV
        detections = []
        
        if _HAS_FACE_RECOGNITION:
            # Convert BGR to RGB for face_recognition
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            face_locations = face_recognition.face_locations(rgb, model='hog')
            if not face_locations:
                print('[unitrack] No faces found')
                return jsonify({'success': True, 'detections': []})

            face_encodings = face_recognition.face_encodings(rgb, face_locations)

            for face_encoding, location in zip(face_encodings, face_locations):
                name = 'Unknown'
                confidence = 0.0

                if len(known_faces) > 0:
                    encodings_list = list(known_faces.values())
                    names_list = list(known_faces.keys())
                    distances = face_recognition.face_distance(encodings_list, face_encoding)
                    # lower distance = more similar. Convert to confidence [0,1]
                    best_idx = int(np.argmin(distances))
                    min_dist = float(distances[best_idx])
                    # simple confidence transform
                    confidence = max(0.0, min(1.0, 1.0 - min_dist))
                    matches = face_recognition.compare_faces(encodings_list, face_encoding, tolerance=0.6)
                    if True in matches:
                        match_idx = matches.index(True)
                        name = names_list[match_idx]
                
                # Convert face_recognition bbox (top,right,bottom,left) to OpenCV style (x,y,w,h)
                top, right, bottom, left = location
                bbox = [int(left), int(top), int(right-left), int(bottom-top)]
                detections.append({'name': name, 'confidence': confidence, 'bbox': bbox})
        else:
            # Fallback to OpenCV face detection
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            cascade = get_face_cascade()
            if cascade is None:
                print('[unitrack] No face cascade available for OpenCV fallback')
            else:
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                evidence_dir = os.path.join(os.getcwd(), config.get('evidence_dir', 'evidence'))
                os.makedirs(evidence_dir, exist_ok=True)

                for (x, y, w, h) in faces:
                    name = 'Unknown'
                    confidence = 0.5  # placeholder confidence for OpenCV detection
                    bbox = [int(x), int(y), int(w), int(h)]

                    # Save face crop
                    try:
                        face_img = cv_img[y:y+h, x:x+w]
                        time_now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                        safe_name = name.replace(' ', '_')
                        filename = f"{safe_name}_{time_now}.jpg"
                        image_path = os.path.join(evidence_dir, filename)
                        cv2.imwrite(image_path, face_img)
                    except Exception as e:
                        print(f"[unitrack] Failed to save evidence crop: {e}")
                        image_path = ''

                    detections.append({'name': name, 'confidence': confidence, 'bbox': bbox, 'image_path': image_path})
                    print(f"[unitrack] Detected {name} at {bbox} confidence={confidence:.3f} image={image_path}")

                    # Insert into tracking.db if exists
                    try:
                        db_path = config.get('database', 'tracking.db')
                        if os.path.exists(db_path):
                            conn = sqlite3.connect(db_path)
                            cur = conn.cursor()
                            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            cur.execute("INSERT INTO logs (name, location, time, image_path) VALUES (?, ?, ?, ?)",
                                        (name, 'Unitrack', now_str, image_path))
                            conn.commit()
                            conn.close()
                    except Exception as e:
                        print(f"[unitrack] Failed to write to tracking.db: {e}")

        return jsonify({'success': True, 'detections': detections})
    except Exception as e:
        print('[unitrack] Error processing image:', e, file=sys.stderr)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reload_encodings', methods=['POST'])
def reload_encodings():
    global known_faces
    known_faces = load_known_encodings()
    return jsonify({'success': True, 'loaded': len(known_faces)})


if __name__ == '__main__':
    # Allow running with optional HTTPS (useful for camera access from remote devices)
    import argparse

    parser = argparse.ArgumentParser(description='Run unitrack Flask app')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind (default: 5000)')
    parser.add_argument('--ssl', action='store_true', help='Enable HTTPS (adhoc self-signed cert)')
    args = parser.parse_args()

    if args.ssl:
        print(f"Starting unitrack on https://{args.host}:{args.port} (self-signed cert — accept browser warning)")
        app.run(host=args.host, port=args.port, debug=True, ssl_context='adhoc')
    else:
        print(f"Starting unitrack on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=True)
