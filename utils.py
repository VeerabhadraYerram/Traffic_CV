"""
utils.py — Shared utility functions for the Traffic CV pipeline.

Contains:
- Vehicle class mapping
- Indian license plate OCR correction & consensus voting
- Plate image enhancement
- Database flush logic for completed tracker sessions
"""

import re
import cv2
import numpy as np
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Any

from database import SessionLocal
from models import Camera, PremiseAccessLog, Violation

# ─── Constants ────────────────────────────────────────────────────────────────

BLACKLISTED_PLATES = {"TS08EX1234", "AP28CH7890", "TS09FF1122"}

YOLO_CLASS_MAP = {1: "Bike", 2: "Car", 3: "Bike", 5: "Bus", 7: "Truck"}

# ─── Plate Correction ────────────────────────────────────────────────────────

VALID_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "GA", "GJ", "HR", "HP", "JH", "KA", "KL", "MP",
    "MH", "MN", "ML", "MZ", "NL", "OD", "PB", "RJ", "SK", "TN", "TS", "TR", "UP",
    "UK", "WB", "AN", "CH", "DN", "DD", "DL", "JK", "LA", "LD", "PY"
}

def clean_plate(text):
    """Clean and return an alphanumeric plate string universally without strict templates."""
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    # Filter out absolute garbage (e.g., less than 3 chars or weirdly long)
    if len(cleaned) < 3 or len(cleaned) > 15:
        return None
    return cleaned

def correct_indian_plate(text):
    """Clean and correct an OCR-read Indian license plate string using strict templates."""
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    if not (7 <= len(cleaned) <= 11):
        return None

    letter_to_digit = {
        'O': '0', 'D': '0', 'Q': '0', 'U': '0',
        'I': '1', 'L': '1', 'T': '1', 'J': '1',
        'Z': '2', 'S': '5', 'G': '6', 'B': '8'
    }
    digit_to_letter = {
        '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'
    }

    def force_letters(s):
        return "".join(digit_to_letter.get(c, c) if c.isdigit() else c for c in s)

    def force_digits(s):
        return "".join(letter_to_digit.get(c, c) if c.isalpha() else c for c in s)

    state = force_letters(cleaned[0:2])
    num_part = force_digits(cleaned[-4:])
    if len(cleaned) < 8:
        max_num_len = min(4, len(cleaned) - 3)
        num_part = force_digits(cleaned[-max_num_len:])

    mid_part = cleaned[2:-len(num_part)]

    if len(mid_part) == 0:
        rto = ""
        series = ""
    else:
        if len(mid_part) >= 2:
            c2 = mid_part[1]
            if c2.isdigit() or c2 in letter_to_digit:
                rto = force_digits(mid_part[0:2])
                series = force_letters(mid_part[2:])
            else:
                rto = force_digits(mid_part[0:1])
                series = force_letters(mid_part[1:])
        else:
            rto = force_digits(mid_part[0:1])
            series = ""
            
    return state + rto + series + num_part

def is_indian_plate(text):
    """Regex-based heuristic to check if a plate looks Indian."""
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    if len(cleaned) < 7 or len(cleaned) > 11:
        return False
    state = cleaned[:2]
    # Allow some OCR errors in state code, but mostly check structure
    letters = sum(1 for c in state if c.isalpha() or c in '0852')
    if letters >= 1 and cleaned[-2:].isdigit():
        return True
    return False

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def get_mode(items, confs=None):
    """Compute consensus plate text using Levenshtein clustering and auto-region detection."""
    if not items:
        return "UNKNOWN"
    if confs is None:
        confs = [1.0] * len(items)

    cleaned_items = []
    for item in items:
        c = clean_plate(item)
        if c: cleaned_items.append(c)
        
    if not cleaned_items:
        return Counter(items).most_common(1)[0][0]

    # Region Detection
    indian_matches = sum(1 for x in cleaned_items if is_indian_plate(x))
    is_india_region = (indian_matches / len(cleaned_items)) > 0.4
    
    processed_items = []
    processed_confs = []
    for item, conf in zip(items, confs):
        if is_india_region:
            c = correct_indian_plate(item)
        else:
            c = clean_plate(item)
        if c:
            processed_items.append(c)
            processed_confs.append(conf)

    if not processed_items:
        return Counter(cleaned_items).most_common(1)[0][0]

    # Levenshtein Clustering
    clusters = []
    for string, conf in zip(processed_items, processed_confs):
        added = False
        for cluster in clusters:
            # If distance is <= 1 (or 2 for long plates), add to cluster
            threshold = 1 if len(string) < 8 else 2
            if levenshtein_distance(string, cluster['center']) <= threshold:
                cluster['strings'].append(string)
                cluster['total_conf'] += conf
                added = True
                break
        if not added:
            clusters.append({'center': string, 'strings': [string], 'total_conf': conf})

    # Pick best cluster
    best_cluster = max(clusters, key=lambda x: x['total_conf'])
    
    # Within best cluster, pick most common string
    final_str = Counter(best_cluster['strings']).most_common(1)[0][0]
    return final_str

# ─── Image Enhancement ────────────────────────────────────────────────────────

def deskew_plate(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 200)
    
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image
    
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    plate_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            plate_contour = approx
            break
            
    if plate_contour is None:
        return image
        
    pts = plate_contour.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
        
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def single_scale_retinex(img, sigma):
    # Avoid log(0)
    retinex = np.log10(img + 1.0) - np.log10(cv2.GaussianBlur(img, (0, 0), sigma) + 1.0)
    return retinex

def apply_retinex(img):
    """Multi-Scale Retinex (MSR) for glare/shadow removal."""
    img_float = np.float64(img)
    sigmas = [15, 80, 250]
    retinex = np.zeros_like(img_float)
    for sigma in sigmas:
        retinex += single_scale_retinex(img_float, sigma)
    retinex = retinex / len(sigmas)
    
    min_val, max_val = np.min(retinex), np.max(retinex)
    if max_val - min_val == 0:
        return img
    retinex = 255 * (retinex - min_val) / (max_val - min_val)
    return np.uint8(retinex)

def enhance_plate(crop):
    """Deskew, apply Retinex (MSR), upscale 3x, and CLAHE to sharpen plate crop before OCR."""
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return crop
        
    deskewed = deskew_plate(crop)
    
    dh, dw = deskewed.shape[:2]
    if dh == 0 or dw == 0:
        deskewed = crop
        dh, dw = deskewed.shape[:2]
        
    # Apply MSR to fix lighting/glare
    msr_img = apply_retinex(deskewed)
        
    upscaled = cv2.resize(msr_img, (dw * 3, dh * 3), interpolation=cv2.INTER_CUBIC)
    
    filtered = cv2.bilateralFilter(upscaled, 9, 75, 75)
    gray = cv2.cvtColor(filtered, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

# ─── Database Flush ───────────────────────────────────────────────────────────

def flush_session_to_db(cam_id: str, tid: int, session_data: Dict[str, Any],
                        name: str, speed_limit: int):
    """Write a completed tracker session to the database.
    Called when the tracker goes stale (vehicle leaves frame) or at end-of-video.
    """
    crossed_entry = session_data.get("crossed_entry", False)
    crossed_exit  = session_data.get("crossed_exit",  False)

    if not crossed_entry and not crossed_exit:
        if session_data.get("plate_reads"):
            crossed_entry = True
            crossed_exit = True
        else:
            return

    final_plate = get_mode(session_data.get("plate_reads", []), session_data.get("plate_confidences", []))
    confidences  = session_data.get("plate_confidences", [])
    avg_conf     = sum(confidences) / len(confidences) if confidences else 0.0
    v_type       = session_data.get("vehicle_type", "Car")
    entry_time   = session_data.get("entry_time")  or datetime.now(timezone.utc)
    exit_time    = session_data.get("exit_time")

    print(f"[{name}] 💾 [DB WRITE] Tracker {tid} | Plate: {final_plate} "
          f"| entry={crossed_entry} exit={crossed_exit} "
          f"| reads={len(session_data.get('plate_reads', []))}")

    db = SessionLocal()
    try:
        is_blacklisted = final_plate in BLACKLISTED_PLATES

        if crossed_entry and not crossed_exit:
            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                is_violation=is_blacklisted,
                is_active=True
            )
            db.add(new_log)
            db.flush()
            if is_blacklisted:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="BLACKLISTED", recorded_value=0.0,
                    zone_limit=0.0, severity_level="CRITICAL",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))

        elif crossed_exit and not crossed_entry:
            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                exit_time=exit_time or datetime.now(timezone.utc),
                duration_minutes=0.0,
                is_active=False
            )
            db.add(new_log)

        else:
            duration_sec = (exit_time - entry_time).total_seconds() if exit_time else 0
            duration_min = duration_sec / 60.0
            max_inst_speed = session_data.get("max_speed_kmh", 0.0)
            if max_inst_speed > 0:
                speed_kmh = max_inst_speed
            else:
                line_dist = session_data.get("distance_between_lines_meters", 15.0)
                speed_kmh = (line_dist / duration_sec) * 3.6 if duration_sec > 0 else 0.0

            is_speeding = speed_kmh > speed_limit

            new_log = PremiseAccessLog(
                camera_id=cam_id,
                tracker_id=tid,
                license_plate=final_plate,
                ocr_confidence=avg_conf,
                vehicle_type=v_type,
                vehicle_color="Unknown",
                entry_time=entry_time,
                exit_time=exit_time or datetime.now(timezone.utc),
                duration_minutes=duration_min,
                speed_kmh=float(speed_kmh),
                is_violation=is_blacklisted or is_speeding,
                is_active=False
            )
            db.add(new_log)
            db.flush()
            if is_blacklisted:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="BLACKLISTED", recorded_value=0.0,
                    zone_limit=0.0, severity_level="CRITICAL",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))
            if is_speeding:
                db.add(Violation(
                    event_id=new_log.visit_id, license_plate=final_plate,
                    violation_type="SPEEDING", recorded_value=float(speed_kmh),
                    zone_limit=float(speed_limit),
                    severity_level="HIGH" if speed_kmh > speed_limit + 15 else "MEDIUM",
                    status="UNRESOLVED", created_at=datetime.now(timezone.utc)
                ))

        db.commit()
    except Exception as e:
        print(f"[{name}] ❌ DB Error flushing tracker {tid}: {e}")
        db.rollback()
    finally:
        db.close()
