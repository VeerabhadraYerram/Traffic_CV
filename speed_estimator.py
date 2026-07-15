import cv2
import numpy as np
import collections
import time

class SpeedEstimator:
    def __init__(self, polygon_normalized, distance_meters, frame_width, frame_height, window_size=15):
        """
        Initializes the SpeedEstimator.
        polygon_normalized: List of 4 points in normalized coordinates, e.g.,
                            [{"x": 0.2, "y": 0.5}, {"x": 0.8, "y": 0.5}, {"x": 1.0, "y": 0.9}, {"x": 0.0, "y": 0.9}]
                            (top-left, top-right, bottom-right, bottom-left)
        distance_meters: Physical length of the polygon (top to bottom).
        """
        self.distance_meters = distance_meters
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        self.src_points = self._parse_polygon(polygon_normalized)
        
        self.homography_matrix = None
        if self.src_points is not None and len(self.src_points) == 4 and self.distance_meters > 0:
            self.homography_matrix = self._calculate_homography()
            
        # Store history of positions for smoothing
        self.track_history = {} # tracker_id -> deque of (timestamp, rw_x, rw_y)
        self.window_size = window_size

    def _parse_polygon(self, poly):
        if not poly or not isinstance(poly, list) or len(poly) != 4:
            return None
        try:
            pts = []
            for pt in poly:
                pts.append([pt['x'] * self.frame_width, pt['y'] * self.frame_height])
            return np.array(pts, dtype=np.float32)
        except Exception as e:
            print(f"Warning: Invalid speed polygon configuration: {e}")
            return None

    def _calculate_homography(self):
        # We create a top-down projection space where 1 meter = 10 pixels
        scale = 10.0
        projected_height = self.distance_meters * scale
        
        # Arbitrary width just to form a rectangle, as long as it aligns with the perspective depth
        projected_width = projected_height
        
        dst_points = np.array([
            [0, 0],
            [projected_width, 0],
            [projected_width, projected_height],
            [0, projected_height]
        ], dtype=np.float32)
        
        M, _ = cv2.findHomography(self.src_points, dst_points)
        return M

    def update_and_get_speed(self, tracker_id, bottom_center, current_time=None):
        """
        Updates the history for a tracker_id and returns the smoothed instantaneous speed in km/h.
        """
        if self.homography_matrix is None:
            return 0.0
            
        if current_time is None:
            current_time = time.time()
            
        if tracker_id not in self.track_history:
            self.track_history[tracker_id] = collections.deque(maxlen=self.window_size)
            
        x, y = bottom_center
        # Transform pixel (x,y) to real-world (rw_x, rw_y) via perspective matrix
        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.homography_matrix)
        rw_x, rw_y = transformed[0][0]
        
        # Convert out of projected scale back to actual meters
        rw_x_meters = rw_x / 10.0
        rw_y_meters = rw_y / 10.0
        
        self.track_history[tracker_id].append((current_time, rw_x_meters, rw_y_meters))
        
        history = self.track_history[tracker_id]
        if len(history) < 5:  # Need at least 5 frames of history to calculate a stable speed
            return 0.0
            
        oldest_time, old_x, old_y = history[0]
        newest_time, new_x, new_y = history[-1]
        
        dt = newest_time - oldest_time
        if dt <= 0.01:
            return 0.0
            
        dx = new_x - old_x
        dy = new_y - old_y
        distance = np.sqrt(dx**2 + dy**2)
        
        speed_mps = distance / dt
        speed_kmh = speed_mps * 3.6
        return speed_kmh

    def clean_stale_trackers(self, active_tracker_ids):
        """Removes history for trackers that are no longer active to prevent memory leaks."""
        stale = [tid for tid in self.track_history if tid not in active_tracker_ids]
        for tid in stale:
            del self.track_history[tid]
