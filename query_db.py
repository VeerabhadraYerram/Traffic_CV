import os
from sqlalchemy import create_engine, text

# Connect to the database (exposed by Docker on port 5432 locally, or via network inside container)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:adminpassword@localhost:5432/traffic")
engine = create_engine(DATABASE_URL)

def view_database():
    print("\n=== 📸 ACTIVE CAMERAS ===")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, video_source, camera_role, is_active FROM cameras WHERE is_active = True"))
            rows = result.fetchall()
            if not rows:
                print("No active cameras found.")
            else:
                # Print headers
                print(f"{'ID':<40} | {'Name':<25} | {'Video Source':<35} | {'Role':<15}")
                print("-" * 125)
                for row in rows:
                    print(f"{str(row[0]):<40} | {row[1]:<25} | {row[2]:<35} | {row[3]:<15}")
    except Exception as e:
        print(f"Could not read cameras: {e}")

    print("\n=== 🚗 PREMISE ACCESS LOGS ===")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT visit_id, tracker_id, license_plate, entry_time, exit_time FROM premise_access_logs"))
            rows = result.fetchall()
            if not rows:
                print("No vehicles have been logged yet.")
            else:
                # Print headers
                print(f"{'Visit ID':<40} | {'Tracker ID':<10} | {'License Plate':<15} | {'Entry Time (UTC)':<25} | {'Exit Time (UTC)':<25}")
                print("-" * 125)
                for row in rows:
                    entry_str = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'N/A'
                    exit_str = row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else 'Active'
                    plate = row[2] if row[2] else 'UNKNOWN'
                    print(f"{str(row[0]):<40} | {row[1]:<10} | {plate:<15} | {entry_str:<25} | {exit_str:<25}")
    except Exception as e:
        print(f"Could not read logs: {e}")

if __name__ == "__main__":
    view_database()
