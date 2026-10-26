from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Enum, Float, text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base
import enum

class CameraRole(str, enum.Enum):
    entrance = "entrance"
    exit = "exit"
    bidirectional = "bidirectional"
    internal = "internal"

class UC4CameraConfig(Base):
    """Local cache of camera configuration received dynamically from platform."""
    __tablename__ = "uc4_camera_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    camera_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    video_source = Column(String, nullable=True)
    camera_role = Column(Enum(CameraRole), default=CameraRole.bidirectional, nullable=False)
    entry_line_normalized = Column(JSONB)
    exit_line_normalized = Column(JSONB)
    speed_polygon_normalized = Column(JSONB)
    calibration_polygon_normalized = Column(JSONB)
    distance_between_lines_meters = Column(Float, default=15.0)
    speed_limit_kmh = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

class UC4PremiseAccessLog(Base):
    """Permanent vehicle access events logged by UC4 ANPR."""
    __tablename__ = "uc4_premise_access_logs"

    visit_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    camera_id = Column(String, nullable=False, index=True)
    tracker_id = Column(Integer, nullable=False)
    license_plate = Column(String, nullable=False, index=True)
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    exit_time = Column(DateTime(timezone=True))
    duration_minutes = Column(Numeric)
    ocr_confidence = Column(Float, default=0.0)
    vehicle_type = Column(String, default="Car")
    vehicle_color = Column(String, default="Unknown")
    speed_kmh = Column(Float, default=0.0)
    is_violation = Column(Boolean, default=False)
    snapshot_path = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("ix_uc4_access_cam_entry", "camera_id", "entry_time"),
    )

class UC4Violation(Base):
    """Violations detected by UC4 (e.g. Speeding, Blacklisted plates)."""
    __tablename__ = "uc4_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    event_id = Column(UUID(as_uuid=True), ForeignKey("uc4_premise_access_logs.visit_id", ondelete="CASCADE"))
    camera_id = Column(String, nullable=True)
    license_plate = Column(String, nullable=False, index=True)
    violation_type = Column(String, nullable=False)  # SPEEDING, BLACKLISTED
    recorded_value = Column(Float)
    zone_limit = Column(Float)
    severity_level = Column(String, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String, default="UNRESOLVED")     # UNRESOLVED, ACKNOWLEDGED, RESOLVED
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), index=True)

# Backward-compatibility aliases
Camera = UC4CameraConfig
PremiseAccessLog = UC4PremiseAccessLog
Violation = UC4Violation
