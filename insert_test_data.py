import sqlite3

# conn = sqlite3.connect("tracking.db")
# cursor = conn.cursor()

# test_data = [
#     ("Mostafa", "2025-04-22 06:00:00", "Floor 1", "evidence/Mostafa_2025-04-22-06-00-00_Floor_1.jpg"),
#     ("Mostafa", "2025-04-22 08:15:00", "Floor 1", "evidence/Mostafa_2025-04-22-08-15-00_Floor_1.jpg"),
#     ("Mostafa", "2025-04-22 15:30:00", "Floor 1", "evidence/Mostafa_2025-04-22-15-30-00_Floor_1.jpg"),
#     ("John", "2025-04-22 06:05:00", "Floor 2", "evidence/John_2025-04-22-06-05-00_Floor_2.jpg"),
#     ("John", "2025-04-22 07:50:00", "Floor 2", "evidence/John_2025-04-22-07-50-00_Floor_2.jpg"),
#     ("John", "2025-04-22 16:10:00", "Floor 2", "evidence/John_2025-04-22-16-10-00_Floor_2.jpg"),
# ]

# cursor.executemany("INSERT INTO logs (name, time, floor, image_path) VALUES (?, ?, ?, ?)", test_data)
# conn.commit()
# print(f"Inserted {cursor.rowcount} rows into tracking.db")
# conn.close()



conn = sqlite3.connect("tracking.db")
cursor = conn.execute("SELECT * FROM logs WHERE time LIKE '2025-04-22%'")
for row in cursor:
    print(row)
conn.close()