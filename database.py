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
    
    # Run seed function
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()

def seed_data(db):
    from models import Camera, PremiseAccessLog, Violation, CameraRole
    import random
    from datetime import datetime, timedelta

    # Check if we have cameras
    camera_count = db.query(Camera).count()
    if camera_count > 0:
        return
        
    print("Database is empty. Seeding cameras, events, and violations...")
    
    mock_cameras = [
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
        )
    ]
    
    for cam in mock_cameras:
        db.add(cam)
    db.commit()

    vehicles = [
        ("TS08EX1234", "Car", "Red", True),
        ("AP28CH7890", "Car", "Black", True),
        ("TS07HB9999", "Bike", "Black", False),
        ("TS09FF1122", "Car", "White", True),
        ("TS08AJ5566", "Car", "Silver", False),
        ("AP29BK4321", "Car", "Grey", False),
        ("TS08EF2020", "Truck", "Yellow", False),
        ("TS07NK8765", "Bus", "White", False),
        ("TS08ER4321", "Car", "Blue", False),
        ("TS07AF9988", "Bike", "Red", False)
    ]

    cams = db.query(Camera).filter(Camera.is_active == True).all()
    if not cams:
        return

    now = datetime.utcnow()
    for i in range(40):
        plate, v_type, color, is_blacklisted = random.choice(vehicles)
        cam = random.choice(cams)

        is_speeding = not is_blacklisted and random.random() < 0.15
        is_violation = is_blacklisted or is_speeding

        speed = random.randint(35, 55) if is_speeding else random.randint(15, 29)
        ocr_conf = random.uniform(85, 99)

        entry_time = now - timedelta(minutes=i * 20 + random.randint(0, 10))
        exit_time = entry_time + timedelta(seconds=random.randint(10, 120)) if random.random() > 0.2 else None
        duration = (exit_time - entry_time).total_seconds() / 60.0 if exit_time else None

        log = PremiseAccessLog(
            camera_id=cam.id,
            tracker_id=100 + i,
            license_plate=plate,
            ocr_confidence=ocr_conf,
            vehicle_type=v_type,
            vehicle_color=color,
            image_url=f"https://images.unsplash.com/photo-{1549399542 + (i % 5)}-7e3f8b79c341?w=600&auto=format&fit=crop&q=80",
            entry_time=entry_time,
            exit_time=exit_time,
            duration_minutes=duration,
            speed_kmh=float(speed),
            is_violation=is_violation,
            is_active=False if exit_time else True
        )
        db.add(log)
        db.flush()

        if is_violation:
            v_type_str = "BLACKLISTED" if is_blacklisted else "SPEEDING"
            rec_val = 0.0 if is_blacklisted else float(speed)
            limit_val = 0.0 if is_blacklisted else float(cam.speed_limit_kmh)
            sev = "CRITICAL" if is_blacklisted else ("HIGH" if speed > cam.speed_limit_kmh + 15 else "MEDIUM")

            vio = Violation(
                event_id=log.visit_id,
                license_plate=plate,
                violation_type=v_type_str,
                recorded_value=rec_val,
                zone_limit=limit_val,
                severity_level=sev,
                status="UNRESOLVED" if random.random() > 0.4 else "ACKNOWLEDGED",
                created_at=entry_time
            )
            db.add(vio)

    db.commit()
    print("Database successfully seeded.")
