from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import os
import socket
import shutil
import numpy as np
from typing import Optional, List

from database import SessionLocal, init_db
from models import Camera, PremiseAccessLog, Violation

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

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

class SourcePayload(BaseModel):
    video_source: str

class AcknowledgePayload(BaseModel):
    status: str

# Mount static files (the built React app and assets)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/system/network-info")
def get_network_info(request: Request):
    host_header = request.headers.get("host", "")
    client_host = host_header.split(":")[0] if host_header else ""
    
    if client_host and client_host not in ("localhost", "127.0.0.1") and not client_host.startswith("172."):
        ip = client_host
    else:
        ip = os.getenv("HOST_IP", get_local_ip())
        
    return {
        "local_ip": ip,
        "phone_stream_url": f"http://{ip}:8002/phone",
        "pipeline_stream_url": f"http://{ip}:8001/api/stream"
    }


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

@app.post("/api/cameras/{cam_id}/source")
def update_camera_source(cam_id: str, payload: SourcePayload):
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    if not cam:
        db.close()
        raise HTTPException(status_code=404, detail="Camera not found")
    
    old_source = cam.video_source
    cam.video_source = payload.video_source
    if payload.video_source == "push":
        cam.name = f"Phone Web Camera ({cam.name.split('(')[0].strip()})"
    elif payload.video_source.startswith(("rtsp://", "http://", "https://")):
        cam.name = f"Mobile RTSP Feed ({cam.name.split('(')[0].strip()})"
    
    db.commit()
    db.close()
    return {"status": "success", "old_source": old_source, "new_source": payload.video_source}

latest_push_jpeg = None
latest_push_time = 0.0

@app.post("/api/camera/push")
async def camera_push_receiver(request: Request):
    global latest_push_jpeg, latest_push_time
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        if "frame" in form:
            data = await form["frame"].read()
        else:
            return {"error": "empty frame"}
    else:
        data = await request.body()

    if not data:
        return {"error": "empty frame"}

    latest_push_jpeg = data
    latest_push_time = time.time()

    # Forward asynchronously to pipeline engine container if running
    for target_url in ["http://app:8001/api/camera/push", "http://localhost:8001/api/camera/push"]:
        try:
            req = urllib.request.Request(target_url, data=data, headers={'Content-Type': 'image/jpeg'})
            with urllib.request.urlopen(req, timeout=0.3):
                break
        except Exception:
            continue

    return {"ok": True}

@app.get("/api/cameras/{cam_id}/frame")
def get_camera_frame(cam_id: str):
    global latest_push_jpeg, latest_push_time
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    db.close()
    
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    video_source = cam.video_source.strip("'\"")
    
    if video_source == "push":
        # 1. Check if we have recent push bytes in local web_ui memory
        if latest_push_jpeg is not None and (time.time() - latest_push_time < 30.0):
            return Response(content=latest_push_jpeg, media_type="image/jpeg")

        # 2. Attempt to fetch the live snapshot frame from the running pipeline container
        for target_url in ["http://app:8001/api/camera/frame", "http://localhost:8001/api/camera/frame"]:
            try:
                req = urllib.request.Request(target_url, headers={'User-Agent': 'TrafficCV-Web'})
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    if resp.status == 200:
                        return Response(content=resp.read(), media_type="image/jpeg")
            except Exception:
                continue

        # If no frame received yet, create helpful placeholder with instructions
        placeholder = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(placeholder, "MOBILE WEB STREAM (WAITING FOR PHONE)", (220, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (16, 185, 129), 3)
        ip = os.getenv("HOST_IP", get_local_ip())
        cv2.putText(placeholder, f"Open http://{ip}:8002/phone on your mobile browser", (230, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(placeholder, "and tap 'Start Live Stream', then click Refresh Frame!", (230, 420), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (160, 160, 160), 2)
        _, buffer = cv2.imencode('.jpg', placeholder)
        return Response(content=buffer.tobytes(), media_type="image/jpeg")



    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000|stimeout;3000000"
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail=f"Could not open video source: {video_source}")
        
    ret = False
    frame = None
    for _ in range(10):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            break
            
    cap.release()
    
    if not ret or frame is None:
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

@app.get("/phone")
def phone_page():
    phone_path = os.path.join("static", "phone.html")
    if os.path.exists(phone_path):
        return FileResponse(phone_path)
    return RedirectResponse(url="/static/index.html")

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
