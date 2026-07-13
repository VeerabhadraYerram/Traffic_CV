import { useEvents } from './use-events';
import { useCameras } from './use-cameras';
import { useMemo } from 'react';
import type { VehicleEvent, Camera } from '../types';

export function useTracking(searchPlate: string) {
  const { data: events = [] } = useEvents();
  const { data: cameras = [] } = useCameras();

  const results = useMemo(() => {
    if (!searchPlate || searchPlate.trim() === '') {
      return {
        nodes: [],
        routePath: [],
        lastSeen: null
      };
    }

    const cleanSearch = searchPlate.trim().toUpperCase();

    // Filter events matching the plate, sorted chronologically (ascending entry_time)
    const matchedEvents = events
      .filter(e => e.license_plate.toUpperCase().includes(cleanSearch))
      .sort((a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime());

    // Map events to camera locations with coordinates
    const nodes = matchedEvents
      .map(event => {
        const camera = cameras.find(c => c.id === event.camera_id);
        return {
          event,
          camera
        };
      })
      .filter((n): n is { event: VehicleEvent; camera: Camera } => n.camera !== undefined);

    // Coordinate route line for the map
    const routePath = nodes.map(n => ({
      lat: n.camera.latitude,
      lng: n.camera.longitude,
      camera_id: n.camera.id,
      location_name: n.camera.name,
      timestamp: n.event.entry_time
    }));

    // Last seen is the latest node in the chain
    const lastSeen = nodes.length > 0 ? nodes[nodes.length - 1] : null;

    return {
      nodes,
      routePath,
      lastSeen
    };
  }, [events, cameras, searchPlate]);

  return results;
}
