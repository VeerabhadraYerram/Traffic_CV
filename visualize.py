import os
import re
import cv2
import time
from collections import Counter
import numpy as np
import supervision as sv
from dotenv import load_dotenv

from database import SessionLocal
from models import Camera, CameraRole
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr
import torch

load_dotenv()

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def main():
    print("=====================================")
    print("🎥 Starting Debug Visualization Script")
    print("=====================================")
    
    # Connect to DB to get exact lines
    db = SessionLocal()
    # Fetch the camera explicitly requested by the user
    cam = db.query(Camera).filter(Camera.name.ilike("%Test Video Bidirectional%")).first()
    
    if not cam:
        print("❌ Could not find 'Test Video Bidirectional' in the database.")
        db.close()
        return
        
    print(f"✅ Found Camera: {cam.name}")
    print(f"Role: {cam.camera_role}")
    print(f"Entry Line Config: {cam.entry_line_normalized}")
    print(f"Exit Line Config: {cam.exit_line_normalized}")
    db.close()
    
    video_path = "/app/downloads/test_video.mp4"
    output_path = "/app/downloads/output_video.mp4"
    
    if not os.path.exists(video_path):
        print(f"⚠️ Video not found: {video_path}")
        return

    device_is_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
    print(f"GPU Available for EasyOCR: {device_is_gpu}")
    
    print("Loading Models...")
    model = YOLO("yolo11m.pt")
    tracker = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Process only half the video as requested
    max_frames = total_frames // 2
    print(f"Video Dimensions: {width}x{height} | Target Frames: {max_frames} (50% of {total_frames})")
    
    # Setup Video Writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Setup Supervision Lines
    entry_line = None
    if cam.entry_line_normalized:
        entry_line = sv.LineZone(
            start=sv.Point(x=int(cam.entry_line_normalized["x1"] * width), y=int(cam.entry_line_normalized["y1"] * height)),
            end=sv.Point(x=int(cam.entry_line_normalized["x2"] * width), y=int(cam.entry_line_normalized["y2"] * height))
        )
        
    exit_line = None
    if cam.exit_line_normalized:
        exit_line = sv.LineZone(
            start=sv.Point(x=int(cam.exit_line_normalized["x1"] * width), y=int(cam.exit_line_normalized["y1"] * height)),
            end=sv.Point(x=int(cam.exit_line_normalized["x2"] * width), y=int(cam.exit_line_normalized["y2"] * height))
        )
        
    # Setup Annotators
    box_annotator = sv.BoxAnnotator(thickness=2, color_lookup=sv.ColorLookup.TRACK)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=1, text_position=sv.Position.TOP_CENTER, color_lookup=sv.ColorLookup.TRACK)
    
    # Custom colors for lines
    entry_color = sv.Color(r=0, g=255, b=0) # Green for Entry
    exit_color = sv.Color(r=0, g=0, b=255) # Red for Exit
    
    entry_line_annotator = sv.LineZoneAnnotator(thickness=3, text_thickness=2, text_scale=1, color=entry_color)
    exit_line_annotator = sv.LineZoneAnnotator(thickness=3, text_thickness=2, text_scale=1, color=exit_color)

    active_sessions = {}
    frame_counter = 0
    start_time = time.time()

    while cap.isOpened() and frame_counter < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_counter += 1
        loop_start = time.time()

        # 1. YOLO Detection
        results = model(frame, classes=[1, 2, 3, 5, 7], conf=0.45, verbose=False)
        
        bbs = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                bbs.append(([x1, y1, x2 - x1, y2 - y1], conf, cls_id))
                
        # 2. DeepSORT Tracking
        tracks = tracker.update_tracks(bbs, frame=frame)
        
        xyxys = []
        tracker_ids = []
        labels = []
        
        for track in tracks:
            if not track.is_confirmed():
                continue
            tid = int(track.track_id)
            x1, y1, x2, y2 = track.to_ltrb()
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            
            xyxys.append([x1, y1, x2, y2])
            tracker_ids.append(tid)
            
            # Memory and OCR
            if tid not in active_sessions:
                active_sessions[tid] = {"plate_reads": []}
                
            if len(active_sessions[tid]["plate_reads"]) < 10:
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    # Smart Crop: Focus on the bottom 60% of the car to find the plate
                    ch, cw = crop.shape[:2]
                    plate_crop = crop[int(ch * 0.4):, :]
                    
                    if plate_crop.size > 0:
                        ocr_results = reader.readtext(plate_crop)
                        for _, text, prob in ocr_results:
                            if prob > 0.3:
                                cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                if 5 <= len(cleaned) <= 8:
                                    active_sessions[tid]["plate_reads"].append(cleaned)
            
            current_plate = get_mode(active_sessions[tid]["plate_reads"])
            if current_plate == "UNKNOWN":
                labels.append(f"#{tid}")
            else:
                labels.append(f"#{tid} {current_plate}")
                
        # 3. Trigger Virtual Lines and Annotate
        if len(xyxys) > 0:
            detections = sv.Detections(
                xyxy=np.array(xyxys),
                tracker_id=np.array(tracker_ids)
            )
            
            # Update line counts internally
            if entry_line:
                entry_line.trigger(detections)
            if exit_line:
                exit_line.trigger(detections)
                
            # Annotate bounding boxes and labels
            frame = box_annotator.annotate(scene=frame, detections=detections)
            frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)
            
        # Annotate Lines (Always draw them even if no detections)
        if entry_line:
            frame = entry_line_annotator.annotate(frame=frame, line_counter=entry_line)
        if exit_line:
            frame = exit_line_annotator.annotate(frame=frame, line_counter=exit_line)

        # 4. Save Frame
        out.write(frame)

        if frame_counter % 25 == 0:
            elapsed = time.time() - start_time
            print(f"Processed {frame_counter}/{max_frames} frames... ({frame_counter/elapsed:.2f} fps)")

    cap.release()
    out.release()
    
    print(f"\n✅ Visualization Complete!")
    print(f"🎬 Video saved to: {output_path}")
    print(f"⏱️  Total Processing Time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
