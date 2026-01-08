# import sqlite3
# from datetime import datetime

# # Connect to the database
# conn = sqlite3.connect("tracking.db")
# cursor = conn.cursor()

# # Clear existing data (optional, comment out if you don’t want to clear)
# cursor.execute("DELETE FROM logs")

# # Mapping of Floor_N to room names used in the app
# floor_to_room = {
#     "Floor_1": "Room 1",
#     "Floor_2": "Room 2",
#     "Floor_3": "Main Room",
#     "Kitchen": "Kitchen",
# }

# # List of actual image files from the evidence folder
# # Format: (name, timestamp, floor, file_path)
# image_data = [
#     # Abdelrahman
#     ("Abdelrahman", "2025-04-13 11:11:03", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-03_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:05", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-05_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:09", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-09_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:11", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-11_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:12", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-12_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:13", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-13_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:14", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-14_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:16", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-16_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:17", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-17_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:18", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-18_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:11:19", "Floor_3", "evidence/Abdelrahman_image_2025-04-13 11-11-19_Floor_3.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:17", "Floor_1", "evidence/Abdelrahman_image_2025-04-13 11-15-17_Floor_1.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:18", "Floor_1", "evidence/Abdelrahman_image_2025-04-13 11-15-18_Floor_1.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:34", "Floor_1", "evidence/Abdelrahman_image_2025-04-13 11-15-34_Floor_1.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:36", "Floor_1", "evidence/Abdelrahman_image_2025-04-13 11-15-36_Floor_1.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:47", "Floor_2", "evidence/Abdelrahman_image_2025-04-13 11-15-47_Floor_2.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:49", "Floor_2", "evidence/Abdelrahman_image_2025-04-13 11-15-49_Floor_2.jpg"),
#     ("Abdelrahman", "2025-04-13 11:15:52", "Floor_1", "evidence/Abdelrahman_image_2025-04-13 11-15-52_Floor_1.jpg"),
#     # Mahmoud (from Eng.mahmoud)
#     ("Mahmoud", "2025-04-13 12:44:24", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-44-24_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:33", "Floor_1", "evidence/Eng.mahmoud_2025-04-13 12-44-33_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:34", "Floor_1", "evidence/Eng.mahmoud_2025-04-13 12-44-34_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:38", "Floor_1", "evidence/Eng.mahmoud_2025-04-13 12-44-38_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:41", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-44-41_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:43", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-44-43_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:44", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-44-44_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:45", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-44-45_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:46", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-44-46_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:51", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-44-51_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:53", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-44-53_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:54", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-44-54_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:44:56", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-44-56_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:45:00", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-45-00_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:45:02", "Floor_2", "evidence/Eng.mahmoud_2025-04-13 12-45-02_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:45:07", "Floor_3", "evidence/Eng.mahmoud_2025-04-13 12-45-07_Floor_3.jpg"),
#     # Mahmoud (from Mahmoud_Ahmed)
#     ("Mahmoud", "2025-04-13 11:09:58", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-09-58_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:00", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-00_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:01", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-01_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:03", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-03_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:05", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-05_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:07", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-07_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:10", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-10_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:12", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-12_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:19", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-19_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:22", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-22_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:23", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-23_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:27", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-27_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:30", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-30_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:34", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-34_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:47", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-47_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:52", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-52_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:53", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-53_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:55", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-55_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:10:58", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-10-58_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:00", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-00_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:03", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-03_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:05", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-05_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:06", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-06_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:09", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-09_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:09", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-09_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 11:11:13", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-11-13_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:14:50", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 11-14-50_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:02", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-02_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:11", "Floor_3", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-11_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:13", "Floor_3", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-13_Floor_3.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:18", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-18_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:19", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-19_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:34", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-34_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:36", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-36_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:37", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-37_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:38", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-38_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:42", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-42_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:43", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-43_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 11:15:45", "Floor_1", "evidence/Mahmoud_Ahmed_2025-04-13 11-15-45_Floor_1.jpg"),
#     ("Mahmoud", "2025-04-13 12:40:02", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 12-40-02_Floor_2.jpg"),
#     ("Mahmoud", "2025-04-13 12:40:03", "Floor_2", "evidence/Mahmoud_Ahmed_2025-04-13 12-40-03_Floor_2.jpg"),
#     # Ragab (from mohamed_ragab)
#     ("Ragab", "2025-04-13 11:09:49", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-49_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:50", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-50_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:51", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-51_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:52", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-52_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:53", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-53_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:54", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-54_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:56", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-56_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:09:57", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-09-57_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:00", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-00_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:03", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-03_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:10", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-10_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:14", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-14_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:16", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-16_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:18", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-18_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:23", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-23_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:25", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-25_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:28", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-28_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:29", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-29_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:31", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-31_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:34", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-34_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:35", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-35_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:36", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-36_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:37", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-37_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:38", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-38_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:40", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-40_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:42", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-42_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:45", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-45_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:10:49", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-10-49_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:11:03", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-11-03_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:11:11", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-11-11_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:49", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-49_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:51", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-51_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:53", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-53_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:54", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-54_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:55", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-55_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:57", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-57_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:14:59", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-14-59_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:01", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-01_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:02", "Floor_2", "evidence/mohamed_ragab_2025-41-13 11-15-02_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:04", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-04_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:06", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-06_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:09", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-09_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:11", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-11_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:12", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-12_Floor_2.jpg"),
#     ("Ragab", "2025-04-13 11:15:14", "Floor_2", "evidence/mohamed_ragab_2025-04-13 11-15-14_Floor_2.jpg"),
#     # Mostafa
#     ("Mostafa", "2025-04-07 10:05:32", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-32_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:33", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-33_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:34", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-34_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:35", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-35_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:37", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-37_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:38", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-38_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:39", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-39_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:40", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-40_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:41", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-41_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:42", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-42_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:43", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-43_Floor_1.jpg"),
#     ("Mostafa", "2025-04-07 10:05:44", "Floor_1", "evidence/Mostafa_2025-04-07 10-05-44_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:25", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-25_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:27", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-27_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:27", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-27_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:28", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-28_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:28", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-28_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:29", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-29_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:29", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-29_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:30", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-30_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:30", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-30_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:32", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-32_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:32", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-32_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:34", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-34_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:34", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-34_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:35", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-35_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:35", "Floor_2", "evidence/Mostafa_2025-04-10 10-40-35_Floor_2.jpg"),
#     ("Mostafa", "2025-04-10 10:40:36", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-36_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:37", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-37_Floor_1.jpg"),
#     ("Mostafa", "2025-04-10 10:40:38", "Floor_1", "evidence/Mostafa_2025-04-10 10-40-38_Floor_1.jpg"),
#     ("Mostafa", "2025-04-13 11:10:28", "Floor_3", "evidence/Mostafa_2025-04-13 11-10-28_Floor_3.jpg"),
#     ("Mostafa", "2025-04-13 11:10:42", "Floor_3", "evidence/Mostafa_2025-04-13 11-10-42_Floor_3.jpg"),
#     ("Mostafa", "2025-04-13 11:10:44", "Floor_3", "evidence/Mostafa_2025-04-13 11-10-44_Floor_3.jpg"),
#     ("Mostafa", "2025-04-13 12:45:00", "Floor_2", "evidence/Mostafa_2025-04-13 12-45-00_Floor_2.jpg"),
#     ("Mostafa", "2025-04-13 12:45:05", "Floor_1", "evidence/Mostafa_2025-04-13 12-45-05_Floor_1.jpg"),
#     ("Mostafa", "2025-04-13 12:45:06", "Floor_1", "evidence/Mostafa_2025-04-13 12-45-06_Floor_1.jpg"),
#     ("Mostafa", "2025-04-13 12:45:08", "Floor_1", "evidence/Mostafa_2025-04-13 12-45-08_Floor_1.jpg"),
#     ("Mostafa", "2025-04-13 12:45:10", "Floor_1", "evidence/Mostafa_2025-04-13 12-45-10_Floor_1.jpg"),
#     # Yousef
#     ("Yousef", "2025-04-13 12:39:32", "Floor_2", "evidence/yousef_2025-04-13 12-39-32_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:39:34", "Floor_2", "evidence/yousef_2025-04-13 12-39-34_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:39:35", "Floor_2", "evidence/yousef_2025-04-13 12-39-35_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:39:36", "Floor_2", "evidence/yousef_2025-04-13 12-39-36_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:39:38", "Floor_2", "evidence/yousef_2025-04-13 12-39-38_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:39:44", "Floor_3", "evidence/yousef_2025-04-13 12-39-44_Floor_3.jpg"),
#     ("Yousef", "2025-04-13 12:39:45", "Floor_3", "evidence/yousef_2025-04-13 12-39-45_Floor_3.jpg"),
#     ("Yousef", "2025-04-13 12:39:46", "Floor_3", "evidence/yousef_2025-04-13 12-39-46_Floor_3.jpg"),
#     ("Yousef", "2025-04-13 12:39:47", "Floor_3", "evidence/yousef_2025-04-13 12-39-47_Floor_3.jpg"),
#     ("Yousef", "2025-04-13 12:39:56", "Floor_1", "evidence/yousef_2025-04-13 12-39-56_Floor_1.jpg"),
#     ("Yousef", "2025-04-13 12:39:58", "Floor_1", "evidence/yousef_2025-04-13 12-39-58_Floor_1.jpg"),
#     ("Yousef", "2025-04-13 12:45:00", "Floor_2", "evidence/yousef_2025-04-13 12-45-00_Floor_2.jpg"),
#     ("Yousef", "2025-04-13 12:45:02", "Floor_2", "evidence/yousef_2025-04-13 12-45-02_Floor_2.jpg"),

#     ("Gamila", "2025-04-13 12:45:05", "Kitchen", "evidence/yousef_2025-04-13 12-45-02_Floor_1.jpg"),
#     ("Dalia", "2025-04-13 12:45:08", "Floor_3", "evidence/yousef_2025-04-13 12-45-02_Floor_3.jpg"),
# ]

# # Convert to database entries with mapped room names
# sample_data = [
#     (name, floor_to_room[floor], timestamp, file_path)
#     for name, timestamp, floor, file_path in image_data
# ]

# # Insert the data into the logs table
# cursor.executemany("INSERT INTO logs (name, location, time, image_path) VALUES (?, ?, ?, ?)", sample_data)

# # Commit and close
# conn.commit()
# conn.close()

# print("Data injected successfully.")



import sqlite3

# Path to your SQLite database
db_file = "tracking.db"

# Connect to the database
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Clear the logs table
cursor.execute("DELETE FROM logs")
conn.commit()

print("✅ All entries in 'logs' table have been deleted.")

# Close the connection
conn.close()