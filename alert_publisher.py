"""
alert_publisher.py — Formats and publishes UC4 ANPR access and violation events
to the platform Redis alert stream (alerts:live) adhering strictly to the platform AlertEvent contract.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import cv2
import numpy as np
import redis

from config import settings
from platform_contracts import (
    AlertEvent,
    AlertSeverity,
    AlertStatus,
    FrameProvider,
    SourceUC,
    AlertEventValidator,
)

logger = logging.getLogger(__name__)

PLATFORM_ALERTS_STREAM = "alerts:live"

def _ensure_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, TypeError):
        # Deterministically convert non-UUID strings to UUID
        return uuid5(NAMESPACE_URL, f"innovision-cam:{val}")

class AlertPublisher:
    def __init__(self, stream: str = PLATFORM_ALERTS_STREAM):
        self.stream_name = stream
        self.redis_client = None
        self._connect_redis()

        # Ensure local snapshot directory exists
        os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)

    def _connect_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False,
                socket_timeout=2.0
            )
            self.redis_client.ping()
            logger.info(f"✅ [AlertPublisher] Connected to Redis alert stream: '{self.stream_name}'")
        except Exception as e:
            logger.warning(f"⚠️ [AlertPublisher] Could not connect to Redis: {e}. Alerts will be logged locally.")
            self.redis_client = None

    def save_snapshot(self, camera_id: str, tracker_id: int, plate: str, frame: np.ndarray) -> Optional[str]:
        """Saves a JPEG snapshot to local disk for platform UI rendering."""
        if frame is None or frame.size == 0:
            return None
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            folder = os.path.join(settings.SNAPSHOT_DIR, date_str, str(camera_id))
            os.makedirs(folder, exist_ok=True)

            filename = f"track_{tracker_id}_{plate}_{int(datetime.now(timezone.utc).timestamp())}.jpg"
            file_path = os.path.join(folder, filename)
            cv2.imwrite(file_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            return file_path
        except Exception as e:
            logger.error(f"Error saving vehicle snapshot: {e}")
            return None

    def publish_event(
        self,
        camera_id: Any,
        tracker_id: int,
        license_plate: str,
        ocr_confidence: float,
        vehicle_type: str,
        movement: str,
        speed_kmh: float,
        speed_limit_kmh: int,
        is_violation: bool,
        violation_type: Optional[str] = None,
        snapshot_frame: Optional[np.ndarray] = None,
        frame_reference: Optional[str] = None,
        frame_provider: Optional[FrameProvider] = None,
        domain_event_id: Optional[UUID] = None
    ) -> AlertEvent:
        """
        Builds, validates, and publishes an official platform AlertEvent.
        Uses deterministic alert_id (uuid5 of domain_event_id) so retries never create duplicate alerts.
        """
        cam_uuid = _ensure_uuid(camera_id)
        source_event_uuid = domain_event_id or uuid4()
        now = datetime.now(timezone.utc)

        # Save snapshot if frame is provided
        snapshot_path = None
        if snapshot_frame is not None:
            snapshot_path = self.save_snapshot(str(camera_id), tracker_id, license_plate, snapshot_frame)

        # Determine severity & alert_type
        if violation_type == "BLACKLISTED":
            severity = AlertSeverity.CRITICAL
            alert_type = "BLACKLISTED_VEHICLE"
            title = f"[UC4] Blacklisted Vehicle Detected: {license_plate}"
            desc = f"Vehicle {vehicle_type} with blacklisted plate {license_plate} crossed camera {cam_uuid} ({movement})."
        elif is_violation or (speed_kmh > speed_limit_kmh + 15):
            severity = AlertSeverity.HIGH
            alert_type = "VEHICLE_SPEEDING"
            title = f"[UC4] Excessive Speeding: {license_plate} ({speed_kmh:.1f} km/h)"
            desc = f"Vehicle {vehicle_type} ({license_plate}) exceeded zone limit {speed_limit_kmh} km/h by {speed_kmh - speed_limit_kmh:.1f} km/h."
        elif speed_kmh > speed_limit_kmh:
            severity = AlertSeverity.MEDIUM
            alert_type = "VEHICLE_SPEEDING"
            title = f"[UC4] Speeding Detected: {license_plate} ({speed_kmh:.1f} km/h)"
            desc = f"Vehicle {vehicle_type} ({license_plate}) recorded at {speed_kmh:.1f} km/h in a {speed_limit_kmh} km/h zone."
        else:
            severity = AlertSeverity.LOW
            alert_type = "VEHICLE_ACCESS"
            title = f"[UC4] Vehicle {movement}: {license_plate}"
            desc = f"Vehicle {vehicle_type} ({license_plate}) registered {movement} at camera {cam_uuid}."

        # Consistency rule: frame_reference and frame_provider must both be set or both None
        if frame_reference and not frame_provider:
            frame_provider = FrameProvider.REDIS
        elif not frame_reference:
            frame_provider = None

        metadata = {
            "tracker_id": tracker_id,
            "license_plate": license_plate,
            "ocr_confidence": round(ocr_confidence, 2),
            "vehicle_type": vehicle_type,
            "movement": movement,
            "speed_kmh": round(speed_kmh, 1),
            "speed_limit_kmh": speed_limit_kmh,
            "is_violation": is_violation,
            "violation_type": violation_type,
            "snapshot_path": snapshot_path
        }

        # Deterministic alert_id for platform deduplication
        alert_id = uuid5(NAMESPACE_URL, f"innovision-anpr:{alert_type}:{source_event_uuid}")

        alert = AlertEvent(
            alert_id=alert_id,
            camera_id=cam_uuid,
            timestamp=now,
            severity=severity,
            alert_type=alert_type,
            title=title[:200],
            description=desc[:2000],
            source_event_id=source_event_uuid,
            source_uc=SourceUC.UC4,
            frame_reference=frame_reference,
            frame_provider=frame_provider,
            status=AlertStatus.PENDING,
            metadata=metadata
        )

        # Publish to Redis Stream
        if self.redis_client:
            try:
                payload_json = alert.model_dump_json()
                self.redis_client.xadd(
                    self.stream_name,
                    {"data": payload_json},
                    maxlen=10000
                )
                logger.info(f"📢 [PlatformAlertPublished] {alert.alert_id} | {alert.title}")
            except Exception as e:
                logger.error(f"❌ Failed to publish alert to Redis: {e}")
                self._connect_redis()
        else:
            logger.info(f"📢 [LocalAlert] {alert.alert_id} | {alert.title}")

        return alert
