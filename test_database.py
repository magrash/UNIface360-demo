import sqlite3
import os
import datetime

# Database file path
DB_FILE = "tracking.db"

def test_database():
    print(f"Testing database connection to {DB_FILE}")
    
    # Check if database file exists
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} does not exist, it will be created.")
    
    # Connect to the database
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        print("✓ Connected to database successfully.")
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
        if cursor.fetchone():
            print("✓ 'logs' table exists.")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(logs)")
            columns = cursor.fetchall()
            print("Table structure:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # Count records
            cursor.execute("SELECT COUNT(*) FROM logs")
            count = cursor.fetchone()[0]
            print(f"✓ Table contains {count} records.")
            
            if count > 0:
                # Show last 5 records
                cursor.execute("SELECT id, name, time, floor, confidence FROM logs ORDER BY id DESC LIMIT 5")
                print("\nLast 5 records:")
                for row in cursor.fetchall():
                    print(f"  ID: {row[0]} | Name: {row[1]} | Time: {row[2]} | Floor: {row[3]} | Confidence: {row[4]}")
        else:
            print("✗ 'logs' table does not exist.")
            
            # Create the table
            print("Creating 'logs' table...")
            cursor.execute("""
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    time TEXT,
                    floor TEXT,
                    image_path TEXT,
                    confidence REAL
                )
            """)
            conn.commit()
            print("✓ Created 'logs' table.")
        
        # Test inserting a record
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_data = ("Test User", current_time, "Test Floor", "test_image_path.jpg", 0.95)
        
        cursor.execute(
            "INSERT INTO logs (name, time, floor, image_path, confidence) VALUES (?, ?, ?, ?, ?)",
            test_data
        )
        conn.commit()
        
        # Verify the insert worked
        cursor.execute("SELECT id FROM logs WHERE name=? AND time=?", ("Test User", current_time))
        result = cursor.fetchone()
        if result:
            print(f"✓ Test record inserted successfully with ID: {result[0]}")
            
            # Clean up test record
            cursor.execute("DELETE FROM logs WHERE name=? AND time=?", ("Test User", current_time))
            conn.commit()
            print("✓ Test record removed.")
        else:
            print("✗ Failed to insert test record.")
        
        conn.close()
        print("✓ Database connection closed.")
        
    except sqlite3.Error as e:
        print(f"✗ SQLite error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        
if __name__ == "__main__":
    test_database()
