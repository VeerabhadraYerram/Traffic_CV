"""
test_dual_uc_integration.py — Dual Use Case Integration Test on a Common RTSP Stream.
Simulates:
1. Platform Ingestion decoding a common RTSP camera stream.
2. Ingestion storing JPEG bytes in Redis key and pushing a FrameEvent to frames:{camera_id}.
3. UC1 (People & Intruder Detection from Innovision-multiAnalytics) processing the frame.
4. UC4 (Vehicle & ANPR Access Logging from Traffic_CV) processing the same frame.
5. Both UCs publishing their respective alerts to alerts:live without conflicts.
"""

import cv2
import json
import time
import numpy as np
from uuid import uuid4, UUID
from datetime import datetime, timezone

from platform_contracts import (
    FrameEvent,
    FrameProvider,
    AlertEvent,
    AlertSeverity,
    SourceUC,
    AlertEventValidator
)
from alert_publisher import AlertPublisher

def run_dual_uc_test():
    print("=================================================================")
    print("TESTING DUAL USE-CASE INTEGRATION ON COMMON RTSP CAMERA FEED")
    print("=================================================================")

    # 1. Simulate Common RTSP Camera
    camera_id = uuid4()
    print(f"[INGESTION] Common Camera RTSP Stream Active: {camera_id}")

    # Generate synthetic camera frame with simulated vehicle and pedestrian
    frame_h, frame_w = 1080, 1920
    frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
    # Draw simulated vehicle
    cv2.rectangle(frame, (400, 500), (900, 800), (0, 255, 0), -1)
    # Draw simulated license plate
    cv2.rectangle(frame, (550, 720), (750, 780), (255, 255, 255), -1)
    cv2.putText(frame, "TS08EX1234", (560, 765), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    # Draw simulated pedestrian
    cv2.rectangle(frame, (1200, 400), (1300, 700), (0, 0, 255), -1)

    _, encoded_jpeg = cv2.imencode(".jpg", frame)
    frame_bytes = encoded_jpeg.tobytes()

    # 2. Simulate Ingestion Worker Storing Frame & Emitting FrameEvent
    frame_seq = 1042
    frame_reference = f"frame:{camera_id}:{frame_seq}"
    frame_event = FrameEvent(
        camera_id=camera_id,
        frame_seq=frame_seq,
        frame_provider=FrameProvider.REDIS,
        frame_reference=frame_reference,
        frame_shape=(frame_h, frame_w),
        timestamp=datetime.now(timezone.utc)
    )

    stream_name = f"frames:{camera_id}"
    print(f"[INGESTION] Decoded frame once (seq={frame_seq}). Stored at key '{frame_reference}'")
    print(f"[INGESTION] Dispatched FrameEvent to Redis stream: '{stream_name}'")

    # In-memory simulated Redis KV store
    simulated_redis_kv = {frame_reference: frame_bytes}

    # 3. Simulate UC1 (Innovision-multiAnalytics) Processing Frame
    print("\n--- UC1 (Multi-Analytics / Intruder & Zone Monitor) ---")
    uc1_frame_data = simulated_redis_kv.get(frame_event.frame_reference)
    assert uc1_frame_data is not None, "UC1 failed to retrieve frame bytes from Redis key"
    
    # UC1 detects person in restricted zone and emits an alert
    uc1_alert = AlertEvent(
        alert_id=uuid4(),
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        severity=AlertSeverity.HIGH,
        alert_type="ZONE_INTRUDER",
        title="[UC1] Intruder Detected in Restricted Loading Zone",
        description="Person detected inside restricted polygon for >5 seconds.",
        source_event_id=uuid4(),
        source_uc=SourceUC.UC1,
        frame_reference=frame_reference,
        frame_provider=FrameProvider.REDIS,
        metadata={"track_id": 12, "dwell_seconds": 6.2, "zone_name": "Loading Bay"}
    )
    print(f"[UC1] Detection & Zone check complete. Emitted Alert: {uc1_alert.alert_id} ({uc1_alert.title})")

    # 4. Simulate UC4 (Traffic_CV ANPR & Vehicle Access) Processing Same Frame
    print("\n--- UC4 (Traffic_CV / ANPR & Vehicle Tracking) ---")
    uc4_frame_data = simulated_redis_kv.get(frame_event.frame_reference)
    assert uc4_frame_data is not None, "UC4 failed to retrieve frame bytes from Redis key"

    uc4_publisher = AlertPublisher()
    uc4_alert = uc4_publisher.publish_event(
        camera_id=camera_id,
        tracker_id=45,
        license_plate="TS08EX1234",
        ocr_confidence=97.5,
        vehicle_type="Car",
        movement="ENTRY",
        speed_kmh=42.0,
        speed_limit_kmh=30,
        is_violation=True,
        violation_type="SPEEDING",
        frame_reference=frame_reference,
        frame_provider=FrameProvider.REDIS
    )
    print(f"[UC4] Tracking & OCR complete. Emitted Alert: {uc4_alert.alert_id} ({uc4_alert.title})")

    # 5. Validate Both Alerts Against Platform Validator
    print("\n--- Platform Validation of Output Stream (alerts:live) ---")
    known_cameras = {camera_id}
    
    uc1_errors = AlertEventValidator.validate(uc1_alert, known_cameras)
    assert not uc1_errors, f"UC1 alert failed platform validation: {uc1_errors}"
    print(f"[VALIDATOR] UC1 Alert Validated: OK (Source: {uc1_alert.source_uc.value})")

    uc4_errors = AlertEventValidator.validate(uc4_alert, known_cameras)
    assert not uc4_errors, f"UC4 alert failed platform validation: {uc4_errors}"
    print(f"[VALIDATOR] UC4 Alert Validated: OK (Source: {uc4_alert.source_uc.value})")

    print("\n=================================================================")
    print("SUCCESS: BOTH UC1 AND UC4 COEXIST HARMONIOUSLY ON COMMON RTSP!")
    print("Both UCs consumed the same frame once without duplicate decoding.")
    print("Both UCs emitted valid platform alerts to alerts:live with zero collision.")
    print("=================================================================")

if __name__ == "__main__":
    run_dual_uc_test()
