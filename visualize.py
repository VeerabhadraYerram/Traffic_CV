'''
Traffic Camera Visualization Script

Generates a debug video (output_video.mp4) containing:
1. YOLO bounding boxes
2. OCR License Plate reads
3. Configured Entry/Exit line overlays

How to Run:
docker compose run --rm app python visualize.py
(This will automatically grab the first active camera in your database and use its video)

Optional - To run on a specific camera:
docker compose run --rm app python visualize.py --camera "Test Video Bidirectional"
'''

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
import argparse
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr
import torch

load_dotenv()

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

VALID_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", 
    "HR", "HP", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", 
    "MZ", "NL", "OD", "PB", "PY", "RJ", "SK", "TN", "TS", "TR", "UA", "UK", 
    "UP", "WB", "BH"
}

# Letter-to-number map for digit columns
L2N = {
    'I': '1', 'L': '1', 'J': '1', 'S': '5', 'O': '0', 'D': '0', 'B': '8', 'G': '6', 'Z': '2', 'T': '7'
}

# Number-to-letter map for character columns
N2L = {
    '1': 'I', '5': 'S', '0': 'O', '8': 'B', '2': 'Z', '6': 'G', '7': 'T'
}

def correct_indian_plate(text):
    text = text.strip().upper()
    
    # Strip common IND prefix (which often shifts index positions)
    if len(text) >= 3 and text[:3] in ["IND", "1ND", "IMD", "IID"]:
        text = text[3:]
        
    if len(text) < 4:
        return text
        
    chars = list(text)
    
    # 1. Pre-pass: Force expected character types at the extreme ends to assist block parsing
    for idx in [0, 1]:
        if chars[idx].isdigit():
            chars[idx] = N2L.get(chars[idx], chars[idx])
            
    last_four_start = max(2, len(text) - 4)
    for idx in range(last_four_start, len(text)):
        if chars[idx].isalpha():
            chars[idx] = L2N.get(chars[idx], chars[idx])
            
    cleaned_text = "".join(chars)
    
    # 2. Dynamic block parser: Group into alternating groups of letters and numbers
    blocks = []
    current_block = []
    current_is_digit = None
    
    for char in cleaned_text:
        is_digit = char.isdigit()
        if current_is_digit is None:
            current_is_digit = is_digit
            current_block.append(char)
        elif is_digit == current_is_digit:
            current_block.append(char)
        else:
            blocks.append(("digit" if current_is_digit else "letter", "".join(current_block)))
            current_is_digit = is_digit
            current_block.append(char)
    if current_block:
        blocks.append(("digit" if current_is_digit else "letter", "".join(current_block)))
        
    # 3. If we have exactly 4 alternating blocks, enforce strict type rules on each block
    if len(blocks) == 4 and blocks[0][0] == "letter" and blocks[1][0] == "digit" and blocks[2][0] == "letter" and blocks[3][0] == "digit":
        b0_val = blocks[0][1]
        b1_val = blocks[1][1]
        b2_val = blocks[2][1]
        b3_val = blocks[3][1]
        
        b0_corr = "".join(N2L.get(c, c) for c in b0_val)
        b1_corr = "".join(L2N.get(c, c) for c in b1_val)
        b2_corr = "".join(N2L.get(c, c) for c in b2_val)
        b3_corr = "".join(L2N.get(c, c) for c in b3_val)
        
        return b0_corr + b1_corr + b2_corr + b3_corr
        
    # 4. Fallback to positional corrector if blocks are merged or shifted
    for idx in [2, 3]:
        if chars[idx].isalpha():
            chars[idx] = L2N.get(chars[idx], chars[idx])
            
    if len(chars) >= 8:
        for idx in range(4, last_four_start):
            if chars[idx].isdigit():
                chars[idx] = N2L.get(chars[idx], chars[idx])
    else:
        for idx in range(4, len(chars)):
            if chars[idx].isalpha():
                chars[idx] = L2N.get(chars[idx], chars[idx])
                
    return "".join(chars)

def preprocess_plate_crop(crop):
    if crop is None or crop.size == 0:
        return crop
    # 1. Convert to grayscale
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # 2. Dynamic scaling: Ensure the crop is at least 300 pixels wide for OCR
    h, w = gray.shape[:2]
    if w < 300:
        scale = 300.0 / w
        resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    else:
        resized = gray
    # 3. Apply Bilateral Filter to reduce noise while keeping edges sharp
    denoised = cv2.bilateralFilter(resized, 9, 75, 75)
    # 4. Apply CLAHE to equalize contrast locally (handles glare and shadows)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(denoised)
    # 5. Apply Unsharp Masking (sharpening filter)
    blurred = cv2.GaussianBlur(equalized, (0, 0), 3)
    sharpened = cv2.addWeighted(equalized, 1.5, blurred, -0.5, 0)
    return sharpened

def get_final_plate(reads):
    if not reads:
        return "UNKNOWN"
    # Filter reads to valid length range (standard plates are 5-12 chars)
    valid_reads = [(text, prob) for text, prob in reads if 5 <= len(text) <= 12]
    if not valid_reads:
        return "UNKNOWN"
    
    # If we only have 1 or 2 reads, return the one with highest confidence
    if len(valid_reads) <= 2:
        return sorted(valid_reads, key=lambda x: x[1], reverse=True)[0][0]
        
    # Find most common length among all readings
    lengths = [len(text) for text, prob in valid_reads]
    most_common_len = Counter(lengths).most_common(1)[0][0]
    
    # Filter readings matching the most common length
    same_len_reads = [(text, prob) for text, prob in valid_reads if len(text) == most_common_len]
    
    if not same_len_reads:
        return sorted(valid_reads, key=lambda x: x[1], reverse=True)[0][0]
        
    # Column-wise/character-wise confidence-weighted voting to correct individual character errors
    final_chars = []
    for i in range(most_common_len):
        char_confidences = {}
        for text, prob in same_len_reads:
            char = text[i]
            char_confidences[char] = char_confidences.get(char, 0.0) + prob
        
        best_char = max(char_confidences, key=char_confidences.get)
        final_chars.append(best_char)
        
    candidate = "".join(final_chars)
    # Apply regional Indian Plate syntax correction rules
    return correct_indian_plate(candidate)

def main():
    print("=====================================")
    print("🎥 Starting Debug Visualization Script")
    print("=====================================")
    
    parser = argparse.ArgumentParser(description="Visualize Traffic Camera")
    parser.add_argument("--camera", type=str, help="Name of the camera to visualize (defaults to the first active camera)")
    args = parser.parse_args()

    # Connect to DB to get exact lines
    db = SessionLocal()
    
    if args.camera:
        cam = db.query(Camera).filter(Camera.name.ilike(f"%{args.camera}%")).first()
    else:
        cam = db.query(Camera).filter(Camera.is_active == True).first()
        
    if not cam:
        print("❌ Could not find an active camera in the database. Please add one first.")
        db.close()
        return
        
    print(f"✅ Found Camera: {cam.name}")
    print(f"Role: {cam.camera_role}")
    print(f"Entry Line Config: {cam.entry_line_normalized}")
    print(f"Exit Line Config: {cam.exit_line_normalized}")
    db.close()
    
    video_path = cam.video_source.strip("'\"")
    
    # Generate output path (e.g. /app/downloads/video_output.mp4)
    base_name, ext = os.path.splitext(video_path)
    output_path = f"{base_name}_output{ext}"
    
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
    
    # Setup Video Writer (using mp4v as hardware avc1 fails in Docker)
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
    
    entry_line_annotator = sv.LineZoneAnnotator(thickness=3, text_thickness=2, text_scale=1, color=entry_color, display_in_count=False, display_out_count=False)
    exit_line_annotator = sv.LineZoneAnnotator(thickness=3, text_thickness=2, text_scale=1, color=exit_color, display_in_count=False, display_out_count=False)

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
                
            # Only scan once every 3 frames to save CPU/GPU cycles, staggering vehicles
            if len(active_sessions[tid]["plate_reads"]) < 30 and (frame_counter - tid) % 3 == 0:
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    # Smart Crop: Focus on bottom 60% if large; use full crop if car is small/far away
                    ch, cw = crop.shape[:2]
                    if ch < 100:
                        plate_crop = crop
                    else:
                        plate_crop = crop[int(ch * 0.4):, :]
                    
                    if plate_crop.size > 0:
                        preprocessed_crop = preprocess_plate_crop(plate_crop)
                        ocr_results = reader.readtext(
                            preprocessed_crop,
                            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                            text_threshold=0.3,
                            low_text=0.2
                        )
                        if ocr_results:
                            # Group and sort detected text boxes (top-to-bottom for lines, left-to-right on same line)
                            sorted_results = []
                            for bbox, text, prob in ocr_results:
                                x_center = sum(pt[0] for pt in bbox) / 4.0
                                y_center = sum(pt[1] for pt in bbox) / 4.0
                                sorted_results.append((x_center, y_center, text, prob))
                            
                            # Sort by y-center (grouped in 15px bands for multi-line support) then x-center
                            sorted_results.sort(key=lambda item: (item[1] // 15, item[0]))
                            
                            joined_text = "".join(item[2] for item in sorted_results)
                            avg_prob = sum(item[3] for item in sorted_results) / len(sorted_results)
                            cleaned = re.sub(r'[^A-Z0-9]', '', joined_text.upper())
                            
                            print(f"   [Frame {frame_counter}] Tracker {tid} Multi-Box OCR: '{cleaned}' (avg conf: {avg_prob:.2f})")
                            if avg_prob > 0.15:
                                if 4 <= len(cleaned) <= 12:
                                    active_sessions[tid]["plate_reads"].append((cleaned, avg_prob))
            
            current_plate = get_final_plate(active_sessions[tid]["plate_reads"])
            if len(active_sessions[tid]["plate_reads"]) > 0 and frame_counter % 25 == 0:
                print(f" 🗳️ [Tracker {tid}] Current Consensus: {current_plate} (Total reads: {len(active_sessions[tid]['plate_reads'])})")
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
            total_entries = entry_line.in_count + entry_line.out_count
            mx = int((entry_line.vector.start.x + entry_line.vector.end.x) / 2)
            my = int((entry_line.vector.start.y + entry_line.vector.end.y) / 2) - 15
            text = f"Entries: {total_entries}"
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame, (mx - text_w // 2 - 10, my - text_h - 10), (mx + text_w // 2 + 10, my + 5), (0, 0, 0), -1)
            cv2.putText(frame, text, (mx - text_w // 2, my - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            
        if exit_line:
            frame = exit_line_annotator.annotate(frame=frame, line_counter=exit_line)
            total_exits = exit_line.in_count + exit_line.out_count
            mx = int((exit_line.vector.start.x + exit_line.vector.end.x) / 2)
            my = int((exit_line.vector.start.y + exit_line.vector.end.y) / 2) - 15
            text = f"Exits: {total_exits}"
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame, (mx - text_w // 2 - 10, my - text_h - 10), (mx + text_w // 2 + 10, my + 5), (0, 0, 0), -1)
            cv2.putText(frame, text, (mx - text_w // 2, my - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

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
