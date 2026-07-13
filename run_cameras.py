import os
os.environ["OMP_NUM_THREADS"] = "1"
import re
import cv2
import threading
from datetime import datetime, timezone
from collections import Counter
import numpy as np
from typing import Dict, Any
import supervision as sv
from dotenv import load_dotenv

from database import SessionLocal, init_db
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

def correct_indian_plate(text):
    # Clean text to keep only alphanumeric uppercase characters
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Valid Indian plates are typically between 7 and 11 characters long
    if not (7 <= len(cleaned) <= 11):
        return None

    # Mappings for character corrections
    letter_to_digit = {
        'O': '0', 'D': '0', 'Q': '0', 'U': '0',
        'I': '1', 'L': '1', 'T': '1', 'J': '1',
        'Z': '2', 'S': '5', 'G': '6', 'B': '8'
    }
    digit_to_letter = {
        '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'
    }

    def force_letters(s):
        return "".join(digit_to_letter.get(c, c) if c.isdigit() else c for c in s)

    def force_digits(s):
        return "".join(letter_to_digit.get(c, c) if c.isalpha() else c for c in s)

    # 1. State Code (first 2 characters must be letters)
    state = force_letters(cleaned[0:2])
    
    # 2. Number suffix (last 1 to 4 characters must be digits)
    max_num_len = min(4, len(cleaned) - 3)  # Leave at least 3 chars for state (2) + RTO (1)
    num_part = force_digits(cleaned[-max_num_len:])
    
    # The middle part is everything between the State and the Number suffix
    mid_part = cleaned[2:-max_num_len]
    
    # 3. Parse Middle Part: [RTO Code (1-2 digits)] [Series (0-3 letters)]
    if len(mid_part) == 0:
        rto = ""
        series = ""
    else:
        # Determine if RTO is 1 or 2 characters.
        # If second character looks like a digit, RTO is 2 characters; otherwise 1 character.
        if len(mid_part) >= 2:
            c2 = mid_part[1]
            is_c2_digit = c2.isdigit() or c2 in letter_to_digit
            if is_c2_digit:
                rto = force_digits(mid_part[0:2])
                series = force_letters(mid_part[2:])
            else:
                rto = force_digits(mid_part[0:1])
                series = force_letters(mid_part[1:])
        else:
            rto = force_digits(mid_part[0:1])
            series = ""

    return state + rto + series + num_part

def align_to_template(s):
    cleaned = re.sub(r'[^A-Z0-9]', '', s.upper())
    if len(cleaned) == 10:
        return cleaned
        
    if len(cleaned) == 9:
        # e.g., JH0EM8138 (9 characters) or DL3CA1234 (9 characters)
        # Check if it has: State (2 letters) + Mid (3 chars) + Num (4 digits)
        state = cleaned[0:2]
        num = cleaned[-4:]
        mid = cleaned[2:-4]
        if len(mid) == 3 and state.isalpha() and num.isdigit():
            # Split mid into digits and letters
            digits = "".join(c for c in mid if c.isdigit())
            letters = "".join(c for c in mid if c.isalpha())
            # Standard mid is 2 digits + 2 letters = 4 characters.
            # If we have 1 digit and 2 letters (e.g. 0 + EM), we pad digits to 2:
            if len(digits) == 1 and len(letters) == 2:
                return state + digits + "?" + letters + num
            # If we have 2 digits and 1 letter (e.g. 01 + E), we pad letters to 2:
            elif len(digits) == 2 and len(letters) == 1:
                return state + digits + letters + "?" + num
                
    return cleaned

def get_mode(items):
    if not items:
        return "UNKNOWN"
        
    # Align all reads using the alignment helper
    aligned_reads = []
    for item in items:
        aligned = align_to_template(item)
        if aligned:
            aligned_reads.append(aligned)
            
    if not aligned_reads:
        return Counter(items).most_common(1)[0][0]
        
    # Vote character-by-character on the aligned strings
    # Since aligned strings can be of length 10 or 11 (if RJ01ESP7199),
    # let's find the most common length of the aligned strings.
    lengths = [len(r) for r in aligned_reads]
    common_len = Counter(lengths).most_common(1)[0][0]
    
    # Filter reads to only those matching the most common length
    filtered_reads = [r for r in aligned_reads if len(r) == common_len]
    
    consensus_chars = []
    for i in range(common_len):
        chars_at_pos = [read[i] for read in filtered_reads if read[i] != "?"]
        if chars_at_pos:
            most_common_char = Counter(chars_at_pos).most_common(1)[0][0]
            consensus_chars.append(most_common_char)
        else:
            consensus_chars.append("?")
            
    consensus_str = "".join(consensus_chars)
    
    # Clean the consensus string using correct_indian_plate
    corrected = correct_indian_plate(consensus_str)
    if corrected:
        return corrected
        
    return consensus_str

def enhance_plate(crop):
    """Upscale 3x and apply CLAHE to sharpen plate crop before OCR."""
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return crop
    upscaled = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

def flush_session_to_db(cam_id: str, tid: int, session_data: Dict[str, Any],
                        name: str, speed_limit: int):
    """Write a completed tracker session to the database.
    Called when the tracker goes stale (vehicle leaves frame) or at end-of-video.
    At this point we have all accumulated OCR reads, giving us the best plate text.
    """
    crossed_entry = session_data.get("crossed_entry", False)
    crossed_exit  = session_data.get("crossed_exit",  False)

    # Only log vehicles that crossed at least one line (or if we have valid reads)
    if not crossed_entry and not crossed_exit:
        if session_data.get("plate_reads"):
            crossed_entry = True
            crossed_exit = True
        else:
            return

    final_plate = get_mode(session_data.get("plate_reads", []))
    confidences  = session_data.get("plate_confidences", [])
    avg_conf     = sum(confidences) / len(confidences) if confidences else 0.0
    v_type       = session_data.get("vehicle_type", "Car")
    entry_time   = session_data.get("entry_time")  or datetime.now(timezone.utc)
    exit_time    = session_data.get("exit_time")

    print(f"[{name}] 💾 [DB WRITE] Tracker {tid} | Plate: {final_plate} "
          f"| entry={crossed_entry} exit={crossed_exit} "
          f"| reads={len(session_data.get('plate_reads', []))} ({session_data.get('plate_reads', [])})")

    db = SessionLocal()
    try:
        is_blacklisted = final_plate in BLACKLISTED_PLATES

        if crossed_entry and not crossed_exit:
            # Vehicle entered but did not exit during this video segment
            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                is_violation=is_blacklisted,
                is_active=True
            )
            db.add(new_log)
            db.flush()
            if is_blacklisted:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="BLACKLISTED", recorded_value=0.0,
                    zone_limit=0.0, severity_level="CRITICAL",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))

        elif crossed_exit and not crossed_entry:
            # Only crossed exit (exit-only camera, or missed entry)
            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                exit_time=exit_time or datetime.now(timezone.utc),
                duration_minutes=0.0,
                is_active=False
            )
            db.add(new_log)

        else:
            # Crossed both lines — full transit
            duration_sec = (exit_time - entry_time).total_seconds() if exit_time else 0
            duration_min = duration_sec / 60.0
            speed_kmh = (15.0 / duration_sec) * 3.6 if duration_sec > 0 else 0.0
            is_speeding = speed_kmh > speed_limit

            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                exit_time=exit_time or datetime.now(timezone.utc),
                duration_minutes=duration_min,
                speed_kmh=float(speed_kmh),
                is_violation=is_blacklisted or is_speeding,
                is_active=False
            )
            db.add(new_log)
            db.flush()
            if is_blacklisted:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="BLACKLISTED", recorded_value=0.0,
                    zone_limit=0.0, severity_level="CRITICAL",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))
            if is_speeding:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="SPEEDING", recorded_value=float(speed_kmh),
                    zone_limit=float(speed_limit),
                    severity_level="HIGH" if speed_kmh > speed_limit + 15 else "MEDIUM",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))

        db.commit()
    except Exception as e:
        print(f"[{name}] ❌ DB Error flushing tracker {tid}: {e}")
        db.rollback()
    finally:
        db.close()

def process_camera(cam_id, name, video_source, role, entry_line_norm, exit_line_norm):
    print(f"[{name}] Starting YOLO11 + DeepSORT pipeline...")
    
    # Initialize YOLO11 Model
    model = YOLO("yolo11m.pt")
    
    # Initialize License Plate Detection Model (Stage 2 YOLO)
    lp_model = YOLO("models/yolov8n_license_plate.pt")
    
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
            end=sv.Point(x=int(entry_line_norm["x2"] * width), y=int(entry_line_norm["y2"] * height)),
            triggering_anchors=[sv.Position.BOTTOM_CENTER]
        )
        
    exit_line = None
    if exit_line_norm:
        exit_line = sv.LineZone(
            start=sv.Point(x=int(exit_line_norm["x1"] * width), y=int(exit_line_norm["y1"] * height)),
            end=sv.Point(x=int(exit_line_norm["x2"] * width), y=int(exit_line_norm["y2"] * height)),
            triggering_anchors=[sv.Position.BOTTOM_CENTER]
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
        # --- Phase A: collect crops (lock held briefly for dict access) ---
        ocr_jobs = []  # list of (tid, crop) to process outside the lock
        with session_lock:
            for tid, x1, y1, x2, y2, v_type in valid_tracks:
                if tid not in active_sessions[cam_id]:
                    active_sessions[cam_id][tid] = {
                        "plate_reads": [],
                        "plate_confidences": [],
                        "vehicle_type": v_type,
                        "last_seen": frame_counter,
                        "crossed_entry": False,
                        "crossed_exit":  False,
                        "entry_time":    None,
                        "exit_time":     None,
                    }
                else:
                    active_sessions[cam_id][tid]["last_seen"] = frame_counter
                    active_sessions[cam_id][tid]["vehicle_type"] = v_type

                # Only queue OCR if we still need more reads
                num_reads = len(active_sessions[cam_id][tid]["plate_reads"])
                if num_reads < 30:
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        ocr_jobs.append((tid, crop.copy()))
                        if frame_counter % 10 == 0 or frame_counter in range(70, 140):
                            print(f"[{name}] [DEBUG] Frame {frame_counter}: Queued tracker {tid} for OCR (current reads: {num_reads})")

        # --- Phase B: GPU inference OUTSIDE the lock ---
        ocr_results_map = {}  # tid -> (plate_text, confidence)
        for tid, crop in ocr_jobs:
            plate_crop = None
            lp_results = lp_model(crop, conf=0.20, verbose=False)
            for r in lp_results:
                if len(r.boxes) > 0:
                    best_box = max(r.boxes, key=lambda b: float(b.conf[0]))
                    px1, py1, px2, py2 = best_box.xyxy[0].tolist()
                    px1 = max(0, int(px1)); py1 = max(0, int(py1))
                    px2 = min(crop.shape[1], int(px2)); py2 = min(crop.shape[0], int(py2))
                    plate_crop = crop[py1:py2, px1:px2]
                    break

            # Fallback: bottom 30% of vehicle box
            is_fallback = False
            if plate_crop is None or plate_crop.size == 0:
                is_fallback = True
                ch = crop.shape[0]
                plate_crop = crop[int(ch * 0.70):, :]

            if plate_crop is not None and plate_crop.size > 0:
                enhanced = enhance_plate(plate_crop)
                reads = reader.readtext(enhanced)
                if reads:
                    print(f"[{name}] [DEBUG] Frame {frame_counter}: OCR read raw results for tid {tid}: {[(text, prob) for _, text, prob in reads]}")
                for _, text, prob in reads:
                    if prob > 0.20:
                        cleaned = correct_indian_plate(text)
                        print(f"[{name}] [DEBUG] Frame {frame_counter}: OCR text='{text}' (prob={prob:.2f}) -> cleaned='{cleaned}'")
                        if cleaned:
                            if tid not in ocr_results_map:
                                ocr_results_map[tid] = []
                            ocr_results_map[tid].append((cleaned, float(prob * 100)))
                        else:
                            print(f"[{name}] [DEBUG] Frame {frame_counter}: cleaned plate was None/empty for '{text}'")

        # --- Phase C: store results (lock held briefly) ---
        with session_lock:
            for tid, results in ocr_results_map.items():
                if tid in active_sessions[cam_id]:
                    for cleaned, conf_val in results:
                        active_sessions[cam_id][tid]["plate_reads"].append(cleaned)
                        active_sessions[cam_id][tid]["plate_confidences"].append(conf_val)
                    print(f"[{name}] [DEBUG] Frame {frame_counter}: Added {len(results)} reads for tid {tid}. Total reads: {len(active_sessions[cam_id][tid]['plate_reads'])}")

            # Flush stale trackers to DB (vehicle has left the frame — all reads are in)
            stale_tids = [
                t for t, data in active_sessions[cam_id].items()
                if frame_counter - data["last_seen"] > 60
            ]

        # DB flush happens outside the lock (it does I/O)
        if stale_tids:
            _db = SessionLocal()
            cam_row = _db.query(Camera).filter(Camera.id == cam_id).first()
            speed_limit_val = cam_row.speed_limit_kmh if cam_row else 30
            _db.close()
            for t in stale_tids:
                with session_lock:
                    session_snap = dict(active_sessions[cam_id].pop(t, {}))
                flush_session_to_db(cam_id, t, session_snap, name, speed_limit_val)
                
        # 4. Evaluate Line Crossings
        entry_tids = []
        exit_tids = []
        
        if role in [CameraRole.entrance, CameraRole.bidirectional] and entry_line:
            crossed_in, crossed_out = entry_line.trigger(detections)
            for idx, tid in enumerate(tracker_ids):
                if crossed_in[idx] or crossed_out[idx]:
                    # Ignore tiny background noise (must be at least 100x100 pixels)
                    x1, y1, x2, y2 = xyxys[idx]
                    if (x2 - x1) >= 100 and (y2 - y1) >= 100:
                        entry_tids.append(tid)
                    
        if role in [CameraRole.exit, CameraRole.bidirectional] and exit_line:
            crossed_in, crossed_out = exit_line.trigger(detections)
            for idx, tid in enumerate(tracker_ids):
                if crossed_in[idx] or crossed_out[idx]:
                    # Ignore tiny background noise (must be at least 100x100 pixels)
                    x1, y1, x2, y2 = xyxys[idx]
                    if (x2 - x1) >= 100 and (y2 - y1) >= 100:
                        exit_tids.append(tid)
                    
        # 5. Record line crossings in session memory (DB write is deferred to stale flush)
        with session_lock:
            for tid in entry_tids:
                if tid in active_sessions[cam_id]:
                    if not active_sessions[cam_id][tid]["crossed_entry"]:
                        active_sessions[cam_id][tid]["crossed_entry"] = True
                        active_sessions[cam_id][tid]["entry_time"] = datetime.now(timezone.utc)
                        print(f"[{name}] 🚀 [ENTRY recorded] Tracker {tid} — will write to DB when vehicle leaves frame")
            for tid in exit_tids:
                if tid in active_sessions[cam_id]:
                    if not active_sessions[cam_id][tid]["crossed_exit"]:
                        active_sessions[cam_id][tid]["crossed_exit"] = True
                        active_sessions[cam_id][tid]["exit_time"] = datetime.now(timezone.utc)
                        print(f"[{name}] 🛑 [EXIT recorded] Tracker {tid} — will write to DB when vehicle leaves frame")
                
    # End of video: flush any remaining sessions that crossed a line but never went stale
    _db2 = SessionLocal()
    cam_row2 = _db2.query(Camera).filter(Camera.id == cam_id).first()
    speed_limit_final = cam_row2.speed_limit_kmh if cam_row2 else 30
    _db2.close()
    with session_lock:
        for t, session_data in list(active_sessions[cam_id].items()):
            flush_session_to_db(cam_id, t, session_data, name, speed_limit_final)
        active_sessions[cam_id].clear()

    cap.release()
    print(f"[{name}] Pipeline completed.")


def main():
    import sys
    print("Ensuring database schema is up to date...")
    init_db()  # Guarantee schema migrations + camera seed before querying

    db = SessionLocal()

    # Check if a video source path argument was provided
    if len(sys.argv) > 1:
        video_arg = sys.argv[1]
        print(f"Custom video source argument provided: {video_arg}")
        
        # Get the first active camera to update its video source
        cam = db.query(Camera).filter(Camera.is_active == True).first()
        if cam:
            print(f"Updating camera '{cam.name}' ({cam.id}) video source to: {video_arg}")
            cam.video_source = video_arg
            db.commit()
        else:
            print("⚠️ No active cameras found in database to associate video source with.")
            db.close()
            return

    print("Fetching active camera configurations from Database...")
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
