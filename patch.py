import re

def patch():
    with open('run_cameras.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Threading -> Multiprocessing
    code = code.replace('import threading', 'import multiprocessing')
    code = code.replace('session_lock = threading.Lock()', '')
    
    # Remove global active_sessions init (lines 22-24)
    code = re.sub(r'# Global memory for all cameras\n# Structure:.*?\nactive_sessions = \{\}\n', '', code, flags=re.DOTALL)
    
    # 2. flush_session_to_db: max_speed logic
    speed_calc = """            speed_kmh = (15.0 / duration_sec) * 3.6 if duration_sec > 0 else 0.0
            is_speeding = speed_kmh > speed_limit"""
    new_speed_calc = """            max_inst_speed = session_data.get("max_speed_kmh", 0.0)
            if max_inst_speed > 0:
                speed_kmh = max_inst_speed
            else:
                line_dist = session_data.get("distance_between_lines_meters", 15.0)
                speed_kmh = (line_dist / duration_sec) * 3.6 if duration_sec > 0 else 0.0
            
            is_speeding = speed_kmh > speed_limit"""
    code = code.replace(speed_calc, new_speed_calc)

    # 3. process_camera signature
    code = code.replace('def process_camera(cam_id, name, video_source, role, entry_line_norm, exit_line_norm):',
                        'def process_camera(cam_id, name, video_source, role, entry_line_norm, exit_line_norm, speed_polygon_normalized, distance_between_lines_meters):\n    from speed_estimator import SpeedEstimator\n    active_sessions = {}')

    # 4. YOLO model init
    old_yolo = """    # Initialize YOLO11 Model
    model = YOLO("yolo11m.pt")"""
    new_yolo = """    # Initialize YOLO11 Model
    import os
    if torch.cuda.is_available() and os.path.exists("yolo11m.engine"):
        print(f"[{name}] ⚡ Loading TensorRT Engine: yolo11m.engine")
        model = YOLO("yolo11m.engine", task="detect")
    else:
        print(f"[{name}] ℹ️ Loading standard PyTorch Model: yolo11m.pt")
        model = YOLO("yolo11m.pt")"""
    code = code.replace(old_yolo, new_yolo)

    # 5. Remove global init inside process_camera
    old_init = """    # Init DB memory for this camera
    with session_lock:
        if cam_id not in active_sessions:
            active_sessions[cam_id] = {}"""
    code = code.replace(old_init, '')

    # 6. speed estimator init
    old_cap = """    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))"""
    new_cap = """    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    speed_estimator = None
    if speed_polygon_normalized:
        speed_estimator = SpeedEstimator(
            polygon_normalized=speed_polygon_normalized,
            distance_meters=distance_between_lines_meters or 15.0,
            frame_width=width,
            frame_height=height
        )"""
    code = code.replace(old_cap, new_cap)

    # 7. Replace all active_sessions[cam_id] with active_sessions
    code = code.replace('active_sessions[cam_id]', 'active_sessions')
    
    # 8. Remove with session_lock: and fix indentation. 
    # A simple hack for Python is to replace 'with session_lock:' with 'if True:' so we don't have to re-indent everything!
    code = code.replace('with session_lock:', 'if True:')

    # 9. Update the loop where we process valid_tracks to calculate speed
    old_valid_tracks = """        for tid, x1, y1, x2, y2, v_type in valid_tracks:
            if tid not in active_sessions:"""
    new_valid_tracks = """        for tid, x1, y1, x2, y2, v_type in valid_tracks:
            inst_speed = 0.0
            if speed_estimator:
                cx = (x1 + x2) / 2
                inst_speed = speed_estimator.update_and_get_speed(tid, (cx, y2))
                
            if tid not in active_sessions:"""
    code = code.replace(old_valid_tracks, new_valid_tracks)

    # Update init of new sessions to store distance_between_lines_meters and max_speed
    old_new_session = """                    active_sessions[tid] = {
                        "plate_reads": [],
                        "plate_confidences": [],
                        "vehicle_type": v_type,
                        "last_seen": frame_counter,
                        "crossed_entry": False,
                        "crossed_exit":  False,
                        "entry_time":    None,
                        "exit_time":     None,
                    }"""
    new_new_session = """                    active_sessions[tid] = {
                        "plate_reads": [],
                        "plate_confidences": [],
                        "vehicle_type": v_type,
                        "last_seen": frame_counter,
                        "crossed_entry": False,
                        "crossed_exit":  False,
                        "entry_time":    None,
                        "exit_time":     None,
                        "max_speed_kmh": inst_speed,
                        "distance_between_lines_meters": distance_between_lines_meters or 15.0
                    }"""
    code = code.replace(old_new_session, new_new_session)

    # Update existing session max speed
    old_update_session = """                    active_sessions[tid]["last_seen"] = frame_counter
                    active_sessions[tid]["vehicle_type"] = v_type"""
    new_update_session = """                    active_sessions[tid]["last_seen"] = frame_counter
                    active_sessions[tid]["vehicle_type"] = v_type
                    if inst_speed > active_sessions[tid].get("max_speed_kmh", 0):
                        active_sessions[tid]["max_speed_kmh"] = inst_speed"""
    code = code.replace(old_update_session, new_update_session)
    
    # 10. Clean stale trackers in speed estimator
    old_flush = """        # DB flush happens outside the lock (it does I/O)
        if stale_tids:
            _db = SessionLocal()
            cam_row = _db.query(Camera).filter(Camera.id == cam_id).first()
            speed_limit_val = cam_row.speed_limit_kmh if cam_row else 30
            _db.close()
            for t in stale_tids:
                if True:
                    session_snap = dict(active_sessions.pop(t, {}))
                flush_session_to_db(cam_id, t, session_snap, name, speed_limit_val)"""
    new_flush = """        # DB flush happens outside the lock (it does I/O)
        if stale_tids:
            _db = SessionLocal()
            cam_row = _db.query(Camera).filter(Camera.id == cam_id).first()
            speed_limit_val = cam_row.speed_limit_kmh if cam_row else 30
            _db.close()
            for t in stale_tids:
                if True:
                    session_snap = dict(active_sessions.pop(t, {}))
                flush_session_to_db(cam_id, t, session_snap, name, speed_limit_val)
            if speed_estimator:
                speed_estimator.clean_stale_trackers(active_sessions.keys())"""
    code = code.replace(old_flush, new_flush)

    # 11. Main Threading to Multiprocessing
    old_thread_start = """        t = multiprocessing.Thread(
            target=process_camera,
            args=(cam_id, cam.name, cam.video_source, role, cam.entry_line_normalized, cam.exit_line_normalized)
        )
        t.start()
        threads.append(t)"""
    new_thread_start = """        t = multiprocessing.Process(
            target=process_camera,
            args=(cam_id, cam.name, cam.video_source, role, cam.entry_line_normalized, cam.exit_line_normalized, cam.speed_polygon_normalized, cam.distance_between_lines_meters)
        )
        t.start()
        threads.append(t)"""
    code = code.replace(old_thread_start, new_thread_start)
    
    # Oh wait, we replaced 'import threading' with 'import multiprocessing', so 'threading.Thread' became 'multiprocessing.Thread'!
    # Let's fix that fallback explicitly in case the string is different.
    code = code.replace('multiprocessing.Thread(', 'multiprocessing.Process(')
    code = code.replace('args=(cam_id, cam.name, cam.video_source, role, cam.entry_line_normalized, cam.exit_line_normalized)', 
                        'args=(cam_id, cam.name, cam.video_source, role, cam.entry_line_normalized, cam.exit_line_normalized, cam.speed_polygon_normalized, cam.distance_between_lines_meters)')

    with open('run_cameras.py', 'w', encoding='utf-8') as f:
        f.write(code)

if __name__ == '__main__':
    patch()
