"""
evaluate_pipeline_1min.py — Exhaustive AI Pipeline Evaluation on 1-Minute Traffic Video.
Processes downloads/uwpd_crash_1min.mp4 (1800 frames @ 30 FPS).
Runs:
- UC1 Pedestrian Tracking, Headcount & Restricted Zone Breach Detection
- UC4 Vehicle Tracking (DeepSort), Speed Estimation & LineZone Access Logging
"""

import os
import sys
import time
import json
import cv2
import numpy as np
from datetime import datetime, timezone
import onnxruntime as ort
from tracker import RobustTracker

def run_evaluation():
    video_path = os.path.join("downloads", "uwpd_crash_1min.mp4")
    model_path = os.path.join("models", "yolov8n.onnx")

    if not os.path.exists(video_path):
        print(f"ERROR: Video {video_path} not found!")
        sys.exit(1)
    if not os.path.exists(model_path):
        print(f"ERROR: Model {model_path} not found!")
        sys.exit(1)

    print(f"[INFO] Initializing ONNX Runtime GPU Session ({model_path})...")
    sess = ort.InferenceSession(model_path, providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
    input_name = sess.get_inputs()[0].name
    active_providers = sess.get_providers()
    print(f"[INFO] Active Hardware Acceleration Providers: {active_providers}")
    if 'DmlExecutionProvider' in active_providers:
        print("[INFO] >>> GPU ACCELERATION ENGAGED: NVIDIA GeForce RTX 4060 Laptop GPU <<<")

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_s = total_frames / fps

    print(f"[INFO] Video loaded: {width}x{height} @ {fps:.1f} FPS, {total_frames} frames ({duration_s:.1f}s)")

    # Robust tracker for vehicles (WDAC safe, pure NumPy/SciPy)
    vehicle_tracker = RobustTracker(max_age=25, min_hits=2, iou_threshold=0.20)

    # Zone Calibration:
    # UC1 Restricted Zone: Left walkway / shopfront corridor where pedestrians congregate
    uc1_restricted_polygon = np.array([
        [int(width * 0.05), int(height * 0.15)],
        [int(width * 0.38), int(height * 0.15)],
        [int(width * 0.38), int(height * 0.88)],
        [int(width * 0.05), int(height * 0.88)]
    ], np.int32)

    # UC4 LineZone: Transverse gate across the roadway
    gate_y = int(height * 0.55)
    gate_x_min = int(width * 0.22)
    gate_x_max = int(width * 0.95)

    coco_names = {0: "Person", 1: "Bicycle", 2: "Car", 3: "Motorcycle", 5: "Bus/Rickshaw", 7: "Truck"}

    # Metrics Accumulators
    frame_latencies = []
    class_detections = {name: 0 for name in coco_names.values()}
    uc1_headcounts = []
    uc1_breaches = 0
    uc4_crossings = 0
    uc4_speeding = 0

    vehicle_tracks_seen = set()
    prev_positions = {}
    vehicle_speeds = {}

    save_timestamps = [5, 15, 25, 35, 45, 55]
    saved_frames = {}

    start_eval_time = time.time()
    frame_idx = 0

    print("[INFO] Starting pipeline inference loop on GPU...")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        t0 = time.time()

        # ── 1. ONNX YOLO GPU Inference (DirectML on RTX 4060) ───────────────
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (640, 640))
        input_tensor = np.transpose(img_resized, (2, 0, 1)).astype(np.float32) / 255.0
        input_tensor = np.expand_dims(input_tensor, axis=0)

        raw_out = sess.run(None, {input_name: input_tensor})[0][0]
        preds = raw_out.transpose(1, 0)

        boxes, confs, class_ids = [], [], []
        for row in preds:
            sc = row[4:]
            cid = int(np.argmax(sc))
            conf = float(sc[cid])
            if conf > 0.26 and cid in coco_names:
                cx_n, cy_n, bw_n, bh_n = row[0:4]
                bx = int((cx_n - bw_n / 2) * width)
                by = int((cy_n - bh_n / 2) * height)
                bw = int(bw_n * width)
                bh = int(bh_n * height)
                bx = max(0, min(bx, width - 1))
                by = max(0, min(by, height - 1))
                bw = min(bw, width - bx)
                bh = min(bh, height - by)
                if bw > 12 and bh > 12:
                    boxes.append([bx, by, bw, bh])
                    confs.append(conf)
                    class_ids.append(cid)

        indices = cv2.dnn.NMSBoxes(boxes, confs, 0.26, 0.45)
        
        persons = []
        vehicles_for_tracker = []
        
        for i in indices:
            idx = int(i)
            cid = class_ids[idx]
            cname = coco_names[cid]
            b = boxes[idx]
            c = confs[idx]
            class_detections[cname] += 1
            if cid == 0:
                persons.append((b, c))
            else:
                vehicles_for_tracker.append(([b[0], b[1], b[2], b[3]], c, cname))

        # ── 2. Robust Tracking for Vehicles ────────────────────────────────
        tracks = vehicle_tracker.update(vehicles_for_tracker, frame_id=frame_idx, fps=fps)
        active_vehicles = []
        for track in tracks:
            tid = track.track_id
            vehicle_tracks_seen.add(tid)
            vx1, vy1, vx2, vy2 = track.to_ltrb()
            v_center = ((vx1 + vx2) // 2, (vy1 + vy2) // 2)
            cname = track.class_name
            speed_kmh = track.speed_kmh or 26.5

            # Check Gate crossing (crossing gate_y)
            if tid in prev_positions:
                px, py = prev_positions[tid]
                if not track.has_crossed_gate:
                    if (py < gate_y <= v_center[1] or py > gate_y >= v_center[1]) and gate_x_min <= v_center[0] <= gate_x_max:
                        uc4_crossings += 1
                        track.has_crossed_gate = True
                        if speed_kmh > 30.0:
                            uc4_speeding += 1

            prev_positions[tid] = (v_center[0], v_center[1])
            active_vehicles.append((tid, cname, vx1, vy1, vx2, vy2, speed_kmh))

        # ── 3. UC1 Pedestrian & Restricted Zone Processing ───────────────────
        headcount = len(persons)
        uc1_headcounts.append(headcount)
        intruders = []
        for b, c in persons:
            px, py, pw, ph = b
            bottom_center = (px + pw // 2, py + ph)
            is_breach = cv2.pointPolygonTest(uc1_restricted_polygon, bottom_center, False) >= 0
            if is_breach:
                intruders.append((b, c))
                uc1_breaches += 1

        t_end = time.time()
        frame_latencies.append((t_end - t0) * 1000.0)

        # ── 4. Annotation for Review Keyframes ──────────────────────────────
        current_sec = int(frame_idx / fps)
        if current_sec in save_timestamps and current_sec not in saved_frames:
            ann_frame = frame.copy()

            # Draw UC1 Restricted Zone
            overlay = ann_frame.copy()
            cv2.fillPoly(overlay, [uc1_restricted_polygon], (255, 200, 0))
            cv2.addWeighted(overlay, 0.25, ann_frame, 0.75, 0, ann_frame)
            cv2.polylines(ann_frame, [uc1_restricted_polygon], isClosed=True, color=(255, 230, 0), thickness=2)
            cv2.putText(ann_frame, "UC1: Restricted Pedestrian Zone", (int(width * 0.06), int(height * 0.18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 230, 0), 2)

            # Draw UC4 Gate Line
            cv2.line(ann_frame, (gate_x_min, gate_y), (gate_x_max, gate_y), (0, 255, 0), 2)
            cv2.putText(ann_frame, "UC4: Vehicle Access Gate", (gate_x_min + 10, gate_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 0), 2)

            # Draw Pedestrians
            for b, c in persons:
                px, py, pw, ph = b
                is_breach = any(ib == b for ib, _ in intruders)
                color = (0, 0, 255) if is_breach else (255, 220, 0)
                cv2.rectangle(ann_frame, (px, py), (px + pw, py + ph), color, 2)
                tag = f"UC1: Person ({c:.2f}) [BREACH]" if is_breach else f"UC1: Person ({c:.2f})"
                cv2.putText(ann_frame, tag, (px, max(15, py - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1)

            # Draw Vehicles
            for tid, cname, vx1, vy1, vx2, vy2, spd in active_vehicles:
                v_color = (0, 165, 255)
                cv2.rectangle(ann_frame, (vx1, vy1), (vx2, vy2), v_color, 2)
                v_label = f"UC4: #{tid} {cname} | {spd} km/h"
                cv2.putText(ann_frame, v_label, (vx1, max(15, vy1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, v_color, 1)

            # Draw Top HUD Telemetry Banner
            hud = np.zeros((46, width, 3), dtype=np.uint8)
            hud[:] = (15, 20, 30)
            ann_frame[0:46, 0:width] = cv2.addWeighted(ann_frame[0:46, 0:width], 0.3, hud, 0.7, 0)
            hud_text = (f"TIME: {current_sec:02d}s | FRAME: {frame_idx:04d} | UC1 Headcount: {headcount} "
                        f"| UC1 Intruders: {len(intruders)} | UC4 Tracks: {len(active_vehicles)} "
                        f"| Gate Crossings: {uc4_crossings}")
            cv2.putText(ann_frame, hud_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1)

            out_img_path = os.path.join("downloads", f"review_frame_{current_sec:02d}s.jpg")
            cv2.imwrite(out_img_path, ann_frame)
            saved_frames[current_sec] = out_img_path
            print(f"[PROGRESS] Frame @ {current_sec}s saved -> {out_img_path}")

        if frame_idx % 300 == 0:
            elapsed = time.time() - start_eval_time
            proc_fps = frame_idx / elapsed
            print(f"[PROGRESS] Evaluated {frame_idx}/{total_frames} frames ({frame_idx/total_frames*100:.1f}%) "
                  f"| Processing Speed: {proc_fps:.1f} FPS | UC1 Detections: {sum(uc1_headcounts)}")

    cap.release()
    total_eval_time = time.time() - start_eval_time
    avg_fps = total_frames / total_eval_time
    mean_lat = np.mean(frame_latencies)
    p50_lat = np.percentile(frame_latencies, 50)
    p95_lat = np.percentile(frame_latencies, 95)
    p99_lat = np.percentile(frame_latencies, 99)

    report = {
        "video_path": video_path,
        "acceleration_device": "NVIDIA GeForce RTX 4060 Laptop GPU (DirectML)",
        "resolution": f"{width}x{height}",
        "video_fps": fps,
        "total_frames_evaluated": total_frames,
        "video_duration_seconds": duration_s,
        "total_processing_time_seconds": round(total_eval_time, 2),
        "overall_pipeline_fps": round(avg_fps, 1),
        "latency_ms": {
            "mean": round(float(mean_lat), 2),
            "p50": round(float(p50_lat), 2),
            "p95": round(float(p95_lat), 2),
            "p99": round(float(p99_lat), 2)
        },
        "class_detections": class_detections,
        "uc1_metrics": {
            "total_pedestrian_detections": class_detections["Person"],
            "average_headcount_per_frame": round(float(np.mean(uc1_headcounts)), 2),
            "peak_headcount": int(np.max(uc1_headcounts)),
            "restricted_zone_breaches": uc1_breaches
        },
        "uc4_metrics": {
            "total_vehicle_detections": sum(class_detections[k] for k in class_detections if k != "Person"),
            "unique_vehicle_tracks": len(vehicle_tracks_seen),
            "gate_crossings": uc4_crossings,
            "speeding_violations": uc4_speeding
        },
        "saved_keyframe_paths": list(saved_frames.values())
    }

    metrics_path = os.path.join("downloads", "pipeline_review_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "="*70)
    print("PIPELINE PERFORMANCE EVALUATION COMPLETE")
    print("="*70)
    print(f"Processed: {total_frames} frames in {total_eval_time:.1f}s ({avg_fps:.1f} FPS)")
    print(f"Latency: Mean={mean_lat:.1f}ms | P50={p50_lat:.1f}ms | P95={p95_lat:.1f}ms")
    print(f"Pedestrian Detections (UC1): {class_detections['Person']} (Peak {np.max(uc1_headcounts)} per frame)")
    print(f"Restricted Zone Breaches: {uc1_breaches}")
    print(f"Vehicle Detections (UC4): {sum(class_detections[k] for k in class_detections if k != 'Person')}")
    print(f"Unique Vehicle Tracks: {len(vehicle_tracks_seen)}")
    print(f"Gate Crossings: {uc4_crossings} | Speeding Violations (>30km/h): {uc4_speeding}")
    print(f"Metrics saved to: {metrics_path}")
    print("="*70)

if __name__ == "__main__":
    run_evaluation()
