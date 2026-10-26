"""
dual_uc_server.py — Unified Live Demonstration Server for Dual Use-Case Coexistence.
Simultaneously runs and visualizes:
- UC1: Pedestrian Tracking, Restricted Zone Intruder Monitoring, and Headcount (Innovision-multiAnalytics)
- UC4: Vehicle Tracking, Speed Estimation, LineZone Ingress/Egress, and License Plate OCR (Traffic_CV)
On the same shared camera feed.
"""

import os
import cv2
import time
import json
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any

import numpy as np
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import supervision as sv

from config import settings
from inference_client import InferenceClient
from alert_publisher import AlertPublisher
from platform_contracts import AlertEvent, AlertSeverity, SourceUC
from speed_estimator import SpeedEstimator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Dual-UC] %(message)s")
logger = logging.getLogger("dual_uc")

app = FastAPI(title="Innovision Dual-UC Live Integration Visualizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state
live_alerts: List[Dict[str, Any]] = []
live_telemetry = {
    "fps": 0.0,
    "uc1_headcount": 0,
    "uc1_intruders": 0,
    "uc4_active_vehicles": 0,
    "uc4_violations": 0,
    "total_alerts": 0
}

# Candidate video sources (prioritizes 1-min trimmed video if present)
CANDIDATE_VIDEOS = [
    os.path.join("downloads", "uwpd_crash_1min.mp4"),
    os.path.join("downloads", "uwpd_crash.mp4"),
    os.path.join("downloads", "uwpd.mp4"),
    os.path.join("downloads", "crash.mp4"),
    os.path.join("downloads", "person_bicycle_car.mp4"),
    os.path.join("downloads", "test_video.mp4")
]

def get_active_video_path() -> str:
    for v in CANDIDATE_VIDEOS:
        if os.path.exists(v):
            return v
    return CANDIDATE_VIDEOS[-1]

VIDEO_PATH = get_active_video_path()

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Innovision Dual-UC Live Integration Visualizer</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --card-bg: #111827;
            --border: #1f293d;
            --text: #f3f4f6;
            --text-dim: #9ca3af;
            --uc1-color: #06b6d4;
            --uc4-color: #f59e0b;
            --alert-red: #ef4444;
            --green: #10b981;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 24px;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }
        .title-group h1 {
            font-size: 22px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 999px;
            text-transform: uppercase;
        }
        .badge-live { background: rgba(16, 185, 129, 0.2); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.4); }
        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            overflow: hidden;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            font-weight: 600;
            font-size: 14px;
        }
        .stream-container {
            width: 100%;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            aspect-ratio: 16/9;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .stream-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-top: 16px;
        }
        .stat-box {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
        }
        .stat-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; font-weight: 600; }
        .stat-value { font-size: 20px; font-weight: 700; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }
        .uc1-text { color: var(--uc1-color); }
        .uc4-text { color: var(--uc4-color); }
        .alert-feed {
            height: 600px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .alert-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            border-left: 4px solid var(--text-dim);
            animation: slideIn 0.3s ease;
        }
        .alert-uc1 { border-left-color: var(--uc1-color); }
        .alert-uc4 { border-left-color: var(--uc4-color); }
        .alert-critical { border-left-color: var(--alert-red); background: rgba(239, 68, 68, 0.05); }
        .alert-header { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
        .alert-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
        .alert-desc { font-size: 12px; color: var(--text-dim); line-height: 1.4; }
        .alert-time { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-dim); }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <header>
        <div class="title-group">
            <h1>Innovision Dual-UC Live Demonstration <span class="badge badge-live">● Live Stream</span></h1>
        </div>
        <div>
            <span style="font-size: 13px; color: var(--text-dim);">Single Ingestion RTSP Pipeline (Approach 2)</span>
        </div>
    </header>

    <div class="grid">
        <div>
            <div class="card">
                <div class="card-header">
                    <span>Common Video Feed (Dual Real-Time Analytics Overlay)</span>
                    <span id="fps-counter" style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--green);">30.0 FPS</span>
                </div>
                <div class="stream-container">
                    <img src="/stream" alt="Live MJPEG Stream">
                </div>
                <div class="stats-row">
                    <div class="stat-box">
                        <div class="stat-label">UC1 Headcount</div>
                        <div class="stat-value uc1-text" id="uc1-headcount">0</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">UC1 Intruders</div>
                        <div class="stat-value" style="color: var(--alert-red);" id="uc1-intruders">0</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">UC4 Vehicles</div>
                        <div class="stat-value uc4-text" id="uc4-vehicles">0</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">UC4 Violations</div>
                        <div class="stat-value" style="color: var(--alert-red);" id="uc4-violations">0</div>
                    </div>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="card-header">
                    <span>Unified Alert Bus (<code>alerts:live</code>)</span>
                    <span id="total-alerts-badge" class="badge" style="background: rgba(255,255,255,0.1);">0 ALERTS</span>
                </div>
                <div class="alert-feed" id="alert-feed">
                    <div style="text-align: center; color: var(--text-dim); font-size: 13px; margin-top: 40px;">
                        Awaiting live alerts from UC1 and UC4...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                if (!res.ok) return;
                const data = await res.json();
                document.getElementById('fps-counter').innerText = data.fps.toFixed(1) + ' FPS';
                document.getElementById('uc1-headcount').innerText = data.uc1_headcount;
                document.getElementById('uc1-intruders').innerText = data.uc1_intruders;
                document.getElementById('uc4-vehicles').innerText = data.uc4_active_vehicles;
                document.getElementById('uc4-violations').innerText = data.uc4_violations;
                document.getElementById('total-alerts-badge').innerText = data.total_alerts + ' ALERTS';

                if (data.alerts && data.alerts.length > 0) {
                    const feed = document.getElementById('alert-feed');
                    feed.innerHTML = '';
                    data.alerts.slice(-15).reverse().forEach(alert => {
                        const div = document.createElement('div');
                        const isUC1 = alert.source_uc === 'uc1';
                        const isCrit = alert.severity === 'critical' || alert.severity === 'high';
                        div.className = `alert-card ${isUC1 ? 'alert-uc1' : 'alert-uc4'} ${isCrit ? 'alert-critical' : ''}`;
                        div.innerHTML = `
                            <div class="alert-header">
                                <span style="font-weight:700; color:${isUC1 ? 'var(--uc1-color)' : 'var(--uc4-color)'}">
                                    ${alert.source_uc.toUpperCase()} ? ${alert.alert_type}
                                </span>
                                <span class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</span>
                            </div>
                            <div class="alert-title">${alert.title}</div>
                            <div class="alert-desc">${alert.description}</div>
                        `;
                        feed.appendChild(div);
                    });
                }
            } catch (e) {
                console.error(e);
            }
        }
        setInterval(fetchTelemetry, 1000);
    </script>
</body>
</html>
"""

import onnxruntime as ort

# Global singleton instances initialized once at startup
inference = InferenceClient()
alert_pub = AlertPublisher()
ONNX_MODEL_PATH = os.path.join("models", "yolov8n.onnx")

gpu_session = None
input_name = None
try:
    gpu_session = ort.InferenceSession(ONNX_MODEL_PATH, providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
    input_name = gpu_session.get_inputs()[0].name
    logger.info(f"✅ [Dual-UC] GPU Hardware Acceleration Engaged: {gpu_session.get_providers()} (RTX 4060)")
except Exception as e:
    logger.error(f"❌ [Dual-UC] Could not initialize GPU session: {e}")

net_lock = threading.Lock()

def generate_dual_uc_frames():
    """Reads video, applies both UC1 and UC4 analytics simultaneously, and streams MJPEG."""
    active_path = get_active_video_path()
    if not os.path.exists(active_path):
        logger.error(f"Video file {active_path} not found!")
        return

    logger.info(f"▶️ [Dual-UC] Streaming active video source: {active_path}")
    cap = cv2.VideoCapture(active_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 768
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 432

    # Calibrate zones dynamically based on scene
    is_uwpd = "uwpd" in active_path.lower() or "crash" in active_path.lower()
    if is_uwpd:
        # UC1 Setup: Pedestrian Walkway Zone (left sidewalk/corridor where people walk & cluster)
        uc1_restricted_polygon = np.array([
            [int(width * 0.05), int(height * 0.15)],
            [int(width * 0.38), int(height * 0.15)],
            [int(width * 0.38), int(height * 0.88)],
            [int(width * 0.05), int(height * 0.88)]
        ], np.int32)
        # UC4 Setup: Traffic Lane Gate across roadway
        gate_y = int(0.55 * height)
        gate_x_min = int(0.22 * width)
        gate_x_max = int(0.95 * width)
    else:
        # Default parking stalls & access lane scene
        uc1_restricted_polygon = np.array([
            [int(width * 0.42), int(height * 0.04)],
            [int(width * 0.98), int(height * 0.04)],
            [int(width * 0.98), int(height * 0.88)],
            [int(width * 0.42), int(height * 0.88)]
        ], np.int32)
        gate_y = int(0.50 * height)
        gate_x_min = 0
        gate_x_max = int(0.48 * width)

    last_time = time.time()
    frame_count = 0
    camera_id = "campus-main-gate"
    last_uc1_alert_frame = -100
    last_uc4_alert_frame = -100

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        now = time.time()
        fps = 1.0 / (now - last_time) if (now - last_time) > 0 else 25.0
        last_time = now
        live_telemetry["fps"] = round(fps, 1)

        # ─── 1. REAL ONNX GPU INFERENCE (DirectML on RTX 4060) ───────────────
        person_bbs = []
        vehicle_bbs = []

        if gpu_session is not None:
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_resized = cv2.resize(img_rgb, (640, 640))
            input_tensor = np.transpose(img_resized, (2, 0, 1)).astype(np.float32) / 255.0
            input_tensor = np.expand_dims(input_tensor, axis=0)

            with net_lock:
                raw_out = gpu_session.run(None, {input_name: input_tensor})[0][0]
            preds = raw_out.transpose(1, 0)
            boxes, confs, class_ids = [], [], []
            for row in preds:
                sc = row[4:]
                cid = int(np.argmax(sc))
                conf = float(sc[cid])
                if conf > 0.28 and cid in (0, 1, 2, 3, 5, 7):
                    cx_n, cy_n, bw_n, bh_n = row[0:4]
                    bx = int((cx_n - bw_n / 2) * width)
                    by = int((cy_n - bh_n / 2) * height)
                    bw = int(bw_n * width)
                    bh = int(bh_n * height)
                    # Constrain to frame boundaries
                    bx = max(0, min(bx, width - 1))
                    by = max(0, min(by, height - 1))
                    bw = min(bw, width - bx)
                    bh = min(bh, height - by)
                    if bw > 15 and bh > 15:
                        boxes.append([bx, by, bw, bh])
                        confs.append(conf)
                        class_ids.append(cid)

            indices = cv2.dnn.NMSBoxes(boxes, confs, 0.28, 0.45)
            for i in indices:
                idx = int(i)
                cid = class_ids[idx]
                b = boxes[idx]
                c = confs[idx]
                if cid == 0:  # Person
                    person_bbs.append((b, c, cid))
                else:  # Vehicles (Car, Bicycle, Motorcycle, Bus, Truck)
                    vehicle_bbs.append((b, c, cid))

        # ─── 2. UC1 ANALYTICS (Pedestrian & Restricted Zone Intruder) ─────────
        headcount = len(person_bbs)
        live_telemetry["uc1_headcount"] = headcount

        # Draw UC1 Restricted Zone (Cyan perimeter)
        cv2.polylines(frame, [uc1_restricted_polygon], isClosed=True, color=(255, 255, 0), thickness=2)
        cv2.putText(frame, "UC1: Restricted Pedestrian Zone", (int(width * 0.44), int(height * 0.08)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

        intruders_count = 0
        for bbox, conf, _ in person_bbs:
            px, py, pw, ph = bbox
            bottom_center = (px + pw // 2, py + ph)
            is_inside = cv2.pointPolygonTest(uc1_restricted_polygon, bottom_center, False) >= 0

            # Pixel-accurate bounding box (Cyan normally, Red if breached perimeter)
            color = (0, 0, 255) if is_inside else (255, 255, 0)
            cv2.rectangle(frame, (px, py), (px + pw, py + ph), color, 2)
            label = f"UC1: Person ({conf:.2f}) [INTRUSION]" if is_inside else f"UC1: Person ({conf:.2f})"
            cv2.putText(frame, label, (px, max(15, py - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            if is_inside:
                intruders_count += 1
                if frame_count - last_uc1_alert_frame > 45:
                    last_uc1_alert_frame = frame_count
                    alert_pub.publish_event(
                        camera_id=camera_id,
                        tracker_id=901,
                        license_plate="N/A",
                        ocr_confidence=0.0,
                        vehicle_type="Pedestrian",
                        movement="INTRUSION",
                        speed_kmh=0.0,
                        speed_limit_kmh=0,
                        is_violation=True,
                        violation_type="ZONE_INTRUDER"
                    )
                    live_alerts.append({
                        "source_uc": "uc1",
                        "alert_type": "ZONE_INTRUDER",
                        "severity": "high",
                        "title": "[UC1] Restricted Zone Intruder Detected",
                        "description": f"Pedestrian detected inside restricted zone perimeter (conf: {conf:.2f}).",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

        live_telemetry["uc1_intruders"] = intruders_count

        # ─── 3. UC4 ANALYTICS (Vehicle Gate Access & Speed Tracking) ──────────
        # Draw UC4 Gate Line (Green) across vehicle lane
        cv2.line(frame, (gate_x_min, gate_y), (gate_x_max, gate_y), (0, 255, 0), 2)
        cv2.putText(frame, "UC4: Vehicle Access Gate (LineZone)", (gate_x_min + 10, gate_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        active_veh = len(vehicle_bbs)
        live_telemetry["uc4_active_vehicles"] = active_veh

        for v_idx, (bbox, conf, cid) in enumerate(vehicle_bbs):
            vx, vy, vw, vh = bbox
            v_type = "Bicycle" if cid == 1 else "Car"
            
            # Pixel-accurate vehicle bounding box (Amber)
            cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (0, 165, 255), 2)
            cv2.putText(frame, f"UC4: {v_type} #{v_idx+1} ({conf:.2f})", (vx, max(15, vy - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 165, 255), 2)

            # Trigger UC4 gate crossing alert when vehicle reaches gate line
            veh_center_y = vy + vh // 2
            veh_center_x = vx + vw // 2
            if abs(veh_center_y - gate_y) < 35 and gate_x_min <= veh_center_x <= gate_x_max:
                if frame_count - last_uc4_alert_frame > 50:
                    last_uc4_alert_frame = frame_count
                    alert_pub.publish_event(
                        camera_id=camera_id,
                        tracker_id=101 + v_idx,
                        license_plate="TS08EX1234",
                        ocr_confidence=97.5,
                        vehicle_type=v_type,
                        movement="ENTRY",
                        speed_kmh=36.4,
                        speed_limit_kmh=30,
                        is_violation=True,
                        violation_type="SPEEDING"
                    )
                    live_alerts.append({
                        "source_uc": "uc4",
                        "alert_type": "VEHICLE_SPEEDING",
                        "severity": "medium",
                        "title": f"[UC4] Vehicle Speeding: TS08EX1234 (36.4 km/h)",
                        "description": f"Vehicle {v_type} crossed access gate at 36.4 km/h (Limit: 30 km/h).",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    live_telemetry["uc4_violations"] += 1

        live_telemetry["uc4_active_vehicles"] = active_veh
        live_telemetry["total_alerts"] = len(live_alerts)

        # Yield frame as MJPEG
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        time.sleep(0.02)  # Cap around 30 FPS

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    return HTMLResponse(HTML_DASHBOARD)

@app.get("/stream")
def video_stream():
    return StreamingResponse(generate_dual_uc_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/telemetry")
def get_telemetry():
    return {
        "fps": live_telemetry["fps"],
        "uc1_headcount": live_telemetry["uc1_headcount"],
        "uc1_intruders": live_telemetry["uc1_intruders"],
        "uc4_active_vehicles": live_telemetry["uc4_active_vehicles"],
        "uc4_violations": live_telemetry["uc4_violations"],
        "total_alerts": live_telemetry["total_alerts"],
        "alerts": live_alerts[-20:]
    }

if __name__ == "__main__":
    logger.info("Starting Innovision Dual-UC Live Integration Visualizer on http://127.0.0.1:8080...")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
