import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# The Docker setup will inject DATABASE_URL, e.g. postgresql://user:password@postgres:5432/traffic
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:adminpassword@localhost:5435/traffic")

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from sqlalchemy import text
    # Run column addition SQL queries to ensure database is migrated
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ACTIVE';"))
        conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ip_address TEXT;"))
        conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS speed_limit_kmh INTEGER DEFAULT 30;"))

        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS ocr_confidence DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS vehicle_type TEXT DEFAULT 'Car';"))
        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS vehicle_color TEXT DEFAULT 'White';"))
        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS image_url TEXT;"))
        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS speed_kmh DOUBLE PRECISION;"))
        conn.execute(text("ALTER TABLE premise_access_logs ADD COLUMN IF NOT EXISTS is_violation BOOLEAN DEFAULT FALSE;"))

        # Create violations table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS violations (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                event_id UUID REFERENCES premise_access_logs(visit_id) ON DELETE CASCADE,
                license_plate TEXT NOT NULL,
                violation_type TEXT NOT NULL,
                recorded_value DOUBLE PRECISION,
                zone_limit DOUBLE PRECISION,
                severity_level TEXT NOT NULL,
                status TEXT DEFAULT 'UNRESOLVED',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    # Run seed function (cameras only — no mock events)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


def seed_data(db):
    """Seeds the 8 campus cameras on first boot. No mock events are created —
    all access logs will come exclusively from the live pipeline processing
    /app/downloads/test_video.mp4."""
    from models import Camera, CameraRole

    # Skip if cameras already exist
    camera_count = db.query(Camera).count()
    if camera_count > 0:
        print("Cameras already present — skipping seed.")
        return

    print("Database is empty. Seeding 8 cameras (no mock events)...")

    cameras = [
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000001",
            name="Main Entrance (Gate 1)",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.bidirectional,
            entry_line_normalized={"x1": 0.0, "y1": 0.4268, "x2": 1.0, "y2": 0.4268},
            exit_line_normalized={"x1": 0.0, "y1": 0.6824, "x2": 1.0, "y2": 0.6824},
            latitude=17.5365,
            longitude=78.3835,
            status="ACTIVE",
            ip_address="192.168.10.11",
            speed_limit_kmh=30,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000002",
            name="Academic A-Block",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5375,
            longitude=78.3842,
            status="ACTIVE",
            ip_address="192.168.10.12",
            speed_limit_kmh=20,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000003",
            name="Library & CSE Block",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5383,
            longitude=78.3838,
            status="ACTIVE",
            ip_address="192.168.10.13",
            speed_limit_kmh=20,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000004",
            name="Central Canteen",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5392,
            longitude=78.3832,
            status="ACTIVE",
            ip_address="192.168.10.14",
            speed_limit_kmh=20,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000005",
            name="West Entrance (Gate 2)",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.bidirectional,
            latitude=17.5380,
            longitude=78.3810,
            status="ACTIVE",
            ip_address="192.168.10.15",
            speed_limit_kmh=30,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000006",
            name="Main Parking Lot",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5371,
            longitude=78.3820,
            status="ACTIVE",
            ip_address="192.168.10.16",
            speed_limit_kmh=20,
            is_active=True
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000007",
            name="Sports Complex / Ground",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5401,
            longitude=78.3844,
            status="MAINTENANCE",
            ip_address="192.168.10.17",
            speed_limit_kmh=25,
            is_active=False
        ),
        Camera(
            id="a0e0a0a0-0000-0000-0000-000000000008",
            name="Research Park Gate",
            video_source="/app/downloads/test_video.mp4",
            camera_role=CameraRole.internal,
            latitude=17.5388,
            longitude=78.3846,
            status="OFFLINE",
            ip_address="192.168.10.18",
            speed_limit_kmh=20,
            is_active=False
        ),
    ]

    for cam in cameras:
        db.add(cam)
    db.commit()
    print("✅ 8 cameras seeded. Awaiting real pipeline data.")
