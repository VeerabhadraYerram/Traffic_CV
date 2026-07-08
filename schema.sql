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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE premise_access_logs (
    visit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id),
    tracker_id INTEGER NOT NULL,
    license_plate TEXT,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes NUMERIC,
    is_active BOOLEAN DEFAULT TRUE
);

-- Seed data for testing locally within Docker
INSERT INTO cameras (name, video_source, camera_role, entry_line_normalized, exit_line_normalized)
VALUES (
    'Test Video Bidirectional',
    '/app/downloads/test_video.mp4',
    'bidirectional',
    '{"x1": 0.0, "y1": 0.4268, "x2": 1.0, "y2": 0.4268}'::jsonb,
    '{"x1": 0.0, "y1": 0.6824, "x2": 1.0, "y2": 0.6824}'::jsonb
);
