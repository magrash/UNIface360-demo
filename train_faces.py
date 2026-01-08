import face_recognition
import os
import pickle

# Function to compute encodings from subfolders
def compute_encodings(image_folder):
    encodings_dict = {}
    for person_folder in os.listdir(image_folder):
        person_path = os.path.join(image_folder, person_folder)
        if os.path.isdir(person_path):  # Ensure it's a directory
            for filename in os.listdir(person_path):
                image_path = os.path.join(person_path, filename)
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    name = person_folder  # Use folder name as identity
                    if name not in encodings_dict:
                        encodings_dict[name] = []
                    encodings_dict[name].append(encodings[0])
                    print(f"Trained face for {name} from {filename}")
                else:
                    print(f"No face detected in {filename} for {name}, skipping.")
    # Average encodings for each person (optional, for better accuracy)
    for name in encodings_dict:
        if len(encodings_dict[name]) > 1:
            encodings_dict[name] = sum(encodings_dict[name]) / len(encodings_dict[name])
            print(f"Averaged {len(encodings_dict[name])} encodings for {name}")
        else:
            encodings_dict[name] = encodings_dict[name][0]
    return encodings_dict

# Settings
IMAGE_FOLDER = "known_faces"
ENCODINGS_FILE = "face_encodings.pkl"

# Compute and save encodings
known_faces = compute_encodings(IMAGE_FOLDER)
with open(ENCODINGS_FILE, "wb") as f:
    pickle.dump(known_faces, f)
print(f"Saved encodings to {ENCODINGS_FILE}")