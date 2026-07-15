from sqlalchemy import text
from database import engine

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN calibration_polygon_normalized JSONB;"))
            conn.commit()
            print("Successfully added calibration_polygon_normalized to cameras table.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("Column already exists, skipping.")
            else:
                print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
