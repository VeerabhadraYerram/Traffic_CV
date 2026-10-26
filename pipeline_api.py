import os
os.environ["OMP_NUM_THREADS"] = "1"
import cv2
import time
import numpy as np
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import supervision as sv
from deep_sort_realtime.deepsort_tracker import DeepSort

from database import SessionLocal
from models import Camera, CameraRole
from speed_estimator import SpeedEstimator
from utils import YOLO_CLASS_MAP, correct_indian_plate, enhance_plate, flush_session_to_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
try:
    import torch
    from ultralytics import YOLO
    print("[INFO] Loading Global ML Models via PyTorch...")
    if torch.cuda.is_available() and os.path.exists("yolo11m.engine"):
        model = YOLO("yolo11m.engine", task="detect")
    else:
        model = YOLO("yolo11m.pt")
    device_is_gpu = torch.cuda.is_available() or (hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
except Exception as e:
    print(f"[WARN] PyTorch/YOLO unavailable ({e}). Using OpenCV DNN ONNX fallback...")
    device_is_gpu = False
    class OnnxYoloWrapper:
        def __init__(self, onnx_path):
            self.net = cv2.dnn.readNetFromONNX(onnx_path) if os.path.exists(onnx_path) else None
        def __call__(self, frame, classes=None, conf=0.35, verbose=False):
            if self.net is None:
                return []
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1.0/255.0, (640, 640), swapRB=True, crop=False)
            self.net.setInput(blob)
            preds = self.net.forward()[0].transpose(1, 0)
            boxes, confs, class_ids = [], [], []
            for row in preds:
                sc = row[4:]
                cid = int(np.argmax(sc))
                cf = float(sc[cid])
                if cf > conf and (classes is None or cid in classes):
                    cx, cy, bw, bh = row[0:4]
                    bx = int((cx - bw / 2) * w)
                    by = int((cy - bh / 2) * h)
                    bw_p = int(bw * w)
                    bh_p = int(bh * h)
                    boxes.append([bx, by, bw_p, bh_p])
                    confs.append(cf)
                    class_ids.append(cid)
            indices = cv2.dnn.NMSBoxes(boxes, confs, conf, 0.45)
            class BoxItem:
                def __init__(self, b, cf, cid):
                    self.xyxy = [[b[0], b[1], b[0]+b[2], b[1]+b[3]]]
                    self.conf = [cf]
                    self.cls = [cid]
            class ResultItem:
                def __init__(self, boxes_list):
                    self.boxes = boxes_list
            res_boxes = [BoxItem(boxes[int(i)], confs[int(i)], class_ids[int(i)]) for i in indices]
            return [ResultItem(res_boxes)]
    model = OnnxYoloWrapper("models/yolov8n.onnx")

try:
    from ultralytics import YOLO
    lp_model = YOLO("models/yolov8n_license_plate.pt")
except Exception:
    lp_model = None

try:
    from paddleocr import PaddleOCR
    reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
except Exception:
    reader = None

# Global lock for single-instance pipeline
pipeline_lock = threading.Lock()
# Event to signal the running stream to stop
stop_signal = threading.Event()

def generate_frames(cam_id: str):
    # Enforce single instance
    if not pipeline_lock.acquire(blocking=False):
        # Signal the currently running stream to stop
        print("🛑 Another stream is running. Signaling it to stop...")
        stop_signal.set()
        # Wait up to 5 seconds for it to release the lock
        acquired = pipeline_lock.acquire(timeout=5.0)
        if not acquired:
            print("❌ Timeout waiting for previous stream to stop.")
            return
            
    stop_signal.clear()
    
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.id == cam_id).first()
    if not cam:
        db.close()
        pipeline_lock.release()
        return

    name = cam.name
    video_source = cam.video_source
    role = cam.camera_role
    entry_line_norm = cam.entry_line_normalized
    exit_line_norm = cam.exit_line_normalized
    speed_polygon_normalized = cam.speed_polygon_normalized
    calibration_polygon_normalized = cam.calibration_polygon_normalized
    distance_between_lines_meters = cam.distance_between_lines_meters
    speed_limit = cam.speed_limit_kmh or 30
    db.close()

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"[{name}] ⚠️ Cannot open video source: {video_source}")
        pipeline_lock.release()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    speed_estimator = None
    cal_poly = calibration_polygon_normalized
    if not cal_poly and speed_polygon_normalized and len(speed_polygon_normalized) >= 3:
        xs = [p['x'] for p in speed_polygon_normalized]
        ys = [p['y'] for p in speed_polygon_normalized]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cal_poly = [
            {"x": min_x, "y": min_y},
            {"x": max_x, "y": min_y},
            {"x": max_x, "y": max_y},
            {"x": min_x, "y": max_y}
        ]
        
    if cal_poly and len(cal_poly) == 4:
        speed_estimator = SpeedEstimator(
            polygon_normalized=cal_poly,
            distance_meters=distance_between_lines_meters or 15.0,
            frame_width=width,
            frame_height=height
        )
        
    speed_zone = None
    if speed_polygon_normalized and len(speed_polygon_normalized) >= 3:
        pts = np.array([[int(p['x']*width), int(p['y']*height)] for p in speed_polygon_normalized], dtype=np.int32)
        speed_zone = sv.PolygonZone(polygon=pts)

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

    tracker = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
    active_sessions = {}
    frame_counter = 0

    # Annotators
    box_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.TRACK)
    label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5, color_lookup=sv.ColorLookup.TRACK)
    zone_annotator = sv.PolygonZoneAnnotator(zone=speed_zone, color=sv.Color.YELLOW) if speed_zone else None

    try:
        while cap.isOpened():
            if stop_signal.is_set():
                print(f"[{name}] 🛑 Stop signal received. Exiting generator.")
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame_counter += 1

            # 1. Detection
            results = model(frame, classes=[1, 2, 3, 5, 7], conf=0.45, verbose=False)
            bbs = []
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    bbs.append(([x1, y1, x2 - x1, y2 - y1], float(box.conf[0]), int(box.cls[0])))

            # 2. Tracking
            tracks = tracker.update_tracks(bbs, frame=frame)
            xyxys, tracker_ids, valid_tracks = [], [], []

            for track in tracks:
                if not track.is_confirmed(): continue
                tid = int(track.track_id)
                x1, y1, x2, y2 = track.to_ltrb()
                x1, y1 = max(0, int(x1)), max(0, int(y1))
                x2, y2 = min(width, int(x2)), min(height, int(y2))
                v_type = YOLO_CLASS_MAP.get(track.get_det_class(), "Car")
                
                xyxys.append([x1, y1, x2, y2])
                tracker_ids.append(tid)
                valid_tracks.append((tid, x1, y1, x2, y2, v_type))

            # Update speeds and OCR
            ocr_jobs = []
            for tid, x1, y1, x2, y2, v_type in valid_tracks:
                inst_speed = 0.0
                bottom_center = (int((x1+x2)/2), int(y2))
                
                # Check if inside speed zone
                in_zone = True
                if speed_zone:
                    # cv2 point polygon test
                    in_zone = cv2.pointPolygonTest(speed_zone.polygon, bottom_center, False) >= 0

                if speed_estimator and in_zone:
                    safe_fps = fps if fps and fps > 0 else 30.0
                    inst_speed = speed_estimator.update_and_get_speed(tid, bottom_center, current_time=frame_counter/safe_fps)
                    
                if tid not in active_sessions:
                    active_sessions[tid] = {
                        "plate_reads": [], "plate_confidences": [], "vehicle_type": v_type,
                        "last_seen": frame_counter, "crossed_entry": False, "crossed_exit": False,
                        "entry_time": None, "exit_time": None, "max_speed_kmh": inst_speed,
                        "distance_between_lines_meters": distance_between_lines_meters or 15.0
                    }
                else:
                    active_sessions[tid]["last_seen"] = frame_counter
                    active_sessions[tid]["vehicle_type"] = v_type
                    if inst_speed > active_sessions[tid].get("max_speed_kmh", 0):
                        active_sessions[tid]["max_speed_kmh"] = inst_speed

                if len(active_sessions[tid]["plate_reads"]) < 30:
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0: ocr_jobs.append((tid, crop.copy()))
            
            # Prevent CUDA OOM by limiting OCR to top 3 largest vehicles per frame
            ocr_jobs.sort(key=lambda j: j[1].shape[0] * j[1].shape[1], reverse=True)
            ocr_jobs = ocr_jobs[:3]

            # GPU OCR
            for tid, crop in ocr_jobs:
                plate_crop = None
                if lp_model:
                    lp_results = lp_model(crop, conf=0.20, verbose=False)
                    for r in lp_results:
                        if len(r.boxes) > 0:
                            best_box = max(r.boxes, key=lambda b: float(b.conf[0]))
                            px1, py1, px2, py2 = best_box.xyxy[0].tolist()
                            plate_crop = crop[max(0, int(py1)):min(crop.shape[0], int(py2)), max(0, int(px1)):min(crop.shape[1], int(px2))]
                            break
                if plate_crop is None or plate_crop.size == 0:
                    plate_crop = crop[int(crop.shape[0] * 0.70):, :]

                if plate_crop is not None and plate_crop.size > 0:
                    enhanced = enhance_plate(plate_crop)
                    result = reader.ocr(enhanced, cls=True)
                    if result and result[0]:
                        for line in result[0]:
                            text = line[1][0]
                            prob = line[1][1]
                            if prob > 0.20:
                                cleaned = correct_indian_plate(text)
                                if cleaned:
                                    active_sessions[tid]["plate_reads"].append(cleaned)
                                    active_sessions[tid]["plate_confidences"].append(float(prob * 100))

            # Database Flush (Stale)
            stale_tids = [t for t, data in active_sessions.items() if frame_counter - data["last_seen"] > 60]
            if stale_tids:
                for t in stale_tids:
                    flush_session_to_db(cam_id, t, dict(active_sessions.pop(t, {})), name, speed_limit)
                if speed_estimator:
                    speed_estimator.clean_stale_trackers(active_sessions.keys())

            # Evaluate Line Crossings
            if xyxys:
                detections = sv.Detections(xyxy=np.array(xyxys), tracker_id=np.array(tracker_ids))
                
                # Annotate Frame
                labels = []
                for idx, tid in enumerate(tracker_ids):
                    v_type = active_sessions.get(tid, {}).get("vehicle_type", "Unknown")
                    max_speed = active_sessions.get(tid, {}).get("max_speed_kmh", 0)
                    reads = active_sessions.get(tid, {}).get("plate_reads", [])
                    best_plate = max(set(reads), key=reads.count) if reads else "---"
                    labels.append(f"#{tid} {v_type} | {max_speed:.1f} km/h | {best_plate}")
                
                frame = box_annotator.annotate(scene=frame, detections=detections)
                frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)

                if role in [CameraRole.entrance, CameraRole.bidirectional] and entry_line:
                    crossed_in, crossed_out = entry_line.trigger(detections)
                    for idx, tid in enumerate(tracker_ids):
                        if (crossed_in[idx] or crossed_out[idx]) and (xyxys[idx][2] - xyxys[idx][0] >= 100):
                            if tid in active_sessions and not active_sessions[tid]["crossed_entry"]:
                                active_sessions[tid]["crossed_entry"] = True
                                active_sessions[tid]["entry_time"] = datetime.now(timezone.utc)
                    # Draw line
                    cv2.line(frame, (int(entry_line_norm["x1"]*width), int(entry_line_norm["y1"]*height)), (int(entry_line_norm["x2"]*width), int(entry_line_norm["y2"]*height)), (0, 255, 0), 2)
                            
                if role in [CameraRole.exit, CameraRole.bidirectional] and exit_line:
                    crossed_in, crossed_out = exit_line.trigger(detections)
                    for idx, tid in enumerate(tracker_ids):
                        if (crossed_in[idx] or crossed_out[idx]) and (xyxys[idx][2] - xyxys[idx][0] >= 100):
                            if tid in active_sessions and not active_sessions[tid]["crossed_exit"]:
                                active_sessions[tid]["crossed_exit"] = True
                                active_sessions[tid]["exit_time"] = datetime.now(timezone.utc)
                    # Draw line
                    cv2.line(frame, (int(exit_line_norm["x1"]*width), int(exit_line_norm["y1"]*height)), (int(exit_line_norm["x2"]*width), int(exit_line_norm["y2"]*height)), (0, 0, 255), 2)

                if speed_polygon_normalized:
                    pts = np.array([[int(p['x']*width), int(p['y']*height)] for p in speed_polygon_normalized], np.int32)
                    cv2.polylines(frame, [pts], isClosed=True, color=(255, 255, 0), thickness=2)

            # Yield MJPEG frame
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    except GeneratorExit:
        print(f"[{name}] 🛑 Client disconnected! Shutting down stream.")
    except Exception as e:
        print(f"[{name}] ❌ Stream Error: {e}")
    finally:
        print(f"[{name}] Cleaning up resources...")
        cap.release()
        for t, session_data in list(active_sessions.items()):
            flush_session_to_db(cam_id, t, session_data, name, speed_limit)
        active_sessions.clear()
        pipeline_lock.release()

@app.get("/api/stream/{cam_id}")
def stream_camera(cam_id: str, request: Request):
    return StreamingResponse(generate_frames(cam_id), media_type="multipart/x-mixed-replace; boundary=frame")
