import os
os.environ["OMP_NUM_THREADS"] = "1"
import re
import cv2
import threading
from datetime import datetime
from collections import Counter
import numpy as np
import supervision as sv
from dotenv import load_dotenv

from database import SessionLocal
from models import Camera, PremiseAccessLog, CameraRole, Violation
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr

load_dotenv()

# Global memory for all cameras
# Structure: { camera_id: { tracker_id: { "visit_id": uuid, "plate_reads": [], "plate_confidences": [], "vehicle_type": str, "last_seen": timestamp } } }
active_sessions = {}
session_lock = threading.Lock()

# Blacklist of license plates
BLACKLISTED_PLATES = {"TS08EX1234", "AP28CH7890", "TS09FF1122"}

# YOLO class map to vehicle type
YOLO_CLASS_MAP = {1: "Bike", 2: "Car", 3: "Bike", 5: "Bus", 7: "Truck"}

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def process_camera(cam_id, name, video_source, role, entry_line_norm, exit_line_norm):
    print(f"[{name}] Starting YOLO11 + DeepSORT pipeline...")
    
    # Initialize YOLO11 Model
    model = YOLO("yolo11m.pt")
    
    # Initialize DeepSORT Tracker
    tracker = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
    
    device_is_gpu = False
    if torch.cuda.is_available():
        device_is_gpu = True
    elif torch.backends.mps.is_available():
        device_is_gpu = True
    
    print(f"[{name}] Initializing EasyOCR Model on {'GPU' if device_is_gpu else 'CPU'}...")
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    
    # Init DB memory for this camera
    with session_lock:
        if cam_id not in active_sessions:
            active_sessions[cam_id] = {}
            
    video_source = video_source.strip("'\"")
    
    print(f"[{name}] Attempting to open video source: '{video_source}'")
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"[{name}] ⚠️ Cannot open video source. Exiting thread.")
        return
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    entry_line = None
    if entry_line_norm:
        entry_line = sv.LineZone(
            start=sv.Point(x=int(entry_line_norm["x1"] * width), y=int(entry_line_norm["y1"] * height)),
            end=sv.Point(x=int(entry_line_norm["x2"] * width), y=int(entry_line_norm["y2"] * height))
        )
        
    exit_line = None
    if exit_line_norm:
        exit_line = sv.LineZone(
            start=sv.Point(x=int(exit_line_norm["x1"] * width), y=int(exit_line_norm["y1"] * height)),
            end=sv.Point(x=int(exit_line_norm["x2"] * width), y=int(exit_line_norm["y2"] * height))
        )

    frame_counter = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print(f"[{name}] 🏁 End of video stream.")
            break
            
        frame_counter += 1
        if frame_counter % 30 == 0:
            print(f"[{name}] 🔄 Processed {frame_counter} frames...")

        # 1. Detection
        results = model(frame, classes=[1, 2, 3, 5, 7], conf=0.45, verbose=False)
        
        bbs = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                w = x2 - x1
                h = y2 - y1
                bbs.append(([x1, y1, w, h], conf, cls_id))
                
        # 2. Tracking
        tracks = tracker.update_tracks(bbs, frame=frame)
        
        xyxys = []
        tracker_ids = []
        valid_tracks = []
        
        for track in tracks:
            if not track.is_confirmed():
                continue
                
            tid = int(track.track_id)
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb
            
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            
            # Map YOLO class to vehicle type
            det_cls = track.get_det_class()
            v_type = YOLO_CLASS_MAP.get(det_cls, "Car")
            
            xyxys.append([x1, y1, x2, y2])
            tracker_ids.append(tid)
            valid_tracks.append((tid, x1, y1, x2, y2, v_type))
            
        if not xyxys:
            continue
            
        detections = sv.Detections(
            xyxy=np.array(xyxys),
            tracker_id=np.array(tracker_ids)
        )
        
        # 3. OCR on Tracked Vehicles
        with session_lock:
            for tid, x1, y1, x2, y2, v_type in valid_tracks:
                if tid not in active_sessions[cam_id]:
                    active_sessions[cam_id][tid] = {
                        "plate_reads": [],
                        "plate_confidences": [],
                        "vehicle_type": v_type,
                        "last_seen": frame_counter
                    }
                else:
                    active_sessions[cam_id][tid]["last_seen"] = frame_counter
                    active_sessions[cam_id][tid]["vehicle_type"] = v_type
                    
                if len(active_sessions[cam_id][tid]["plate_reads"]) < 10:
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        ch, cw = crop.shape[:2]
                        plate_crop = crop[int(ch * 0.4):, :]
                        
                        if plate_crop.size > 0:
                            ocr_results = reader.readtext(plate_crop)
                            for bbox, text, prob in ocr_results:
                                if prob > 0.3:
                                    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                    if 4 <= len(cleaned) <= 12:
                                        active_sessions[cam_id][tid]["plate_reads"].append(cleaned)
                                        active_sessions[cam_id][tid]["plate_confidences"].append(float(prob * 100))
                                    
            # Cleanup old trackers
            stale_tids = [t for t, data in active_sessions[cam_id].items() if frame_counter - data["last_seen"] > 150]
            for t in stale_tids:
                del active_sessions[cam_id][t]
                
        # 4. Evaluate Line Crossings
        entry_tids = []
        exit_tids = []
        
        if role in [CameraRole.entrance, CameraRole.bidirectional] and entry_line:
            crossed_in, crossed_out = entry_line.trigger(detections)
            for idx, tid in enumerate(tracker_ids):
                if crossed_in[idx] or crossed_out[idx]:
                    entry_tids.append(tid)
                    
        if role in [CameraRole.exit, CameraRole.bidirectional] and exit_line:
            crossed_in, crossed_out = exit_line.trigger(detections)
            for idx, tid in enumerate(tracker_ids):
                if crossed_in[idx] or crossed_out[idx]:
                    exit_tids.append(tid)
                    
        # 5. Database Logic
        if entry_tids or exit_tids:
            db = SessionLocal()
            try:
                # Fetch camera speed limit
                camera = db.query(Camera).filter(Camera.id == cam_id).first()
                speed_limit = camera.speed_limit_kmh if camera else 30
                
                with session_lock:
                    for tid in entry_tids:
                        session_data = active_sessions[cam_id].get(tid, {})
                        final_plate = get_mode(session_data.get("plate_reads", []))
                        confidences = session_data.get("plate_confidences", [])
                        avg_conf = sum(confidences) / len(confidences) if confidences else 90.0
                        v_type = session_data.get("vehicle_type", "Car")
                        
                        print(f"[{name}] 🚀 [ENTRY] Tracker ID {tid}. Plate: {final_plate}")
                        
                        is_blacklisted = final_plate in BLACKLISTED_PLATES
                        
                        # Generate random color for display purposes
                        colors = ["Black", "White", "Grey", "Silver", "Red", "Blue"]
                        color_val = np.random.choice(colors)
                        
                        new_log = PremiseAccessLog(
                            camera_id=cam_id,
                            tracker_id=tid,
                            license_plate=final_plate,
                            ocr_confidence=avg_conf,
                            vehicle_type=v_type,
                            vehicle_color=color_val,
                            image_url=f"https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=600&auto=format&fit=crop&q=80",
                            entry_time=datetime.utcnow(),
                            is_violation=is_blacklisted,
                            is_active=True
                        )
                        db.add(new_log)
                        db.flush() # Populate visit_id
                        
                        if is_blacklisted:
                            new_violation = Violation(
                                event_id=new_log.visit_id,
                                license_plate=final_plate,
                                violation_type="BLACKLISTED",
                                recorded_value=0.0,
                                zone_limit=0.0,
                                severity_level="CRITICAL",
                                status="UNRESOLVED",
                                created_at=datetime.utcnow()
                            )
                            db.add(new_violation)
                        
                    for tid in exit_tids:
                        session_data = active_sessions[cam_id].get(tid, {})
                        final_plate = get_mode(session_data.get("plate_reads", []))
                        print(f"[{name}] 🛑 [EXIT] Tracker ID {tid}. Plate: {final_plate}")
                        
                        active_visit = db.query(PremiseAccessLog).filter(
                            PremiseAccessLog.license_plate == final_plate,
                            PremiseAccessLog.is_active == True,
                            PremiseAccessLog.exit_time.is_(None)
                        ).order_by(PremiseAccessLog.entry_time.desc()).first()
                        
                        if active_visit:
                            active_visit.exit_time = datetime.utcnow()
                            active_visit.is_active = False
                            
                            # Speed calculations (assume average transit distance between entry/exit zone is 15 meters)
                            duration_sec = (active_visit.exit_time - active_visit.entry_time).total_seconds()
                            active_visit.duration_minutes = duration_sec / 60.0
                            
                            if duration_sec > 0:
                                speed_mps = 15.0 / duration_sec
                                speed_kmh = speed_mps * 3.6
                                active_visit.speed_kmh = float(speed_kmh)
                                
                                if speed_kmh > speed_limit:
                                    active_visit.is_violation = True
                                    new_violation = Violation(
                                        event_id=active_visit.visit_id,
                                        license_plate=final_plate,
                                        violation_type="SPEEDING",
                                        recorded_value=float(speed_kmh),
                                        zone_limit=float(speed_limit),
                                        severity_level="HIGH" if speed_kmh > speed_limit + 15 else "MEDIUM",
                                        status="UNRESOLVED",
                                        created_at=datetime.utcnow()
                                    )
                                    db.add(new_violation)
                        else:
                            # Log new exited visit
                            confidences = session_data.get("plate_confidences", [])
                            avg_conf = sum(confidences) / len(confidences) if confidences else 90.0
                            v_type = session_data.get("vehicle_type", "Car")
                            
                            colors = ["Black", "White", "Grey", "Silver", "Red", "Blue"]
                            color_val = np.random.choice(colors)
                            
                            new_log = PremiseAccessLog(
                                camera_id=cam_id,
                                tracker_id=tid,
                                license_plate=final_plate,
                                ocr_confidence=avg_conf,
                                vehicle_type=v_type,
                                vehicle_color=color_val,
                                image_url=f"https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=600&auto=format&fit=crop&q=80",
                                entry_time=datetime.utcnow(),
                                exit_time=datetime.utcnow(),
                                duration_minutes=0.0,
                                is_active=False
                            )
                            db.add(new_log)
                db.commit()
            except Exception as e:
                print(f"[{name}] ❌ DB Error: {e}")
                db.rollback()
            finally:
                db.close()
                
    cap.release()
    print(f"[{name}] Pipeline completed.")


def main():
    print("Fetching active camera configurations from Database...")
    db = SessionLocal()
    cameras = db.query(Camera).filter(Camera.is_active == True).all()
    
    if not cameras:
        print("No active cameras found in database. Exiting.")
        db.close()
        return
        
    print(f"Found {len(cameras)} active cameras. Starting background threads...")
    
    threads = []
    for cam in cameras:
        cam_id = str(cam.id)
        role = cam.camera_role
        
        t = threading.Thread(
            target=process_camera,
            args=(cam_id, cam.name, cam.video_source, role, cam.entry_line_normalized, cam.exit_line_normalized)
        )
        t.start()
        threads.append(t)
        
    db.close()
    
    print("🚀 All camera threads are running via Postgres ORM & YOLO11 + DeepSORT.")
    
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down pipelines...")
    finally:
        print("✅ Execution Complete.")

if __name__ == "__main__":
    main()
