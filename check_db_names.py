import sqlite3

# Connect to database
conn = sqlite3.connect('tracking.db')
cursor = conn.execute("SELECT DISTINCT name FROM logs WHERE name != 'Unknown' ORDER BY name")
names = [row[0] for row in cursor]
conn.close()

print("Names in database:")
for name in names:
    print(f"  '{name}'")

# Check photo map
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

print("\nPhoto map:")
for name, photo in photo_map.items():
    print(f"  '{name}' -> '{photo}'")

print("\nMissing mappings:")
for name in names:
    if name not in photo_map:
        print(f"  '{name}' - NO MAPPING")

print("\nUnused mappings:")
for name in photo_map:
    if name not in names:
        print(f"  '{name}' - NOT IN DATABASE")
