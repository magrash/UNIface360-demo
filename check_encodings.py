import pickle
import os

# Load the encodings file
with open("face_encodings.pkl", "rb") as f:
    encodings = pickle.load(f)

print(f"Number of known faces: {len(encodings)}")
print(f"Known face names: {list(encodings.keys())}")
