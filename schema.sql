CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE camera_role_enum AS ENUM ('entrance', 'exit', 'bidirectional', 'internal');

CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    video_source TEXT NOT NULL,
    camera_role camera_role_enum NOT NULL,
    entry_line_normalized JSONB,
    exit_line_normalized JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    status TEXT DEFAULT 'ACTIVE',
    ip_address TEXT,
    speed_limit_kmh INTEGER DEFAULT 30
);

CREATE TABLE premise_access_logs (
    visit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id),
    tracker_id INTEGER NOT NULL,
    license_plate TEXT,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes NUMERIC,
    is_active BOOLEAN DEFAULT TRUE,
    ocr_confidence DOUBLE PRECISION,
    vehicle_type TEXT DEFAULT 'Car',
    vehicle_color TEXT DEFAULT 'White',
    image_url TEXT,
    speed_kmh DOUBLE PRECISION,
    is_violation BOOLEAN DEFAULT FALSE
);

CREATE TABLE violations (
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

-- Seed cameras matching VNR VJIET campus layout
INSERT INTO cameras (id, name, video_source, camera_role, entry_line_normalized, exit_line_normalized, latitude, longitude, status, ip_address, speed_limit_kmh)
VALUES 
('a0e0a0a0-0000-0000-0000-000000000001', 'Main Entrance (Gate 1)', '/app/downloads/test_video.mp4', 'bidirectional', '{"x1": 0.0, "y1": 0.4268, "x2": 1.0, "y2": 0.4268}'::jsonb, '{"x1": 0.0, "y1": 0.6824, "x2": 1.0, "y2": 0.6824}'::jsonb, 17.5365, 78.3835, 'ACTIVE', '192.168.10.11', 30),
('a0e0a0a0-0000-0000-0000-000000000002', 'Academic A-Block', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5375, 78.3842, 'ACTIVE', '192.168.10.12', 20),
('a0e0a0a0-0000-0000-0000-000000000003', 'Library & CSE Block', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5383, 78.3838, 'ACTIVE', '192.168.10.13', 20),
('a0e0a0a0-0000-0000-0000-000000000004', 'Central Canteen', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5392, 78.3832, 'ACTIVE', '192.168.10.14', 20),
('a0e0a0a0-0000-0000-0000-000000000005', 'West Entrance (Gate 2)', '/app/downloads/test_video.mp4', 'bidirectional', NULL, NULL, 17.5380, 78.3810, 'ACTIVE', '192.168.10.15', 30),
('a0e0a0a0-0000-0000-0000-000000000006', 'Main Parking Lot', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5371, 78.3820, 'ACTIVE', '192.168.10.16', 20),
('a0e0a0a0-0000-0000-0000-000000000007', 'Sports Complex / Ground', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5401, 78.3844, 'MAINTENANCE', '192.168.10.17', 25),
('a0e0a0a0-0000-0000-0000-000000000008', 'Research Park Gate', '/app/downloads/test_video.mp4', 'internal', NULL, NULL, 17.5388, 78.3846, 'OFFLINE', '192.168.10.18', 20);
