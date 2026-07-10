from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import cv2
import os
import json
from typing import Optional, Dict

from database import SessionLocal
from models import Camera

app = FastAPI(title="Traffic Analytics Web Configurator")

# Mount static files for the frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class LineCoordinate(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class LinesPayload(BaseModel):
    entry_line: Optional[LineCoordinate] = None
    exit_line: Optional[LineCoordinate] = None

@app.get("/api/cameras")
def get_cameras():
    db = SessionLocal()
    cameras = db.query(Camera).filter(Camera.is_active == True).all()
    
    result = []
    for c in cameras:
        result.append({
            "id": str(c.id),
            "name": c.name,
            "role": c.camera_role.value,
            "video_source": c.video_source,
            "entry_line": c.entry_line_normalized,
            "exit_line": c.exit_line_normalized
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
def save_lines(cam_id: str, payload: LinesPayload):
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    
    if not cam:
        db.close()
        raise HTTPException(status_code=404, detail="Camera not found")
        
    if payload.entry_line:
        cam.entry_line_normalized = payload.entry_line.dict()
    if payload.exit_line:
        cam.exit_line_normalized = payload.exit_line.dict()
        
    db.commit()
    db.close()
    
    return {"status": "success", "message": "Lines updated successfully"}

# Provide a root redirect to the static index
from fastapi.responses import RedirectResponse
@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")
