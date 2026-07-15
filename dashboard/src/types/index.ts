

export interface NormalizedLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface NormalizedPoint {
  x: number;
  y: number;
}

/** Full camera shape as returned by /api/cameras.
 *  The endpoint merges both the configurator fields and the dashboard fields
 *  into one object — this interface covers the complete response. */
export interface ConfiguratorCamera {
  // Configurator fields
  id: string;
  name: string;
  role: string;
  video_source: string;
  entry_line: NormalizedLine | null;
  exit_line: NormalizedLine | null;
  speed_polygon_normalized: NormalizedPoint[] | null;
  calibration_polygon_normalized: NormalizedPoint[] | null;
  distance_between_lines_meters: number | null;
  // Dashboard fields (same endpoint, merged response)
  camera_id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  status: string;
  ip_address?: string;
  speed_limit_kmh: number;
}

/** Alias — used by tracking/analytics components that only need dashboard fields. */
export type Camera = ConfiguratorCamera;

export interface VehicleEvent {
  event_id: string;
  camera_id: string;
  camera_name?: string; // resolved locally for ease
  license_plate: string;
  ocr_confidence: number; // percentage
  vehicle_type: string;
  vehicle_color: string;
  image_url: string;
  entry_time: string; // ISO String
  exit_time?: string; // ISO String
  speed_kmh?: number;
  is_violation: boolean;
}

export interface Violation {
  violation_id: string;
  event_id: string;
  license_plate: string; // denormalized for easy rendering
  violation_type: 'SPEEDING' | 'UNAUTHORIZED_ENTRY' | 'RED_LIGHT' | 'BLACKLISTED';
  recorded_value: number;
  zone_limit: number;
  severity_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'UNRESOLVED' | 'ACKNOWLEDGED' | 'ESCALATED' | 'RESOLVED';
  created_at: string;
}

export interface WatchlistEntry {
  plate: string;
  reason: string;
  severity: 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface CameraEdge {
  edge_id: number;
  source_camera_id: string;
  target_camera_id: string;
  distance_meters: number;
  average_transit_time_seconds: number;
}

export interface AnalyticsStats {
  totalVehiclesToday: number;
  liveSpeedViolations: number;
  activeCameras: number;
  pendingAlertsCount: number;
}
