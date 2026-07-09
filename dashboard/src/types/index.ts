export interface Camera {
  camera_id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  status: 'ACTIVE' | 'OFFLINE' | 'MAINTENANCE';
  ip_address?: string;
  speed_limit_kmh: number;
}

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
