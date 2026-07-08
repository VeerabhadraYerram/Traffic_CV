from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Enum, text
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

class PremiseAccessLog(Base):
    __tablename__ = "premise_access_logs"

    visit_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    camera_id = Column(UUID(as_uuid=True))
    tracker_id = Column(Integer, nullable=False)
    license_plate = Column(String)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True))
    duration_minutes = Column(Numeric)
    is_active = Column(Boolean, default=True)
