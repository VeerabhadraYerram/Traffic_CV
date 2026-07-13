import { useEvents } from './use-events';
import { useViolations } from './use-violations';
import { useCameras } from './use-cameras';
import { useMemo } from 'react';

export function useAnalytics(timeframe: 'day' | 'week' | 'month' = 'day') {
  const { data: events = [], isLoading: eventsLoading } = useEvents();
  const { data: violations = [], isLoading: violationsLoading } = useViolations();
  const { data: cameras = [], isLoading: camerasLoading } = useCameras();

  const isLoading = eventsLoading || violationsLoading || camerasLoading;

  const stats = useMemo(() => {
    const activeCamerasCount = cameras.filter(c => c.status === 'ACTIVE').length;
    const unresolvedViolations = violations.filter(v => v.status === 'UNRESOLVED');
    const speedViolationsCount = unresolvedViolations.filter(v => v.violation_type === 'SPEEDING').length;
    
    // total vehicles today (filter by last 24 hours)
    const oneDayAgo = new Date();
    oneDayAgo.setDate(oneDayAgo.getDate() - 1);
    const todayEvents = events.filter(e => new Date(e.entry_time) >= oneDayAgo);

    return {
      totalVehiclesToday: todayEvents.length || events.length,
      liveSpeedViolations: speedViolationsCount,
      activeCameras: activeCamerasCount,
      pendingAlertsCount: unresolvedViolations.length
    };
  }, [events, violations, cameras]);

  // Traffic volume over time
  const trafficChartData = useMemo(() => {
    // Group events by hour/day/week depending on timeframe
    const groups: { [key: string]: number } = {};
    
    events.forEach(event => {
      const date = new Date(event.entry_time);
      let label = '';
      
      if (timeframe === 'day') {
        // Label by hour (e.g. "11 AM")
        label = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      } else if (timeframe === 'week') {
        // Label by weekday (e.g. "Mon")
        label = date.toLocaleDateString([], { weekday: 'short' });
      } else {
        // Label by day of month (e.g. "09 Jul")
        label = date.toLocaleDateString([], { day: 'numeric', month: 'short' });
      }
      
      groups[label] = (groups[label] || 0) + 1;
    });

    // Convert to chart array (reverse to chronological order)
    return Object.entries(groups)
      .map(([name, count]) => ({ name, count }))
      .reverse()
      .slice(-12); // Limit to last 12 points
  }, [events, timeframe]);

  // Vehicle type composition
  const vehicleCompositionData = useMemo(() => {
    const groups: { [key: string]: number } = {
      Car: 0,
      Bike: 0,
      Truck: 0,
      Bus: 0,
      Other: 0
    };

    events.forEach(event => {
      // vehicle_type is stored as bare strings e.g. "Car", "Bike", "Truck", "Bus"
      const type = event.vehicle_type ?? '';
      let matched = false;
      for (const key of Object.keys(groups)) {
        if (type.toLowerCase().includes(key.toLowerCase())) {
          groups[key]++;
          matched = true;
          break;
        }
      }
      if (!matched) groups['Other']++;
    });

    return Object.entries(groups)
      .map(([name, value]) => ({ name, value }))
      .filter(item => item.value > 0);
  }, [events]);

  // Violation types stacked bar data
  const violationDensityData = useMemo(() => {
    const timeGroups: { [key: string]: { speeding: number; redLight: number; blacklist: number; unauthorized: number } } = {};

    violations.forEach(v => {
      const date = new Date(v.created_at);
      let label = '';
      
      if (timeframe === 'day') {
        label = date.toLocaleTimeString([], { hour: 'numeric' });
      } else if (timeframe === 'week') {
        label = date.toLocaleDateString([], { weekday: 'short' });
      } else {
        label = date.toLocaleDateString([], { day: 'numeric', month: 'short' });
      }

      if (!timeGroups[label]) {
        timeGroups[label] = { speeding: 0, redLight: 0, blacklist: 0, unauthorized: 0 };
      }

      if (v.violation_type === 'SPEEDING') timeGroups[label].speeding++;
      else if (v.violation_type === 'RED_LIGHT') timeGroups[label].redLight++;
      else if (v.violation_type === 'BLACKLISTED') timeGroups[label].blacklist++;
      else if (v.violation_type === 'UNAUTHORIZED_ENTRY') timeGroups[label].unauthorized++;
    });

    return Object.entries(timeGroups)
      .map(([name, data]) => ({
        name,
        Speeding: data.speeding,
        'Red Light': data.redLight,
        Blacklisted: data.blacklist,
        'Unauthorized Entry': data.unauthorized
      }))
      .reverse()
      .slice(-8); // last 8 segments
  }, [violations, timeframe]);

  // Camera alert counts horizontal bar data
  const cameraAlertData = useMemo(() => {
    const counts: { [key: string]: number } = {};

    violations.forEach(v => {
      // Find camera by event
      const event = events.find(e => e.event_id === v.event_id);
      if (event) {
        // Find camera by matching UUID
        const camera = cameras.find(c => c.id === event.camera_id);
        const name = camera ? camera.name : event.camera_id;
        counts[name] = (counts[name] || 0) + 1;
      }
    });

    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5); // top 5 alerting cameras
  }, [violations, events, cameras]);

  return {
    isLoading,
    stats,
    trafficChartData,
    vehicleCompositionData,
    violationDensityData,
    cameraAlertData
  };
}
