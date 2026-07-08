import os
from sqlalchemy import create_engine
import pandas as pd

# Prevent pandas from hiding columns with "..."
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# Connect to the local database exposed by Docker on port 5432
DATABASE_URL = "postgresql://admin:adminpassword@localhost:5432/traffic"
engine = create_engine(DATABASE_URL)

def view_database():
    print("\n=== 📸 ACTIVE CAMERAS ===")
    try:
        cameras_df = pd.read_sql_table('cameras', con=engine)
        print(cameras_df[['id', 'name', 'video_source', 'camera_role', 'is_active']])
    except Exception as e:
        print(f"Could not read cameras: {e}")

    print("\n=== 🚗 PREMISE ACCESS LOGS ===")
    try:
        logs_df = pd.read_sql_table('premise_access_logs', con=engine)
        if logs_df.empty:
            print("No vehicles have been logged yet.")
        else:
            print(logs_df[['visit_id', 'tracker_id', 'license_plate', 'entry_time', 'exit_time']])
    except Exception as e:
        print(f"Could not read logs: {e}")

if __name__ == "__main__":
    view_database()
