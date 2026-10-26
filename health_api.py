"""
health_api.py — Non-blocking HTTP API for container health checks and dynamic camera configuration.
Adheres to Approach 2: keeps health checking completely separate from video inference loops.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import settings
from database import get_db, engine
from models import UC4CameraConfig, CameraRole

logger = logging.getLogger(__name__)

app = FastAPI(
    title="UC4 ANPR Health & Config Service",
    version="2.0.0",
    description="Provides orchestrator health probes and platform dynamic camera configuration for UC4."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global runtime telemetry shared with worker
telemetry: Dict[str, Any] = {
    "start_time": time.time(),
    "processed_frames": 0,
    "dropped_stale_frames": 0,
    "alerts_emitted": 0,
    "active_cameras": {},
    "last_processed_timestamp": None,
    "redis_healthy": False,
    "db_healthy": False
}

class LineCoords(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class PointCoords(BaseModel):
    x: float
    y: float

class CameraUpdateRequest(BaseModel):
    camera_id: str
    name: Optional[str] = None
    camera_role: Optional[str] = "bidirectional"
    video_source: Optional[str] = None
    entry_line_normalized: Optional[LineCoords] = None
    exit_line_normalized: Optional[LineCoords] = None
    speed_polygon_normalized: Optional[List[PointCoords]] = None
    calibration_polygon_normalized: Optional[List[PointCoords]] = None
    distance_between_lines_meters: Optional[float] = 15.0
    speed_limit_kmh: Optional[int] = 30
    is_active: Optional[bool] = True

@app.get("/health")
def health_check():
    """
    Non-blocking health probe endpoint queried by Docker and the platform orchestrator.
    Returns 200 OK when operational; 503 Service Unavailable if critical dependencies fail.
    """
    now = time.time()
    uptime = int(now - telemetry["start_time"])

    # Check database liveness
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            db_ok = True
    except Exception as e:
        logger.error(f"DB health probe failed: {e}")

    telemetry["db_healthy"] = db_ok

    status_str = "healthy" if db_ok else "degraded"
    
    return {
        "status": status_str,
        "service": settings.SERVICE_NAME,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime,
        "telemetry": {
            "processed_frames": telemetry["processed_frames"],
            "dropped_stale_frames": telemetry["dropped_stale_frames"],
            "alerts_emitted": telemetry["alerts_emitted"],
            "active_cameras_count": len(telemetry["active_cameras"]),
            "last_processed_time": telemetry["last_processed_timestamp"]
        },
        "dependencies": {
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if telemetry["redis_healthy"] else "disconnected"
        }
    }

@app.get("/api/v1/cameras")
def list_cameras(db: Session = Depends(get_db)):
    """Lists all registered cameras configured for UC4."""
    cameras = db.query(UC4CameraConfig).all()
    return cameras

@app.post("/api/v1/cameras/update")
def update_camera(payload: CameraUpdateRequest, db: Session = Depends(get_db)):
    """
    Dynamic camera configuration endpoint.
    Called by the platform when an admin defines or adjusts LineZones/polygons.
    Updates the local database and immediately refreshes the active worker tracker without restarts.
    """
    cam = db.query(UC4CameraConfig).filter(UC4CameraConfig.camera_id == payload.camera_id).first()
    if not cam:
        cam = UC4CameraConfig(
            camera_id=payload.camera_id,
            name=payload.name or f"Camera {payload.camera_id}",
            camera_role=CameraRole(payload.camera_role) if payload.camera_role in CameraRole.__members__ else CameraRole.bidirectional
        )
        db.add(cam)

    if payload.name:
        cam.name = payload.name
    if payload.camera_role and payload.camera_role in CameraRole.__members__:
        cam.camera_role = CameraRole(payload.camera_role)
    if payload.video_source:
        cam.video_source = payload.video_source
    if payload.entry_line_normalized:
        cam.entry_line_normalized = payload.entry_line_normalized.dict()
    if payload.exit_line_normalized:
        cam.exit_line_normalized = payload.exit_line_normalized.dict()
    if payload.speed_polygon_normalized:
        cam.speed_polygon_normalized = [p.dict() for p in payload.speed_polygon_normalized]
    if payload.calibration_polygon_normalized:
        cam.calibration_polygon_normalized = [p.dict() for p in payload.calibration_polygon_normalized]
    if payload.distance_between_lines_meters is not None:
        cam.distance_between_lines_meters = payload.distance_between_lines_meters
    if payload.speed_limit_kmh is not None:
        cam.speed_limit_kmh = payload.speed_limit_kmh
    if payload.is_active is not None:
        cam.is_active = payload.is_active

    db.commit()
    db.refresh(cam)

    # Immediately update worker's in-memory camera cache
    telemetry["active_cameras"][payload.camera_id] = {
        "name": cam.name,
        "role": cam.camera_role,
        "entry_line": cam.entry_line_normalized,
        "exit_line": cam.exit_line_normalized,
        "speed_polygon": cam.speed_polygon_normalized,
        "calibration_polygon": cam.calibration_polygon_normalized,
        "distance_between_lines_meters": cam.distance_between_lines_meters,
        "speed_limit_kmh": cam.speed_limit_kmh,
        "is_active": cam.is_active
    }

    logger.info(f"✅ [CameraConfigUpdated] Dynamically updated camera: {payload.camera_id} ({cam.name})")
    return {"status": "success", "message": f"Camera {payload.camera_id} updated successfully"}
