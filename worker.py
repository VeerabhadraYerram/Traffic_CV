"""
worker.py — High-Performance Stream Analytics Worker for UC4 ANPR.
Adheres strictly to the Approach 2 Architecture:
- Consumes decoded video frames from Platform Ingestion over Redis Streams (streams:frames)
- Uses Consumer Groups with acknowledgment (XACK)
- Automatically sheds load by dropping stale frames (> MAX_FRAME_AGE_MS)
- Runs multi-camera tracking with independent per-camera DeepSort trackers
- Executes batched vehicle & plate inference (off request path)
- Dynamically scales visual LineZones and polygons to video resolution
- Flushes state to isolated PostgreSQL tables (uc4_*) and emits alerts to streams:alerts
- Serves non-blocking health & dynamic config API via health_api.py in background thread
"""

import os
import cv2
import time
import json
import signal
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import numpy as np
import redis
import supervision as sv
import uvicorn

from config import settings
from database import init_db, SessionLocal, clean_old_records
from models import UC4CameraConfig, UC4PremiseAccessLog, UC4Violation
from inference_client import InferenceClient
from alert_publisher import AlertPublisher
from health_api import app as health_app, telemetry
from speed_estimator import SpeedEstimator
from utils import YOLO_CLASS_MAP, BLACKLISTED_PLATES, get_mode
from platform_contracts import FrameEvent, FrameProvider

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [UC4-Worker] %(message)s"
)
logger = logging.getLogger("uc4_worker")

# Global stop flag
stop_requested = threading.Event()

def signal_handler(signum, frame):
    logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
    stop_requested.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class UC4StreamWorker:
    def __init__(self):
        self.stream_name = settings.FRAME_STREAM_NAME
        self.group_name = settings.FRAME_CONSUMER_GROUP
        self.consumer_id = settings.FRAME_CONSUMER_ID
        self.max_frame_age_ms = settings.MAX_FRAME_AGE_MS
        self.batch_size = settings.STREAM_BATCH_SIZE

        # Redis connection
        self.redis_client = None
        self._init_redis()

        # Inference and alert publishing engines
        self.inference_client = InferenceClient()
        self.alert_publisher = AlertPublisher()

        # Multi-camera state dictionaries
        self.trackers: Dict[str, sv.ByteTrack or Any] = {}
        self.sessions: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.speed_estimators: Dict[str, SpeedEstimator] = {}
        self.zones: Dict[str, Dict[str, Any]] = {}

        # Frame counter for periodic tasks
        self.loop_iterations = 0
        self.last_retention_check = time.time()

    def _init_redis(self):
        """Connects to Redis and registers the consumer group."""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False,
                socket_timeout=5.0
            )
            self.redis_client.ping()
            telemetry["redis_healthy"] = True
            logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")

            # Create consumer group if not present
            try:
                self.redis_client.xgroup_create(self.stream_name, self.group_name, id="0", make_stream=True)
                logger.info(f"✅ Created consumer group '{self.group_name}' on stream '{self.stream_name}'.")
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.debug(f"Consumer group '{self.group_name}' already exists.")
                else:
                    raise e
        except Exception as e:
            logger.error(f"❌ Redis initialization error: {e}")
            telemetry["redis_healthy"] = False

    def load_cached_cameras(self):
        """Loads cached camera line zones and polygons from the database into memory."""
        try:
            db = SessionLocal()
            cameras = db.query(UC4CameraConfig).filter(UC4CameraConfig.is_active == True).all()
            for c in cameras:
                telemetry["active_cameras"][c.camera_id] = {
                    "name": c.name,
                    "role": c.camera_role.value if hasattr(c.camera_role, "value") else c.camera_role,
                    "entry_line": c.entry_line_normalized,
                    "exit_line": c.exit_line_normalized,
                    "speed_polygon": c.speed_polygon_normalized,
                    "calibration_polygon": c.calibration_polygon_normalized,
                    "distance_between_lines_meters": c.distance_between_lines_meters,
                    "speed_limit_kmh": c.speed_limit_kmh or 30,
                    "is_active": c.is_active
                }
            db.close()
            logger.info(f"📷 Loaded {len(cameras)} active camera configurations from database.")
        except Exception as e:
            logger.error(f"Error loading cached camera configs: {e}")

    def _get_or_create_tracker(self, camera_id: str):
        """Maintains independent tracker instance per camera stream."""
        if camera_id not in self.trackers:
            from deep_sort_realtime.deepsort_tracker import DeepSort
            self.trackers[camera_id] = DeepSort(max_age=30, n_init=2, nms_max_overlap=0.5)
            self.sessions[camera_id] = {}
        return self.trackers[camera_id]

    def _setup_camera_zones(self, camera_id: str, width: int, height: int):
        """Dynamically scales normalized visual coordinates to current video resolution."""
        cam_info = telemetry["active_cameras"].get(camera_id, {})
        entry_norm = cam_info.get("entry_line")
        exit_norm = cam_info.get("exit_line")
        speed_poly_norm = cam_info.get("speed_polygon")
        cal_poly_norm = cam_info.get("calibration_polygon")
        dist_meters = cam_info.get("distance_between_lines_meters") or 15.0

        zones = {"entry_line": None, "exit_line": None, "speed_zone": None}

        if entry_norm:
            zones["entry_line"] = sv.LineZone(
                start=sv.Point(x=int(entry_norm["x1"] * width), y=int(entry_norm["y1"] * height)),
                end=sv.Point(x=int(entry_norm["x2"] * width), y=int(entry_norm["y2"] * height)),
                triggering_anchors=[sv.Position.BOTTOM_CENTER]
            )

        if exit_norm:
            zones["exit_line"] = sv.LineZone(
                start=sv.Point(x=int(exit_norm["x1"] * width), y=int(exit_norm["y1"] * height)),
                end=sv.Point(x=int(exit_norm["x2"] * width), y=int(exit_norm["y2"] * height)),
                triggering_anchors=[sv.Position.BOTTOM_CENTER]
            )

        if speed_poly_norm and len(speed_poly_norm) >= 3:
            pts = np.array([[int(p['x'] * width), int(p['y'] * height)] for p in speed_poly_norm], dtype=np.int32)
            zones["speed_zone"] = pts

        # Setup speed estimator
        if (cal_poly_norm and len(cal_poly_norm) == 4) and (camera_id not in self.speed_estimators):
            self.speed_estimators[camera_id] = SpeedEstimator(
                polygon_normalized=cal_poly_norm,
                distance_meters=dist_meters,
                frame_width=width,
                frame_height=height
            )

        self.zones[camera_id] = zones
        return zones

    def flush_completed_session(self, camera_id: str, tid: int, session: Dict[str, Any], frame_for_snapshot: np.ndarray):
        """Flushes a finished or stale track session to DB and platform alert stream."""
        reads = session.get("plate_reads", [])
        if not reads and not session.get("crossed_entry") and not session.get("crossed_exit"):
            return  # Noise / untracked object

        cam_info = telemetry["active_cameras"].get(camera_id, {})
        speed_limit = cam_info.get("speed_limit_kmh", 30)

        final_plate = get_mode(reads) if reads else "UNKNOWN"
        confidences = session.get("plate_confidences", [])
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        v_type = session.get("vehicle_type", "Car")
        entry_time = session.get("entry_time") or datetime.now(timezone.utc)
        exit_time = session.get("exit_time")
        max_speed = session.get("max_speed_kmh", 0.0)

        crossed_entry = session.get("crossed_entry", False)
        crossed_exit = session.get("crossed_exit", False)

        movement = "TRANSIT"
        if crossed_entry and not crossed_exit:
            movement = "ENTRY"
        elif crossed_exit and not crossed_entry:
            movement = "EXIT"

        is_blacklisted = final_plate in BLACKLISTED_PLATES
        is_speeding = max_speed > speed_limit
        is_violation = is_blacklisted or is_speeding

        violation_type = None
        if is_blacklisted:
            violation_type = "BLACKLISTED"
        elif is_speeding:
            violation_type = "SPEEDING"

        # 1. Save to isolated PostgreSQL database
        db = SessionLocal()
        try:
            new_log = UC4PremiseAccessLog(
                camera_id=camera_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                exit_time=exit_time,
                duration_minutes=((exit_time - entry_time).total_seconds() / 60.0) if exit_time else 0.0,
                speed_kmh=max_speed,
                is_violation=is_violation,
                is_active=False
            )
            db.add(new_log)
            db.flush()

            if is_violation:
                db.add(UC4Violation(
                    event_id=new_log.visit_id,
                    camera_id=camera_id,
                    license_plate=final_plate,
                    violation_type=violation_type,
                    recorded_value=max_speed if is_speeding else 0.0,
                    zone_limit=float(speed_limit),
                    severity_level="CRITICAL" if is_blacklisted else ("HIGH" if max_speed > speed_limit + 15 else "MEDIUM"),
                    status="UNRESOLVED"
                ))

            db.commit()
        except Exception as e:
            logger.error(f"❌ Error committing access log to DB: {e}")
            db.rollback()
        finally:
            db.close()

        # 2. Publish to platform alert stream
        self.alert_publisher.publish_event(
            camera_id=camera_id,
            tracker_id=tid,
            license_plate=final_plate,
            ocr_confidence=avg_conf,
            vehicle_type=v_type,
            movement=movement,
            speed_kmh=max_speed,
            speed_limit_kmh=speed_limit,
            is_violation=is_violation,
            violation_type=violation_type,
            snapshot_frame=frame_for_snapshot
        )
        telemetry["alerts_emitted"] += 1

    def process_frame(self, camera_id: str, frame: np.ndarray, frame_timestamp_ms: int):
        """Processes a single camera frame through detection, tracking, OCR, and rules."""
        height, width = frame.shape[:2]

        # Get or setup tracker & zones
        tracker = self._get_or_create_tracker(camera_id)
        zones = self.zones.get(camera_id) or self._setup_camera_zones(camera_id, width, height)
        cam_sessions = self.sessions[camera_id]

        # 1. Detection
        bbs = self.inference_client.detect_vehicles(frame)

        # 2. Tracking
        tracks = tracker.update_tracks(bbs, frame=frame)
        xyxys, tracker_ids, valid_tracks = [], [], []

        for track in tracks:
            if not track.is_confirmed():
                continue
            tid = int(track.track_id)
            x1, y1, x2, y2 = track.to_ltrb()
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            v_type = YOLO_CLASS_MAP.get(track.get_det_class(), "Car")

            xyxys.append([x1, y1, x2, y2])
            tracker_ids.append(tid)
            valid_tracks.append((tid, x1, y1, x2, y2, v_type))

        # 3. Speed & OCR Candidates
        ocr_candidates = []
        now_ts = time.time()

        for tid, x1, y1, x2, y2, v_type in valid_tracks:
            bottom_center = (int((x1 + x2) / 2), int(y2))
            inst_speed = 0.0

            # Calculate speed if estimator and polygon exist
            speed_estimator = self.speed_estimators.get(camera_id)
            speed_pts = zones.get("speed_zone")
            in_zone = True
            if speed_pts is not None:
                in_zone = cv2.pointPolygonTest(speed_pts, bottom_center, False) >= 0

            if speed_estimator and in_zone:
                inst_speed = speed_estimator.update_and_get_speed(tid, bottom_center, current_time=now_ts)

            if tid not in cam_sessions:
                cam_sessions[tid] = {
                    "plate_reads": [],
                    "plate_confidences": [],
                    "vehicle_type": v_type,
                    "last_seen_ts": now_ts,
                    "crossed_entry": False,
                    "crossed_exit": False,
                    "entry_time": None,
                    "exit_time": None,
                    "max_speed_kmh": inst_speed
                }
            else:
                cam_sessions[tid]["last_seen_ts"] = now_ts
                cam_sessions[tid]["vehicle_type"] = v_type
                if inst_speed > cam_sessions[tid].get("max_speed_kmh", 0):
                    cam_sessions[tid]["max_speed_kmh"] = inst_speed

            # Collect crops for plate OCR (up to 20 reads per vehicle)
            if len(cam_sessions[tid]["plate_reads"]) < 20:
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    ocr_candidates.append((tid, crop))

        # 4. Batched OCR on top candidates
        ocr_candidates.sort(key=lambda item: item[1].shape[0] * item[1].shape[1], reverse=True)
        for tid, crop in ocr_candidates[:settings.MAX_CONCURRENT_OCR]:
            result = self.inference_client.read_license_plate(crop)
            if result:
                plate_text, conf = result
                cam_sessions[tid]["plate_reads"].append(plate_text)
                cam_sessions[tid]["plate_confidences"].append(conf)

        # 5. Line Zone Triggers
        if xyxys:
            detections = sv.Detections(xyxy=np.array(xyxys), tracker_id=np.array(tracker_ids))
            entry_line = zones.get("entry_line")
            exit_line = zones.get("exit_line")

            if entry_line:
                crossed_in, crossed_out = entry_line.trigger(detections)
                for idx, tid in enumerate(tracker_ids):
                    if (crossed_in[idx] or crossed_out[idx]) and tid in cam_sessions:
                        if not cam_sessions[tid]["crossed_entry"]:
                            cam_sessions[tid]["crossed_entry"] = True
                            cam_sessions[tid]["entry_time"] = datetime.now(timezone.utc)

            if exit_line:
                crossed_in, crossed_out = exit_line.trigger(detections)
                for idx, tid in enumerate(tracker_ids):
                    if (crossed_in[idx] or crossed_out[idx]) and tid in cam_sessions:
                        if not cam_sessions[tid]["crossed_exit"]:
                            cam_sessions[tid]["crossed_exit"] = True
                            cam_sessions[tid]["exit_time"] = datetime.now(timezone.utc)

        # 6. Flush Stale Tracks (vehicles that left the camera frame)
        stale_tids = [tid for tid, s in cam_sessions.items() if now_ts - s["last_seen_ts"] > 3.0]
        for tid in stale_tids:
            session_data = cam_sessions.pop(tid)
            self.flush_completed_session(camera_id, tid, session_data, frame)

    def _get_payload_field(self, payload: dict, key: str, default=None):
        if key in payload:
            return payload[key]
        b_key = key.encode("utf-8")
        if b_key in payload:
            return payload[b_key]
        return default

    def _extract_str(self, val, default="unknown"):
        if val is None:
            return default
        if isinstance(val, str):
            return val
        if isinstance(val, (bytes, bytearray)):
            return val.decode("utf-8", errors="ignore")
        return str(val)

    def run(self):
        """Main event-driven consumer loop reading frames from Redis Streams."""
        logger.info(f"🚀 [UC4StreamWorker] Started stream ingestion loop from '{self.stream_name}'...")
        telemetry["last_processed_timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Track last processed sequence and timestamps per camera to drop duplicates
        last_frame_ts: Dict[str, int] = {}
        last_frame_seq: Dict[str, int] = {}

        while not stop_requested.is_set():
            if not self.redis_client:
                time.sleep(2.0)
                self._init_redis()
                continue

            try:
                # Read batched frames from Redis Consumer Group
                entries = self.redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_id,
                    streams={self.stream_name: ">"},
                    count=self.batch_size,
                    block=100
                )

                if not entries:
                    continue

                for stream, messages in entries:
                    for msg_id, payload in messages:
                        if stop_requested.is_set():
                            break

                        # Extract frame metadata
                        raw_data = self._get_payload_field(payload, "data")
                        frame_bytes = None
                        frame_reference = None
                        frame_provider = None

                        if raw_data is not None:
                            try:
                                data_str = self._extract_str(raw_data)
                                event = FrameEvent.model_validate_json(data_str)
                                cam_id = str(event.camera_id)
                                ts_ms = int(event.timestamp.timestamp() * 1000)
                                seq = event.frame_seq
                                frame_reference = event.frame_reference
                                frame_provider = event.frame_provider

                                # Fetch frame bytes from Redis key (Platform Pattern)
                                if frame_provider == FrameProvider.REDIS and frame_reference:
                                    frame_bytes = self.redis_client.get(frame_reference)
                            except Exception:
                                # Not a FrameEvent JSON; fallback to field extraction
                                pass

                        if frame_bytes is None:
                            cam_id_raw = self._get_payload_field(payload, "camera_id", "unknown")
                            cam_id = self._extract_str(cam_id_raw, "unknown")
                            ts_raw = self._get_payload_field(payload, "timestamp_ms")
                            ts_ms = int(ts_raw) if ts_raw else int(time.time() * 1000)
                            seq = None

                        now_ms = int(time.time() * 1000)
                        frame_age = now_ms - ts_ms

                        # 1. Backpressure / Stale Frame Drop by Age (Approach 2 Requirement)
                        if frame_age > self.max_frame_age_ms:
                            telemetry["dropped_stale_frames"] += 1
                            self.redis_client.xack(stream, self.group_name, msg_id)
                            continue

                        # 2. Duplicate or Out-of-Order Frame Detection (Approach 2 Requirement)
                        seq_raw = seq if seq is not None else (self._get_payload_field(payload, "sequence") or self._get_payload_field(payload, "frame_id"))
                        if seq_raw is not None:
                            try:
                                s = int(seq_raw)
                                last_seq = last_frame_seq.get(cam_id)
                                if last_seq is not None and s <= last_seq:
                                    telemetry["dropped_stale_frames"] += 1
                                    self.redis_client.xack(stream, self.group_name, msg_id)
                                    continue
                                last_frame_seq[cam_id] = s
                            except (ValueError, TypeError):
                                pass
                        elif ts_ms <= last_frame_ts.get(cam_id, 0):
                            telemetry["dropped_stale_frames"] += 1
                            self.redis_client.xack(stream, self.group_name, msg_id)
                            continue

                        last_frame_ts[cam_id] = ts_ms

                        # 3. Decode image from raw bytes, base64, or inlined payload
                        if frame_bytes is None:
                            frame_bytes = self._get_payload_field(payload, "frame_data") or self._get_payload_field(payload, "image")
                        
                        if not frame_bytes:
                            self.redis_client.xack(stream, self.group_name, msg_id)
                            continue

                        if isinstance(frame_bytes, str):
                            import base64
                            try:
                                frame_bytes = base64.b64decode(frame_bytes)
                            except Exception:
                                self.redis_client.xack(stream, self.group_name, msg_id)
                                continue

                        frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if frame is None:
                            self.redis_client.xack(stream, self.group_name, msg_id)
                            continue

                        # Process frame through analytics pipeline
                        self.process_frame(cam_id, frame, ts_ms)

                        # Acknowledge processed message
                        self.redis_client.xack(stream, self.group_name, msg_id)
                        telemetry["processed_frames"] += 1
                        telemetry["last_processed_timestamp"] = datetime.now(timezone.utc).isoformat()

                # Periodic retention cleanup (once every 12 hours)
                if time.time() - self.last_retention_check > 43200:
                    clean_old_records()
                    self.last_retention_check = time.time()

            except redis.exceptions.ConnectionError:
                logger.error("❌ Redis connection lost. Reconnecting...")
                telemetry["redis_healthy"] = False
                time.sleep(2.0)
                self._init_redis()
            except Exception as e:
                logger.error(f"❌ Error in worker event loop: {e}", exc_info=True)
                time.sleep(0.5)

        logger.info("🛑 [UC4StreamWorker] Ingestion loop terminated gracefully.")

def start_health_server():
    """Runs the FastAPI health and dynamic configuration API in a dedicated thread."""
    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    logger.info("Initializing UC4 Database Schema...")
    init_db()

    # Launch non-blocking health and config API
    api_thread = threading.Thread(target=start_health_server, daemon=True)
    api_thread.start()
    logger.info(f"✅ Health API running on http://0.0.0.0:{settings.SERVICE_PORT}/health")

    # Start main stream worker
    worker = UC4StreamWorker()
    worker.load_cached_cameras()
    worker.run()
