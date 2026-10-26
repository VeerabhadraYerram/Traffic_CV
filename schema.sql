CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE uc4_camera_role_enum AS ENUM ('entrance', 'exit', 'bidirectional', 'internal');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1. Local Camera Configuration Cache (dynamically populated from platform registry)
CREATE TABLE IF NOT EXISTS uc4_camera_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    video_source TEXT,
    camera_role uc4_camera_role_enum DEFAULT 'bidirectional',
    entry_line_normalized JSONB,
    exit_line_normalized JSONB,
    speed_polygon_normalized JSONB,
    calibration_polygon_normalized JSONB,
    distance_between_lines_meters DOUBLE PRECISION DEFAULT 15.0,
    speed_limit_kmh INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_uc4_camera_configs_cam_id ON uc4_camera_configs(camera_id);

-- 2. Vehicle Access Logs (Definitive on-premise log of vehicle access)
CREATE TABLE IF NOT EXISTS uc4_premise_access_logs (
    visit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id TEXT NOT NULL,
    tracker_id INTEGER NOT NULL,
    license_plate TEXT NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes NUMERIC,
    ocr_confidence DOUBLE PRECISION DEFAULT 0.0,
    vehicle_type TEXT DEFAULT 'Car',
    vehicle_color TEXT DEFAULT 'Unknown',
    speed_kmh DOUBLE PRECISION DEFAULT 0.0,
    is_violation BOOLEAN DEFAULT FALSE,
    snapshot_path TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_uc4_access_logs_cam_id ON uc4_premise_access_logs(camera_id);
CREATE INDEX IF NOT EXISTS ix_uc4_access_logs_plate ON uc4_premise_access_logs(license_plate);
CREATE INDEX IF NOT EXISTS ix_uc4_access_logs_entry ON uc4_premise_access_logs(entry_time);
CREATE INDEX IF NOT EXISTS ix_uc4_access_cam_entry ON uc4_premise_access_logs(camera_id, entry_time);

-- 3. Vehicle Violations (Speeding, Blacklisted plates)
CREATE TABLE IF NOT EXISTS uc4_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES uc4_premise_access_logs(visit_id) ON DELETE CASCADE,
    camera_id TEXT,
    license_plate TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    recorded_value DOUBLE PRECISION,
    zone_limit DOUBLE PRECISION,
    severity_level TEXT NOT NULL,
    status TEXT DEFAULT 'UNRESOLVED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_uc4_violations_plate ON uc4_violations(license_plate);
CREATE INDEX IF NOT EXISTS ix_uc4_violations_created ON uc4_violations(created_at);
