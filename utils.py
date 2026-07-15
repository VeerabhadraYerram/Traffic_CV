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

def correct_indian_plate(text):
    """Clean and correct an OCR-read Indian license plate string."""
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

    max_num_len = min(4, len(cleaned) - 3)
    num_part = force_digits(cleaned[-max_num_len:])

    mid_part = cleaned[2:-max_num_len]

    if len(mid_part) == 0:
        rto = ""
        series = ""
    else:
        if len(mid_part) >= 2:
            c2 = mid_part[1]
            is_c2_digit = c2.isdigit() or c2 in letter_to_digit
            if is_c2_digit:
                rto = force_digits(mid_part[0:2])
                series = force_letters(mid_part[2:])
            else:
                rto = force_digits(mid_part[0:1])
                series = force_letters(mid_part[1:])
        else:
            rto = force_digits(mid_part[0:1])
            series = ""

    return state + rto + series + num_part


def align_to_template(s):
    """Align a plate string to the standard 10-character Indian plate template."""
    cleaned = re.sub(r'[^A-Z0-9]', '', s.upper())
    if len(cleaned) == 10:
        return cleaned

    if len(cleaned) == 9:
        state = cleaned[0:2]
        num = cleaned[-4:]
        mid = cleaned[2:-4]
        if len(mid) == 3 and state.isalpha() and num.isdigit():
            digits = "".join(c for c in mid if c.isdigit())
            letters = "".join(c for c in mid if c.isalpha())
            if len(digits) == 1 and len(letters) == 2:
                return state + digits + "?" + letters + num
            elif len(digits) == 2 and len(letters) == 1:
                return state + digits + letters + "?" + num

    return cleaned


def get_mode(items):
    """Compute consensus plate text from multiple OCR reads using character-level voting."""
    if not items:
        return "UNKNOWN"

    aligned_reads = []
    for item in items:
        aligned = align_to_template(item)
        if aligned:
            aligned_reads.append(aligned)

    if not aligned_reads:
        return Counter(items).most_common(1)[0][0]

    lengths = [len(r) for r in aligned_reads]
    common_len = Counter(lengths).most_common(1)[0][0]
    filtered_reads = [r for r in aligned_reads if len(r) == common_len]

    consensus_chars = []
    for i in range(common_len):
        chars_at_pos = [read[i] for read in filtered_reads if read[i] != "?"]
        if chars_at_pos:
            most_common_char = Counter(chars_at_pos).most_common(1)[0][0]
            consensus_chars.append(most_common_char)
        else:
            consensus_chars.append("?")

    consensus_str = "".join(consensus_chars)

    corrected = correct_indian_plate(consensus_str)
    if corrected:
        return corrected

    return consensus_str

# ─── Image Enhancement ────────────────────────────────────────────────────────

def enhance_plate(crop):
    """Upscale 3x and apply CLAHE to sharpen plate crop before OCR."""
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return crop
    upscaled = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
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

    final_plate = get_mode(session_data.get("plate_reads", []))
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
