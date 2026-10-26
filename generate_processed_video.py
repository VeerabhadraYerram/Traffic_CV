"""
generate_processed_video.py — Full Pipeline Video Processor & Renderer.
Processes the traffic camera video using:
- YOLO11 Medium on GPU (DirectML Execution Provider on NVIDIA RTX 4060)
- Class-specific NMS (preserves both riders and motorcycles/bicycles without suppression)
- Zero-drift Robust Tracker (DeepSort/Kalman filter vehicle tracking & speed estimation)
- UC1 Pedestrian Headcount & Restricted Zone Intrusion Monitoring
- UC4 Vehicle Ingress/Egress LineZone Gate Crossing & Speed Violation Logging
- Production HUD Telemetry Banner
Outputs the processed video directly into the repository.
"""

import os
import sys
import time
import cv2
import numpy as np

# Force UTF-8 on Windows stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import onnxruntime as ort
from tracker import RobustTracker

def main():
    input_video = os.path.join("downloads", "uwpd_crash_1min.mp4")
    if not os.path.exists(input_video):
        input_video = "WhatsApp Video 2026-10-26 at 2.53.54 PM.mp4"
    
    output_video = "processed_traffic_pipeline.mp4"
    model_path = "yolo11m.onnx"
    
    if not os.path.exists(model_path):
        print(f"Error: {model_path} not found!")
        sys.exit(1)
        
    print(f"=== [Innovision AI Pipeline Video Processor] ===")
    print(f"Input:  {input_video}")
    print(f"Output: {output_video}")
    print(f"Model:  {model_path} on DirectML (RTX 4060 GPU)")
    
    # Initialize ONNX Session with DirectML
    sess = ort.InferenceSession(model_path, providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
    input_name = sess.get_inputs()[0].name
    print(f"Active Execution Providers: {sess.get_providers()}")
    
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        print(f"Failed to open video: {input_video}")
        sys.exit(1)
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Source video: {width}x{height} @ {fps:.1f} FPS, {total_frames} total frames")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    if not out.isOpened():
        print(f"Failed to create video writer for {output_video}")
        sys.exit(1)
        
    # Scale factors from 640x640 model input
    sx = width / 640.0
    sy = height / 640.0
    
    # Target COCO classes
    # 0: person, 1: bicycle, 2: car, 3: motorcycle, 5: bus/rickshaw, 7: truck
    coco_map = {
        0: "Person",
        1: "Bicycle",
        2: "Car",
        3: "Motorcycle",
        5: "Bus/Rickshaw",
        7: "Truck"
    }
    
    # Tracker for vehicles
    vehicle_tracker = RobustTracker(max_age=25, min_hits=2, iou_threshold=0.20)
    
    # Calibrated Zones
    # UC1 Restricted Zone (Pedestrian Walkway / Shopfront corridor on left)
    uc1_polygon = np.array([
        [int(width * 0.05), int(height * 0.15)],
        [int(width * 0.38), int(height * 0.15)],
        [int(width * 0.38), int(height * 0.88)],
        [int(width * 0.05), int(height * 0.88)]
    ], np.int32)
    
    # UC4 Transverse Gate Line
    gate_y = int(height * 0.55)
    gate_x_min = int(width * 0.22)
    gate_x_max = int(width * 0.95)
    
    prev_positions = {}
    gate_crossings = 0
    speed_violations = 0
    speed_limit = 30.0
    
    frame_idx = 0
    start_time = time.time()
    
    print("Processing frames...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        
        # 1. GPU Preprocessing & Inference
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (640, 640))
        inp = np.expand_dims(np.transpose(img_resized, (2, 0, 1)).astype(np.float32) / 255.0, axis=0)
        
        raw_out = sess.run(None, {input_name: inp})[0][0].transpose(1, 0)
        
        # 2. Per-Class Filtering (Avoids bike/rider mutual suppression)
        by_class = {cid: [] for cid in coco_map}
        for row in raw_out:
            sc = row[4:]
            cid = int(np.argmax(sc))
            conf = float(sc[cid])
            if cid in coco_map and conf > 0.18:
                cx, cy, bw, bh = row[0:4]
                bx = int((cx - bw / 2) * sx)
                by = int((cy - bh / 2) * sy)
                bw_px = int(bw * sx)
                bh_px = int(bh * sy)
                
                # Clip to frame
                bx = max(0, min(bx, width - 1))
                by = max(0, min(by, height - 1))
                bw_px = min(bw_px, width - bx)
                bh_px = min(bh_px, height - by)
                
                if bw_px > 10 and bh_px > 10:
                    by_class[cid].append(([bx, by, bw_px, bh_px], conf))
                    
        # Apply class-specific NMS
        persons = []
        vehicles_for_tracker = []
        
        for cid, items in by_class.items():
            if not items:
                continue
            boxes = [it[0] for it in items]
            confs = [it[1] for it in items]
            idxs = cv2.dnn.NMSBoxes(boxes, confs, 0.18, 0.45)
            cname = coco_map[cid]
            for i in idxs:
                idx = int(i)
                b = boxes[idx]
                c = confs[idx]
                if cid == 0:
                    persons.append((b, c))
                else:
                    vehicles_for_tracker.append((b, c, cname))
                    
        # 3. Robust Tracking for Vehicles
        tracks = vehicle_tracker.update(vehicles_for_tracker, frame_id=frame_idx, fps=fps)
        active_vehicles = []
        for track in tracks:
            tid = track.track_id
            vx1, vy1, vx2, vy2 = track.to_ltrb()
            v_center = ((vx1 + vx2) // 2, (vy1 + vy2) // 2)
            cname = track.class_name
            speed_kmh = track.speed_kmh or 25.0
            
            # Check gate crossing
            if tid in prev_positions:
                px, py = prev_positions[tid]
                if not track.has_crossed_gate:
                    if (py < gate_y <= v_center[1] or py > gate_y >= v_center[1]) and gate_x_min <= v_center[0] <= gate_x_max:
                        gate_crossings += 1
                        track.has_crossed_gate = True
                        if speed_kmh > speed_limit:
                            speed_violations += 1
            prev_positions[tid] = v_center
            active_vehicles.append((tid, cname, vx1, vy1, vx2, vy2, speed_kmh, track.has_crossed_gate))
            
        # 4. UC1 Pedestrian & Restricted Zone Analytics
        headcount = len(persons)
        intruders = []
        for b, c in persons:
            px, py, pw, ph = b
            bottom_center = (px + pw // 2, py + ph)
            is_breach = cv2.pointPolygonTest(uc1_polygon, bottom_center, False) >= 0
            if is_breach:
                intruders.append((b, c))
                
        # 5. Visual Annotations & Overlay Rendering
        annotated = frame.copy()
        
        # Draw UC1 Restricted Zone (Semi-transparent cyan with border)
        overlay = annotated.copy()
        cv2.fillPoly(overlay, [uc1_polygon], (240, 200, 0))
        cv2.addWeighted(overlay, 0.20, annotated, 0.80, 0, annotated)
        cv2.polylines(annotated, [uc1_polygon], isClosed=True, color=(255, 230, 0), thickness=2)
        cv2.putText(annotated, "UC1: Restricted Pedestrian Walkway", (int(width * 0.06), int(height * 0.18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 230, 0), 1)
                    
        # Draw UC4 Gate Line
        gate_color = (0, 255, 120)
        cv2.line(annotated, (gate_x_min, gate_y), (gate_x_max, gate_y), gate_color, 2)
        cv2.putText(annotated, "UC4: Access LineZone Gate", (gate_x_min + 8, gate_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, gate_color, 1)
                    
        # Draw Pedestrians
        for b, c in persons:
            px, py, pw, ph = b
            is_breach = any(ib == b for ib, _ in intruders)
            color = (0, 0, 255) if is_breach else (255, 220, 0)
            cv2.rectangle(annotated, (px, py), (px + pw, py + ph), color, 2)
            tag = f"Person {c:.2f} [BREACH]" if is_breach else f"Person {c:.2f}"
            cv2.putText(annotated, tag, (px, max(12, py - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
            
        # Draw Vehicles
        for tid, cname, vx1, vy1, vx2, vy2, spd, crossed in active_vehicles:
            # Different color for speeding / crossed
            if spd > speed_limit:
                v_color = (0, 0, 255)  # Red for speeding
            elif crossed:
                v_color = (0, 220, 255)  # Yellow for crossed
            else:
                v_color = (0, 165, 255)  # Amber standard
                
            cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), v_color, 2)
            v_label = f"#{tid} {cname} | {spd:.1f} km/h"
            cv2.putText(annotated, v_label, (vx1, max(14, vy1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, v_color, 1)
            
        # 6. Production HUD Telemetry Banner
        hud = np.zeros((46, width, 3), dtype=np.uint8)
        hud[:] = (18, 24, 38)
        annotated[0:46, 0:width] = cv2.addWeighted(annotated[0:46, 0:width], 0.25, hud, 0.75, 0)
        
        current_sec = frame_idx / fps
        hud_left = f"TIME: {current_sec:05.1f}s | FRAME: {frame_idx:04d}/{total_frames} | UC1 Headcount: {headcount} | Breaches: {len(intruders)}"
        hud_right = f"UC4 Tracks: {len(active_vehicles)} | Gates: {gate_crossings} | Speeding: {speed_violations}"
        
        cv2.putText(annotated, hud_left, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(annotated, hud_right, (int(width * 0.58), 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)
        
        out.write(annotated)
        
        if frame_idx % 150 == 0:
            elapsed = time.time() - start_time
            rate = frame_idx / elapsed
            print(f"[{frame_idx}/{total_frames}] {frame_idx/total_frames*100:.1f}% @ {rate:.1f} FPS | UC1: {headcount} | UC4: {len(active_vehicles)}")
            
    cap.release()
    out.release()
    
    total_time = time.time() - start_time
    avg_fps = total_frames / total_time
    print(f"\n[DONE] Processing Complete in {total_time:.1f}s ({avg_fps:.1f} FPS)!")
    print(f"[OUTPUT] Video written to: {os.path.abspath(output_video)}")
    print(f"File size: {os.path.getsize(output_video) / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
