import os

# Photo map
photo_map = {
    "Abdelrahman_image": "abdelrahman.png",
    "Eng.mahmoud": "Eng.mahmoud.png",
    "Mahmoud_Ahmed": "Mahmoud_Ahmed.png",
    "Mostafa": "Mostafa-2.png",
    "mohamed_ragab": "Ragab.png",
    "yousef": "yousef.png",
    "Dalia": "dalia.PNG",
    "Hagar": "hagar.jpeg",
    "Gamila": "Gamila.jpg"
}

formal_photos_dir = "Formal photos"

print("Checking if photo files exist:")
for name, photo_file in photo_map.items():
    file_path = os.path.join(formal_photos_dir, photo_file)
    exists = os.path.exists(file_path)
    status = "✅" if exists else "❌"
    print(f"  {status} '{name}' -> '{photo_file}' {'(EXISTS)' if exists else '(MISSING)'}")

print("\nFiles in Formal photos directory:")
if os.path.exists(formal_photos_dir):
    files = sorted(os.listdir(formal_photos_dir))
    for file in files:
        print(f"  {file}")
else:
    print("  Directory not found!")
