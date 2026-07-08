import os
import re
import cv2
import threading
from datetime import datetime
from collections import Counter
import supervision as sv
from dotenv import load_dotenv

from inference.core.interfaces.stream.inference_pipeline import InferencePipeline
from database import SessionLocal
from models import Camera, PremiseAccessLog, CameraRole

load_dotenv()

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")

# Global memory for all cameras
# Structure: { camera_id: { tracker_id: { "visit_id": uuid, "plate_reads": [] } } }
active_sessions = {}
session_lock = threading.Lock()

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def make_prediction_handler(camera_id, role, entry_line, exit_line):
    # Initialize the camera's memory
    with session_lock:
        if camera_id not in active_sessions:
            active_sessions[camera_id] = {}
            
    frame_counter = 0

    def handle_predictions(predictions, video_frame):
        nonlocal frame_counter
        frame_counter += 1
        
        if frame_counter % 30 == 0:
            print(f"[{camera_id}] 🔄 Processed {frame_counter} frames...")

        if not predictions or not isinstance(predictions, dict):
            return

        tracked = predictions.get("tracked_vehicles")
        if tracked is None or not hasattr(tracked, 'tracker_id') or tracked.tracker_id is None:
            return

        # 1. Evaluate Line Crossings based on role
        entry_tracker_ids = []
        exit_tracker_ids = []
        
        if role in [CameraRole.entrance, CameraRole.bidirectional] and entry_line is not None:
            entry_crossed_in, entry_crossed_out = entry_line.trigger(tracked)
            for idx in range(len(tracked.tracker_id)):
                if entry_crossed_in[idx] or entry_crossed_out[idx]:
                    entry_tracker_ids.append(int(tracked.tracker_id[idx]))
                    
        if role in [CameraRole.exit, CameraRole.bidirectional] and exit_line is not None:
            exit_crossed_in, exit_crossed_out = exit_line.trigger(tracked)
            for idx in range(len(tracked.tracker_id)):
                if exit_crossed_in[idx] or exit_crossed_out[idx]:
                    exit_tracker_ids.append(int(tracked.tracker_id[idx]))

        # 2. Extract OCR
        raw_ocr = predictions.get("ocr_results", [])
        valid_plates = []
        
        if raw_ocr is not None:
            if hasattr(raw_ocr, 'data') and raw_ocr.data and 'text' in raw_ocr.data:
                valid_plates = [str(t) for t in raw_ocr.data['text'] if t]
            elif isinstance(raw_ocr, list):
                for item in raw_ocr:
                    if isinstance(item, str):
                        valid_plates.append(item)
                    elif isinstance(item, dict) and item.get("text"):
                        valid_plates.append(item.get("text"))
        
        cleaned_plates = [re.sub(r'[^A-Z0-9]', '', p.upper()) for p in valid_plates]
        plausible_plates = [p for p in cleaned_plates if 5 <= len(p) <= 8]

        # 3. DB interactions using SQLAlchemy
        db = SessionLocal()
        try:
            with session_lock:
                for tracker_id in entry_tracker_ids:
                    if tracker_id not in active_sessions[camera_id]:
                        print(f"[{camera_id}] 🚀 [ENTRY] Tracker ID {tracker_id}")
                        new_log = PremiseAccessLog(
                            camera_id=camera_id,
                            tracker_id=tracker_id,
                            entry_time=datetime.utcnow()
                        )
                        db.add(new_log)
                        db.commit()
                        db.refresh(new_log)
                        active_sessions[camera_id][tracker_id] = {
                            "visit_id": str(new_log.visit_id),
                            "plate_reads": []
                        }

                if plausible_plates:
                    for t_id, session_data in active_sessions[camera_id].items():
                        session_data["plate_reads"].extend(plausible_plates)

                for tracker_id in exit_tracker_ids:
                    if tracker_id in active_sessions[camera_id]:
                        session_data = active_sessions[camera_id][tracker_id]
                        final_plate = get_mode(session_data["plate_reads"])
                        
                        print(f"[{camera_id}] 🛑 [EXIT] Tracker {tracker_id}. Final Plate Consensus: {final_plate}")
                        
                        log = db.query(PremiseAccessLog).filter(PremiseAccessLog.visit_id == session_data["visit_id"]).first()
                        if log:
                            log.license_plate = final_plate
                            log.exit_time = datetime.utcnow()
                            log.is_active = False
                            db.commit()
                        
                        del active_sessions[camera_id][tracker_id]
        except Exception as e:
            print(f"[{camera_id}] ❌ DB Error: {e}")
            db.rollback()
        finally:
            db.close()

    return handle_predictions

def main():
    print("Fetching active camera configurations from Database...")
    db = SessionLocal()
    cameras = db.query(Camera).filter(Camera.is_active == True).all()
    
    if not cameras:
        print("No active cameras found in database. Exiting.")
        db.close()
        return
        
    print(f"Found {len(cameras)} active cameras. Initializing pipelines...")
    
    pipelines = []
    
    for cam in cameras:
        cam_id = str(cam.id)
        role = cam.camera_role
        
        cap = cv2.VideoCapture(cam.video_source)
        if not cap.isOpened():
            print(f"⚠️ Cannot open video source for {cam.name}. Skipping.")
            continue
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        entry_line = None
        if cam.entry_line_normalized:
            norm = cam.entry_line_normalized
            entry_line = sv.LineZone(
                start=sv.Point(x=int(norm["x1"] * width), y=int(norm["y1"] * height)),
                end=sv.Point(x=int(norm["x2"] * width), y=int(norm["y2"] * height))
            )
            
        exit_line = None
        if cam.exit_line_normalized:
            norm = cam.exit_line_normalized
            exit_line = sv.LineZone(
                start=sv.Point(x=int(norm["x1"] * width), y=int(norm["y1"] * height)),
                end=sv.Point(x=int(norm["x2"] * width), y=int(norm["y2"] * height))
            )
            
        handler = make_prediction_handler(cam_id, role, entry_line, exit_line)
        
        print(f"Starting pipeline for {cam.name} ({width}x{height}) [Role: {role.value}]")
        pipeline = InferencePipeline.init_with_workflow(
            video_reference=cam.video_source,  
            workspace_name="steves-workspace-orhfs",
            workflow_id="continuous-premise-gate-logging-1783423727157", 
            api_key=ROBOFLOW_API_KEY,
            on_prediction=handler
        )
        pipelines.append(pipeline)
        
    db.close()
    
    for p in pipelines:
        p.start()
        
    print("🚀 All camera pipelines are running concurrently via Postgres ORM.")
    
    try:
        for p in pipelines:
            p.join()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down pipelines...")
    finally:
        print("✅ Execution Complete.")

if __name__ == "__main__":
    main()
