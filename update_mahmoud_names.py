import sqlite3
import os

def update_mahmoud_names():
    # Connect to the database
    conn = sqlite3.connect('tracking.db')
    cursor = conn.cursor()
    
    # Create a backup of the database
    if os.path.exists('tracking.db.bak'):
        os.remove('tracking.db.bak')
    conn.backup(sqlite3.connect('tracking.db.bak'))
    
    try:
        # Update entries for Eng. Mahmoud
        cursor.execute("""
            UPDATE logs 
            SET name = 'Eng. Mahmoud',
                image_path = REPLACE(image_path, 'evidence/Eng.mahmoud', 'evidence/Eng.Mahmoud')
            WHERE image_path LIKE 'evidence/Eng.mahmoud%'
        """)
        
        # Update entries for Mahmoud Ahmed
        cursor.execute("""
            UPDATE logs 
            SET name = 'Mahmoud Ahmed',
                image_path = REPLACE(image_path, 'evidence/Mahmoud_Ahmed', 'evidence/Mahmoud_Ahmed')
            WHERE image_path LIKE 'evidence/Mahmoud_Ahmed%'
        """)
        
        # Commit the changes
        conn.commit()
        print("Successfully updated Mahmoud names in the database")
        
    except Exception as e:
        print(f"Error updating database: {e}")
        # Restore from backup if there's an error
        if os.path.exists('tracking.db.bak'):
            os.remove('tracking.db')
            os.rename('tracking.db.bak', 'tracking.db')
            print("Database restored from backup")
    
    finally:
        conn.close()

if __name__ == "__main__":
    update_mahmoud_names() 