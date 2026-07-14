from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Enum, Float, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base
import enum

class CameraRole(enum.Enum):
    entrance = "entrance"
    exit = "exit"
    bidirectional = "bidirectional"
    internal = "internal"

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String, nullable=False)
    video_source = Column(String, nullable=False)
    camera_role = Column(Enum(CameraRole), nullable=False)
    entry_line_normalized = Column(JSONB)
    exit_line_normalized = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    
    # Dashboard additions
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String, default="ACTIVE")
    ip_address = Column(String)
    speed_limit_kmh = Column(Integer, default=30)
    speed_polygon_normalized = Column(JSONB)
    distance_between_lines_meters = Column(Float)

class PremiseAccessLog(Base):
    __tablename__ = "premise_access_logs"

    visit_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"))
    tracker_id = Column(Integer, nullable=False)
    license_plate = Column(String)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True))
    duration_minutes = Column(Numeric)
    is_active = Column(Boolean, default=True)
    
    # Dashboard additions
    ocr_confidence = Column(Float)
    vehicle_type = Column(String, default="Car")
    vehicle_color = Column(String, default="White")
    image_url = Column(String)
    speed_kmh = Column(Float)
    is_violation = Column(Boolean, default=False)

class Violation(Base):
    __tablename__ = "violations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    event_id = Column(UUID(as_uuid=True), ForeignKey("premise_access_logs.visit_id", ondelete="CASCADE"))
    license_plate = Column(String, nullable=False)
    violation_type = Column(String, nullable=False) # SPEEDING, BLACKLISTED
    recorded_value = Column(Float)
    zone_limit = Column(Float)
    severity_level = Column(String, nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String, default="UNRESOLVED") # UNRESOLVED, ACKNOWLEDGED, ESCALATED, RESOLVED
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
