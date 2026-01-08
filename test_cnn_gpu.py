import os
import time
import sys
try:
    import face_recognition
except Exception as e:
    print('face_recognition not importable:', e)
    sys.exit(1)
try:
    import cv2
except Exception:
    cv2 = None
try:
    import torch
    has_torch = True
except Exception:
    torch = None
    has_torch = False

def find_sample_image():
    # search common folders
    candidates = []
    for root in ['test_images', 'known_faces', '.']:
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            for f in filenames:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    candidates.append(os.path.join(dirpath, f))
    return candidates[0] if candidates else None

img_path = find_sample_image()
if not img_path:
    print('No sample image found in test_images or known_faces. Please add one.')
    sys.exit(1)

print('Using sample image:', img_path)
if cv2:
    img = cv2.imread(img_path)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
else:
    # fallback to PIL
    from PIL import Image
    img = Image.open(img_path)
    rgb = face_recognition.load_image_file(img_path)

print('torch available:', has_torch)
if has_torch:
    try:
        print('torch cuda available:', torch.cuda.is_available())
    except Exception as e:
        print('torch.cuda check failed:', e)

def run_model(model_name):
    print('\nRunning model:', model_name)
    t0 = time.time()
    try:
        locs = face_recognition.face_locations(rgb, model=model_name)
        elapsed = time.time() - t0
        print(f'{model_name} completed in {elapsed:.3f}s, faces found: {len(locs)}')
        return True, elapsed
    except Exception as e:
        print(f'{model_name} failed:', e)
        return False, None

run_model('hog')
run_model('cnn')

print('\nDone')
