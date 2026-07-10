import os
import re
import cv2
import threading
from datetime import datetime
from collections import Counter
import numpy as np
import supervision as sv
from dotenv import load_dotenv

from database import SessionLocal
from models import Camera, PremiseAccessLog, CameraRole

# Import the new local open-source stack
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr
load_dotenv()

import torch

# Global memory for all cameras
# Structure: { camera_id: { tracker_id: { "visit_id": uuid, "plate_reads": [], "last_seen": timestamp } } }
active_sessions = {}
session_lock = threading.Lock()

# Dynamically determine the best compute device for EasyOCR
device_is_gpu = False
if torch.cuda.is_available():
    print("NVIDIA CUDA GPU Detected! Enabling for EasyOCR.")
    device_is_gpu = True
elif torch.backends.mps.is_available():
    print("Apple Silicon MPS GPU Detected! Enabling for EasyOCR.")
    device_is_gpu = True
else:
    print("No compatible GPU detected. Falling back to CPU for EasyOCR.")

print("Initializing EasyOCR Model (this might take a few seconds on first run)...")
reader = easyocr.Reader(['en'], gpu=device_is_gpu)

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def process_camera(cam_id, name, video_source, role, entry_line_norm, exit_line_norm):
    print(f"[{name}] Starting YOLO11 + DeepSORT pipeline...")
    
    # Initialize YOLO11 Model
    model = YOLO("yolo11m.pt") # This will download automatically on first run
    
    # Initialize DeepSORT Tracker (Tuned)
    tracker = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
    
    # Init DB memory for this camera
    with session_lock:
        if cam_id not in active_sessions:
            active_sessions[cam_id] = {}
            
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

        # 1. Detection (YOLOv8)
        # COCO Classes: 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
        # Note: Auto-rickshaws (3-wheelers) are usually detected as either cars (2) or motorcycles (3) by default YOLOv8.
        results = model(frame, classes=[1, 2, 3, 5, 7], conf=0.45, verbose=False)
        
        # Format for DeepSORT: [([left,top,w,h], confidence, detection_class), ...]
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
                
        # 2. Tracking (DeepSORT)
        tracks = tracker.update_tracks(bbs, frame=frame)
        
        # Build supervision Detections object so we can use LineZone
        xyxys = []
        tracker_ids = []
        valid_tracks = []
        
        for track in tracks:
            if not track.is_confirmed():
                continue
                
            tid = int(track.track_id)
            ltrb = track.to_ltrb() # left, top, right, bottom
            x1, y1, x2, y2 = ltrb
            
            # Ensure bounds are within image
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            
            xyxys.append([x1, y1, x2, y2])
            tracker_ids.append(tid)
            valid_tracks.append((tid, x1, y1, x2, y2))
            
        if not xyxys:
            continue
            
        detections = sv.Detections(
            xyxy=np.array(xyxys),
            tracker_id=np.array(tracker_ids)
        )
        
        # 3. OCR on Tracked Vehicles
        with session_lock:
            for tid, x1, y1, x2, y2 in valid_tracks:
                if tid not in active_sessions[cam_id]:
                    active_sessions[cam_id][tid] = {
                        "plate_reads": [],
                        "last_seen": frame_counter
                    }
                else:
                    active_sessions[cam_id][tid]["last_seen"] = frame_counter
                    
                # We only want to OCR if we haven't got enough confident reads yet to save CPU
                # 10 confident reads is plenty for a consensus
                if len(active_sessions[cam_id][tid]["plate_reads"]) < 10:
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        # Smart Crop: Focus on the bottom 60% of the car to find the plate
                        ch, cw = crop.shape[:2]
                        plate_crop = crop[int(ch * 0.4):, :]
                        
                        if plate_crop.size > 0:
                            ocr_results = reader.readtext(plate_crop)
                            for bbox, text, prob in ocr_results:
                                if prob > 0.3:
                                    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                    if 5 <= len(cleaned) <= 8:
                                        active_sessions[cam_id][tid]["plate_reads"].append(cleaned)
                                    
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
                with session_lock:
                    for tid in entry_tids:
                        final_plate = get_mode(active_sessions[cam_id].get(tid, {}).get("plate_reads", []))
                        print(f"[{name}] 🚀 [ENTRY] Tracker ID {tid}. Plate: {final_plate}")
                        new_log = PremiseAccessLog(
                            camera_id=cam_id,
                            tracker_id=tid,
                            license_plate=final_plate,
                            entry_time=datetime.utcnow(),
                            is_active=True
                        )
                        db.add(new_log)
                        
                    for tid in exit_tids:
                        final_plate = get_mode(active_sessions[cam_id].get(tid, {}).get("plate_reads", []))
                        print(f"[{name}] 🛑 [EXIT] Tracker ID {tid}. Plate: {final_plate}")
                        
                        active_visit = db.query(PremiseAccessLog).filter(
                            PremiseAccessLog.license_plate == final_plate,
                            PremiseAccessLog.is_active == True,
                            PremiseAccessLog.exit_time.is_(None)
                        ).order_by(PremiseAccessLog.entry_time.desc()).first()
                        
                        if active_visit:
                            active_visit.exit_time = datetime.utcnow()
                            active_visit.is_active = False
                        else:
                            new_log = PremiseAccessLog(
                                camera_id=cam_id,
                                tracker_id=tid,
                                license_plate=final_plate,
                                entry_time=datetime.utcnow(),
                                exit_time=datetime.utcnow(),
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
