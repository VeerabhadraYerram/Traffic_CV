import os
import cv2
import time
from collections import Counter
import numpy as np
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr
import torch

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def run_benchmark(video_path, name):
    print(f"\n=====================================")
    print(f"🚀 Starting Benchmark on: {name}")
    print(f"=====================================")
    
    # We must map the path to where the container mounted the downloads folder
    container_video_path = video_path.replace("/Users/shivaniyerram/Downloads", "/app/downloads")

    if not os.path.exists(container_video_path):
        print(f"⚠️ Video not found: {container_video_path}")
        return

    # Check GPU
    device_is_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
    print(f"Device is GPU for EasyOCR: {device_is_gpu}")
    
    # Init Models
    model = YOLO("yolo11m.pt")
    tracker = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    
    cap = cv2.VideoCapture(container_video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video Dimensions: {width}x{height} | Total Frames: {total_frames}")

    # Trackers memory
    active_sessions = {}
    
    frame_counter = 0
    start_time = time.time()
    total_processing_time = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_counter += 1
        
        loop_start = time.time()

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
        
        valid_tracks = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            tid = int(track.track_id)
            x1, y1, x2, y2 = track.to_ltrb()
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            valid_tracks.append((tid, x1, y1, x2, y2))
            
        # 3. EasyOCR
        for tid, x1, y1, x2, y2 in valid_tracks:
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
                                import re
                                cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                if 5 <= len(cleaned) <= 8:
                                    active_sessions[tid]["plate_reads"].append(cleaned)
                                
        loop_end = time.time()
        total_processing_time += (loop_end - loop_start)

        if frame_counter % 50 == 0:
            print(f"[{name}] Processed {frame_counter}/{total_frames} frames. Current FPS: {frame_counter / total_processing_time:.2f}")

    cap.release()
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_fps = frame_counter / total_processing_time if total_processing_time > 0 else 0
    
    print(f"\n✅ Benchmark Complete for {name}")
    print(f"⏱️  Total Time: {total_time:.2f} seconds")
    print(f"🚀 Average Processing FPS: {avg_fps:.2f} frames/sec")
    print(f"📊 Unique Vehicles Tracked: {len(active_sessions)}")
    
    print("\nVehicle Plate Consensus:")
    for tid, data in active_sessions.items():
        plate = get_mode(data["plate_reads"])
        reads = len(data["plate_reads"])
        print(f"  - Tracker ID {tid}: {plate} (Reads: {reads})")

if __name__ == "__main__":
    run_benchmark("/app/downloads/test_video.mp4", "Test Video 1 (Short)")
