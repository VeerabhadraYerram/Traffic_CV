import re

file_path = r"c:\Internship\Trafffic-Analytics\Traffic_CV\pipeline_api.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fetch calibration_polygon_normalized
content = content.replace(
    "speed_polygon_normalized = cam.speed_polygon_normalized",
    "speed_polygon_normalized = cam.speed_polygon_normalized\n    calibration_polygon_normalized = cam.calibration_polygon_normalized"
)

# 2. Update SpeedEstimator init and add PolygonZone
old_estimator = """    speed_estimator = None
    if speed_polygon_normalized:
        speed_estimator = SpeedEstimator(
            polygon_normalized=speed_polygon_normalized,
            distance_meters=distance_between_lines_meters or 15.0,
            frame_width=width,
            frame_height=height
        )"""

new_estimator = """    speed_estimator = None
    cal_poly = calibration_polygon_normalized if calibration_polygon_normalized else (speed_polygon_normalized if speed_polygon_normalized and len(speed_polygon_normalized) == 4 else None)
    if cal_poly and len(cal_poly) == 4:
        speed_estimator = SpeedEstimator(
            polygon_normalized=cal_poly,
            distance_meters=distance_between_lines_meters or 15.0,
            frame_width=width,
            frame_height=height
        )
        
    speed_zone = None
    if speed_polygon_normalized and len(speed_polygon_normalized) >= 3:
        import numpy as np
        pts = np.array([[int(p['x']*width), int(p['y']*height)] for p in speed_polygon_normalized], dtype=np.int32)
        speed_zone = sv.PolygonZone(polygon=pts)"""

content = content.replace(old_estimator, new_estimator)

# 3. Add PolygonZoneAnnotator
content = content.replace(
    "label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5, color_lookup=sv.ColorLookup.TRACK)",
    "label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5, color_lookup=sv.ColorLookup.TRACK)\n    zone_annotator = sv.PolygonZoneAnnotator(zone=speed_zone, color=sv.Color.YELLOW) if speed_zone else None"
)

# 4. Filter tracking to only update speed if inside zone (optional, maybe just draw it)
# The user wants flexible ROI, so only update speed if bottom_center is inside speed_zone.
# supervision PolygonZone has `trigger(detections)` which takes a sv.Detections object.
# Alternatively we can just use cv2.pointPolygonTest
old_speed_update = """            for tid, x1, y1, x2, y2, v_type in valid_tracks:
                inst_speed = 0.0
                if speed_estimator:
                    bottom_center = (int((x1+x2)/2), int(y2))
                    safe_fps = fps if fps and fps > 0 else 30.0
                    inst_speed = speed_estimator.update_and_get_speed(tid, bottom_center, current_time=frame_counter/safe_fps)"""

new_speed_update = """            for tid, x1, y1, x2, y2, v_type in valid_tracks:
                inst_speed = 0.0
                bottom_center = (int((x1+x2)/2), int(y2))
                
                # Check if inside speed zone
                in_zone = True
                if speed_zone:
                    # cv2 point polygon test
                    in_zone = cv2.pointPolygonTest(speed_zone.polygon, bottom_center, False) >= 0

                if speed_estimator and in_zone:
                    safe_fps = fps if fps and fps > 0 else 30.0
                    inst_speed = speed_estimator.update_and_get_speed(tid, bottom_center, current_time=frame_counter/safe_fps)"""

content = content.replace(old_speed_update, new_speed_update)

# 5. Draw the speed zone
old_draw = """            if speed_polygon_normalized:
                pts = []
                for p in speed_polygon_normalized:
                    pts.append([int(p['x'] * width), int(p['y'] * height)])
                import numpy as np
                pts_arr = np.array(pts, np.int32)
                pts_arr = pts_arr.reshape((-1, 1, 2))
                cv2.polylines(frame, [pts_arr], isClosed=True, color=(0, 255, 255), thickness=2)"""

new_draw = """            if zone_annotator:
                frame = zone_annotator.annotate(scene=frame)"""

content = content.replace(old_draw, new_draw)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("pipeline_api.py patched successfully!")
