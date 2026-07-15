from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import os
import shutil
from typing import Optional, List

from database import SessionLocal, init_db
from models import Camera, PremiseAccessLog, Violation

app = FastAPI(title="Traffic Analytics Web Configurator & Dashboard")

# Add CORS Middleware to support development environment (Vite on port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    print("Running database migrations and seeding check...")
    init_db()

class LineCoordinate(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class PointCoordinate(BaseModel):
    x: float
    y: float

class ConfigPayload(BaseModel):
    entry_line: Optional[LineCoordinate] = None
    exit_line: Optional[LineCoordinate] = None
    speed_polygon: Optional[List[PointCoordinate]] = None
    calibration_polygon: Optional[List[PointCoordinate]] = None
    distance_between_lines_meters: Optional[float] = None

class AcknowledgePayload(BaseModel):
    status: str

# Mount static files (the built React app and assets)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/cameras")
def get_cameras():
    db = SessionLocal()
    # Return all active cameras
    cameras = db.query(Camera).filter(Camera.is_active == True).all()
    
    result = []
    for c in cameras:
        # We return a merged schema containing both configurator and dashboard fields
        result.append({
            # Configurator expected fields
            "id": str(c.id),
            "name": c.name,
            "role": c.camera_role.value,
            "video_source": c.video_source,
            "entry_line": c.entry_line_normalized,
            "exit_line": c.exit_line_normalized,
            "speed_polygon_normalized": c.speed_polygon_normalized,
            "calibration_polygon_normalized": c.calibration_polygon_normalized,
            "distance_between_lines_meters": c.distance_between_lines_meters,
            
            # Dashboard expected fields
            "camera_id": str(c.id),
            "location_name": c.name,
            "latitude": c.latitude if c.latitude is not None else 17.5365,
            "longitude": c.longitude if c.longitude is not None else 78.3835,
            "status": c.status or "ACTIVE",
            "ip_address": c.ip_address or "127.0.0.1",
            "speed_limit_kmh": c.speed_limit_kmh or 30
        })
    db.close()
    return result

@app.get("/api/cameras/{cam_id}/frame")
def get_camera_frame(cam_id: str):
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    db.close()
    
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    video_source = cam.video_source.strip("'\"")
    
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail=f"Could not open video source: {video_source}")
        
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=400, detail="Could not read frame from video")
        
    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    return Response(content=buffer.tobytes(), media_type="image/jpeg")

@app.post("/api/cameras/{cam_id}/lines")
def save_lines(cam_id: str, payload: ConfigPayload):
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    
    if not cam:
        db.close()
        raise HTTPException(status_code=404, detail="Camera not found")
        
    if payload.entry_line is not None:
        cam.entry_line_normalized = payload.entry_line.dict()
    if payload.exit_line is not None:
        cam.exit_line_normalized = payload.exit_line.dict()
    if payload.speed_polygon is not None:
        cam.speed_polygon_normalized = [p.dict() for p in payload.speed_polygon]
    if payload.calibration_polygon is not None:
        cam.calibration_polygon_normalized = [p.dict() for p in payload.calibration_polygon]
    if payload.distance_between_lines_meters is not None:
        cam.distance_between_lines_meters = payload.distance_between_lines_meters
        
    db.commit()
    db.close()
    
    return {"status": "success", "message": "Configuration updated successfully"}

@app.post("/api/cameras/{cam_id}/video")
def upload_video(cam_id: str, file: UploadFile = File(...)):
    import traceback
    try:
        db = SessionLocal()
        cam = db.query(Camera).filter(Camera.id == cam_id).first()
        
        if not cam:
            db.close()
            raise HTTPException(status_code=404, detail="Camera not found")
            
        os.makedirs("downloads", exist_ok=True)
        file_path = os.path.join("downloads", file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        video_source_path = f"/app/{file_path.replace(os.sep, '/')}"
        cam.video_source = video_source_path
        db.commit()
        db.close()
        
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}\n{traceback.format_exc()}")
    
    return {"status": "success", "message": "Video uploaded successfully", "video_source": video_source_path}

@app.get("/api/events")
def get_events():
    db = SessionLocal()
    try:
        # Join access logs with cameras to get names
        logs = db.query(PremiseAccessLog, Camera.name.label("camera_name")).\
            outerjoin(Camera, Camera.id == PremiseAccessLog.camera_id).\
            order_by(PremiseAccessLog.entry_time.desc()).limit(100).all()
        
        result = []
        for log, cam_name in logs:
            result.append({
                "event_id": str(log.visit_id),
                "camera_id": str(log.camera_id) if log.camera_id else None,
                "camera_name": cam_name or "Unknown Camera",
                "license_plate": log.license_plate or "UNKNOWN",
                "ocr_confidence": float(log.ocr_confidence) if log.ocr_confidence is not None else 92.5,
                "vehicle_type": log.vehicle_type or "Car",
                "vehicle_color": log.vehicle_color or "White",
                "image_url": log.image_url or None,
                "entry_time": log.entry_time.isoformat() if log.entry_time else None,
                "exit_time": log.exit_time.isoformat() if log.exit_time else None,
                "duration_minutes": float(log.duration_minutes) if log.duration_minutes is not None else None,
                "speed_kmh": float(log.speed_kmh) if log.speed_kmh is not None else None,
                "is_violation": bool(log.is_violation)
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/violations")
def get_violations():
    db = SessionLocal()
    try:
        violations = db.query(Violation).order_by(Violation.created_at.desc()).limit(100).all()
        result = []
        for v in violations:
            result.append({
                "violation_id": str(v.id),
                "event_id": str(v.event_id),
                "license_plate": v.license_plate,
                "violation_type": v.violation_type,
                "recorded_value": float(v.recorded_value) if v.recorded_value is not None else 0.0,
                "zone_limit": float(v.zone_limit) if v.zone_limit is not None else 30.0,
                "severity_level": v.severity_level,
                "status": v.status or "UNRESOLVED",
                "created_at": v.created_at.isoformat() if v.created_at else None
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/violations/{violation_id}/acknowledge")
def acknowledge_violation(violation_id: str, payload: AcknowledgePayload):
    db = SessionLocal()
    try:
        violation = db.query(Violation).filter(Violation.id == violation_id).first()
        if not violation:
            raise HTTPException(status_code=404, detail="Violation not found")
        violation.status = payload.status
        db.commit()
        return {"status": "success", "message": f"Violation updated to {payload.status}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Root redirect to the index file
@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

# Catch-all route to serve React dashboard index.html for SPA routes (e.g. /dashboard, /tracking, /analytics)
@app.get("/{catchall:path}")
def catch_all(catchall: str):
    if catchall.startswith("api/") or catchall.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    return RedirectResponse(url="/static/index.html")
