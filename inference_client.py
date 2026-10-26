"""
inference_client.py — Layer 4 Inference abstraction for UC4 ANPR.
Implements Hybrid Mode:
- Queries Layer 4 Shared GPU Inference Server when available.
- Gracefully falls back to batched local YOLOv11 and PaddleOCR.
"""

import os
import cv2
import time
import logging
import numpy as np
import httpx
from typing import List, Tuple, Dict, Any, Optional

from config import settings
from utils import YOLO_CLASS_MAP, enhance_plate, correct_indian_plate

logger = logging.getLogger(__name__)

class InferenceClient:
    def __init__(self):
        self.mode = settings.INFERENCE_MODE
        self.shared_url = settings.SHARED_INFERENCE_URL
        self.http_client = httpx.Client(timeout=1.5)
        
        # Local ML models initialized lazily or on startup
        self.yolo_model = None
        self.lp_model = None
        self.ocr_reader = None
        self._init_local_models()

    def _init_local_models(self):
        """Loads local models for local_worker mode or hybrid fallback."""
        logger.info(f"⚡ [InferenceClient] Initializing inference in mode: '{self.mode}'")
        try:
            import torch
            from ultralytics import YOLO
            from paddleocr import PaddleOCR

            engine_path = "yolo11m.engine"
            if torch.cuda.is_available() and os.path.exists(engine_path):
                self.yolo_model = YOLO(engine_path, task="detect")
                logger.info("⚡ Loaded TensorRT YOLO11 engine.")
            elif os.path.exists("yolo11m.pt"):
                self.yolo_model = YOLO("yolo11m.pt")
                logger.info("⚡ Loaded PyTorch YOLO11m weights.")
            else:
                logger.warning("⚠️ Local yolo11m model weights not found locally.")

            # License plate sub-model if present
            lp_path = os.path.join("models", "yolov8n_license_plate.pt")
            if os.path.exists(lp_path):
                self.lp_model = YOLO(lp_path)
                logger.info("⚡ Loaded dedicated license plate detector.")
            else:
                self.lp_model = None

            # PaddleOCR initialization with English model
            self.ocr_reader = PaddleOCR(use_angle_cls=True, lang=settings.PADDLE_OCR_LANG, show_log=False)
            logger.info("⚡ PaddleOCR engine initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to load local inference models: {e}")

    def detect_vehicles(self, frame: np.ndarray) -> List[Tuple[List[float], float, int]]:
        """
        Detects vehicles in the frame.
        Returns list of ([x1, y1, width, height], confidence, class_id).
        """
        # Try shared inference server if in shared or hybrid mode
        if self.mode in ("shared_server", "hybrid"):
            try:
                ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    resp = self.http_client.post(
                        f"{self.shared_url}/detect",
                        files={"file": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                        data={"classes": "1,2,3,5,7", "conf": "0.40"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        bbs = []
                        for det in data.get("detections", []):
                            x1, y1, x2, y2 = det["bbox"]
                            bbs.append(([x1, y1, x2 - x1, y2 - y1], det["confidence"], det["class_id"]))
                        return bbs
            except Exception as e:
                if self.mode == "shared_server":
                    logger.error(f"❌ Shared inference server call failed: {e}")
                    return []
                # In hybrid mode, fall back to local
                logger.debug(f"Shared inference unavailable, using local fallback: {e}")

        # Local YOLO execution
        if not self.yolo_model:
            return []

        results = self.yolo_model(frame, classes=[1, 2, 3, 5, 7], conf=0.45, verbose=False)
        bbs = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bbs.append(([x1, y1, x2 - x1, y2 - y1], float(box.conf[0]), int(box.cls[0])))
        return bbs

    def read_license_plate(self, vehicle_crop: np.ndarray) -> Optional[Tuple[str, float]]:
        """
        Detects plate region inside vehicle crop and performs OCR.
        Returns (plate_text, confidence) or None.
        """
        if vehicle_crop is None or vehicle_crop.size == 0 or not self.ocr_reader:
            return None

        plate_crop = None
        # 1. Use dedicated plate detector if available
        if self.lp_model:
            try:
                lp_results = self.lp_model(vehicle_crop, conf=0.20, verbose=False)
                for r in lp_results:
                    if len(r.boxes) > 0:
                        best_box = max(r.boxes, key=lambda b: float(b.conf[0]))
                        px1, py1, px2, py2 = best_box.xyxy[0].tolist()
                        h, w = vehicle_crop.shape[:2]
                        plate_crop = vehicle_crop[max(0, int(py1)):min(h, int(py2)),
                                                  max(0, int(px1)):min(w, int(px2))]
                        break
            except Exception as e:
                logger.warning(f"Plate model inference error: {e}")

        # Fallback to lower 30% of vehicle crop where plates are positioned
        if plate_crop is None or plate_crop.size == 0:
            h = vehicle_crop.shape[0]
            plate_crop = vehicle_crop[int(h * 0.70):, :]

        if plate_crop is None or plate_crop.size == 0:
            return None

        # 2. Image enhancement & OCR
        try:
            enhanced = enhance_plate(plate_crop)
            result = self.ocr_reader.ocr(enhanced, cls=True)
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    prob = float(line[1][1])
                    if prob > 0.20:
                        cleaned = correct_indian_plate(text)
                        if cleaned:
                            return (cleaned, prob * 100.0)
        except Exception as e:
            logger.warning(f"PaddleOCR reading error: {e}")

        return None
