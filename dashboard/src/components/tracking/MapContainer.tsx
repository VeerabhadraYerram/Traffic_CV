import { useEffect, useRef, useState } from 'react';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import type { Camera, VehicleEvent } from '@/types';
import { AlertCircle } from 'lucide-react';

interface MapContainerProps {
  cameras: Camera[];
  routePath: { lat: number; lng: number; camera_id: string; location_name: string; timestamp: string }[];
  selectedNode: { event: VehicleEvent; camera: Camera } | null;
  onNodeClick: (node: { event: VehicleEvent; camera: Camera }) => void;
  onCameraClick?: (camera: Camera) => void;
}

let isApiInitialized = false;

export function MapContainer({ cameras, routePath, onCameraClick }: MapContainerProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const [googleMap, setGoogleMap] = useState<any | null>(null);
  const [markers, setMarkers] = useState<any[]>([]);
  const [polylines, setPolylines] = useState<any[]>([]);
  
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  const hasApiKey = !!(apiKey && apiKey !== '' && apiKey !== '""');
  
  const [isApiConfigured, setIsApiConfigured] = useState(hasApiKey);
  const [loading, setLoading] = useState(hasApiKey);

  useEffect(() => {
    if (hasApiKey) {
      setIsApiConfigured(true);
      
      if (!isApiInitialized) {
        setOptions({
          key: apiKey,
        });
        isApiInitialized = true;
      }

      const initMap = async () => {
        if (!mapRef.current) return;
        
        try {
          const { Map } = await importLibrary('maps') as any;

          // Custom High-Tech Monochromatic light map styles
          const lightMapStyle = [
            { elementType: 'geometry', stylers: [{ color: '#f8fafc' }] },
            { elementType: 'labels.text.stroke', stylers: [{ color: '#ffffff' }, { weight: 2 }] },
            { elementType: 'labels.text.fill', stylers: [{ color: '#475569' }] },
            {
              featureType: 'administrative',
              elementType: 'labels.text.fill',
              stylers: [{ color: '#334155' }]
            },
            {
              featureType: 'poi',
              stylers: [{ visibility: 'off' }] // Remove generic POIs to de-clutter campus
            },
            {
              featureType: 'road',
              elementType: 'geometry',
              stylers: [{ color: '#ffffff' }]
            },
            {
              featureType: 'road',
              elementType: 'geometry.stroke',
              stylers: [{ color: '#e2e8f0' }]
            },
            {
              featureType: 'road',
              elementType: 'labels.text.fill',
              stylers: [{ color: '#64748b' }]
            },
            {
              featureType: 'road.highway',
              elementType: 'geometry',
              stylers: [{ color: '#e2e8f0' }]
            },
            {
              featureType: 'road.highway',
              elementType: 'geometry.stroke',
              stylers: [{ color: '#cbd5e1' }]
            },
            {
              featureType: 'road.highway',
              elementType: 'labels.text.fill',
              stylers: [{ color: '#475569' }]
            },
            {
              featureType: 'water',
              elementType: 'geometry',
              stylers: [{ color: '#e0f2fe' }]
            },
            {
              featureType: 'water',
              elementType: 'labels.text.fill',
              stylers: [{ color: '#0284c7' }]
            },
            {
              featureType: 'transit',
              stylers: [{ visibility: 'off' }]
            }
          ];

          const map = new Map(mapRef.current, {
            center: { lat: 17.5384, lng: 78.3850 },
            zoom: 17,
            styles: lightMapStyle,
            disableDefaultUI: true,
            zoomControl: true,
          });

          setGoogleMap(map);
          setLoading(false);
        } catch (err) {
          console.error('Error importing Google Maps libraries:', err);
          setIsApiConfigured(false);
          setLoading(false);
        }
      };

      initMap();
    } else {
      setIsApiConfigured(false);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  // Handle markers & routes update on real Google Map
  useEffect(() => {
    if (!googleMap || !isApiConfigured) return;

    const loadElements = async () => {
      try {
        const { Marker } = await importLibrary('marker') as any;

        // Clear old markers
        markers.forEach(m => m.setMap(null));
        setMarkers([]);

        // Clear old routes
        polylines.forEach(p => p.setMap(null));
        setPolylines([]);

        const newMarkers: any[] = [];

        // Create markers for cameras
        cameras.forEach(camera => {
          const color = 
            camera.status === 'ACTIVE' ? '#10b981' : 
            camera.status === 'OFFLINE' ? '#94a3b8' : '#f59e0b';
          
          // High-Tech concentric radar circle target marker
          const targetSvg = `
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
              <circle cx="16" cy="16" r="14" fill="none" stroke="${color}" stroke-width="2" opacity="0.3" />
              <circle cx="16" cy="16" r="8" fill="none" stroke="${color}" stroke-width="1.5" />
              <circle cx="16" cy="16" r="5" fill="${color}" />
              <circle cx="16" cy="16" r="1.5" fill="#ffffff" />
            </svg>
          `;

          const marker = new Marker({
            position: { lat: camera.latitude, lng: camera.longitude },
            map: googleMap,
            title: camera.location_name,
            icon: {
              url: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(targetSvg),
              scaledSize: new (window as any).google.maps.Size(32, 32),
              anchor: new (window as any).google.maps.Point(16, 16)
            }
          });

          marker.addListener('click', () => {
            if (onCameraClick) {
              onCameraClick(camera);
            }
          });

          newMarkers.push(marker);
        });

        setMarkers(newMarkers);

        // Create route lines if we have a tracking path
        if (routePath.length > 1) {
          const flightPlanCoordinates = routePath.map(p => ({ lat: p.lat, lng: p.lng }));
          
          const lineSymbol = {
            path: 'M 0,-1 0,1',
            strokeOpacity: 1,
            scale: 4
          };

          const trackingLine = new (window as any).google.maps.Polyline({
            path: flightPlanCoordinates,
            geodesic: true,
            strokeColor: '#0284c7',
            strokeOpacity: 0,
            icons: [{
              icon: lineSymbol,
              offset: '0',
              repeat: '20px'
            }],
            strokeWeight: 2,
            map: googleMap
          });

          let count = 0;
          const interval = setInterval(() => {
            count = (count + 1) % 200;
            const icons = trackingLine.get('icons');
            if (icons && icons[0]) {
              icons[0].offset = (count / 10) + 'px';
              trackingLine.set('icons', icons);
            }
          }, 50);

          setPolylines([trackingLine]);

          // Adjust boundaries to show route
          const bounds = new (window as any).google.maps.LatLngBounds();
          flightPlanCoordinates.forEach(coord => bounds.extend(coord));
          googleMap.fitBounds(bounds);

          return () => {
            clearInterval(interval);
          };
        } else {
          googleMap.setCenter({ lat: 17.5384, lng: 78.3850 });
          googleMap.setZoom(17);
        }
      } catch (err) {
        console.error('Error generating map markers:', err);
      }
    };

    loadElements();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleMap, cameras, routePath, isApiConfigured]);

  const renderMockMap = () => {
    const minLat = 17.5350;
    const maxLat = 17.5410;
    const minLng = 78.3800;
    const maxLng = 78.3880;

    const getRelativeXY = (lat: number, lng: number) => {
      const x = ((lng - minLng) / (maxLng - minLng)) * 100;
      const y = 100 - (((lat - minLat) / (maxLat - minLat)) * 100);
      return { x: `${x}%`, y: `${y}%` };
    };

    return (
      <div className="relative w-full h-full bg-[#f8fafc] border border-border rounded-xl overflow-hidden flex flex-col justify-between select-none animate-fade-in shadow-inner">
        <div className="absolute inset-0 opacity-5 bg-[linear-gradient(to_right,var(--primary)_1px,transparent_1px),linear-gradient(to_bottom,var(--primary)_1px,transparent_1px)] bg-[size:40px_40px]" />
        
        <div className="absolute top-4 left-4 z-10 bg-card/95 border border-amber-500/25 rounded-md p-3 max-w-sm backdrop-blur text-xs flex gap-2.5 shadow-md">
          <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-slate-700">
            <strong className="text-slate-900 block font-semibold">Google Maps API Offline</strong>
            To enable real maps, provide a valid <code className="bg-slate-100 border border-slate-200 px-1 py-0.5 rounded-md text-[10px] text-amber-600 font-mono">VITE_GOOGLE_MAPS_API_KEY</code> in the project's <code className="bg-slate-100 border border-slate-200 px-1 py-0.5 rounded-md text-[10px] text-amber-600 font-mono">.env</code> file.
          </div>
        </div>

        <div className="absolute bottom-4 left-4 z-10 text-[9px] font-mono text-slate-500 bg-card/90 px-2 py-1 rounded-md border border-border shadow-xs">
          CENTER: 17.5384° N, 78.3850° E // VNR VJIET CAMPUS MOCK
        </div>

        <svg className="absolute inset-0 w-full h-full">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 2 L 10 5 L 0 8 z" fill="var(--primary)" />
            </marker>
          </defs>

          <path d="M 0 80 Q 50 60, 100 20" stroke="var(--border)" strokeWidth="1.5" fill="none" opacity="0.6" />
          <path d="M 20 100 L 80 0" stroke="var(--border)" strokeWidth="1.2" fill="none" opacity="0.6" />
          <path d="M 0 35 H 100" stroke="var(--border)" strokeWidth="1.5" fill="none" opacity="0.6" />
          <path d="M 50 0 V 100" stroke="var(--border)" strokeWidth="1.2" fill="none" opacity="0.6" />

          {routePath.length > 1 && (
            <polyline
              points={routePath.map(p => {
                const { x, y } = getRelativeXY(p.lat, p.lng);
                return `${(parseFloat(x) / 100) * 800} ${(parseFloat(y) / 100) * 500}`; // Adjusted scale dynamically
              }).join(', ')}
              fill="none"
              stroke="var(--primary)"
              strokeWidth="3"
              strokeDasharray="8,6"
              className="animate-[dash_20s_linear_infinite]"
              style={{
                strokeDashoffset: 100
              }}
              markerEnd="url(#arrow)"
            />
          )}
        </svg>

        <style dangerouslySetInnerHTML={{__html: `
          @keyframes dash {
            to {
              stroke-dashoffset: -1000;
            }
          }
        `}} />

        <div className="absolute inset-0 w-full h-full">
          {cameras.map(camera => {
            const { x, y } = getRelativeXY(camera.latitude, camera.longitude);
            const statusColor = 
              camera.status === 'ACTIVE' ? 'bg-success shadow-success/20' : 
              camera.status === 'OFFLINE' ? 'bg-slate-400 shadow-slate-400/20' : 'bg-amber-500 shadow-amber-500/20';

            const isCameraInRoute = routePath.some(rp => rp.camera_id === camera.camera_id);
            const routeIndex = routePath.findIndex(rp => rp.camera_id === camera.camera_id);

            return (
              <div 
                key={camera.camera_id} 
                style={{ left: x, top: y }}
                onClick={() => onCameraClick && onCameraClick(camera)}
                className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-20 group"
              >
                {camera.status === 'MAINTENANCE' && (
                  <span className="absolute -inset-2 flex h-8 w-8 animate-pulse rounded-full bg-amber-500/25" />
                )}
                
                <div className={`h-4 w-4 rounded-full border-2 border-background shadow-lg ${statusColor} transition-transform duration-200 group-hover:scale-125 flex items-center justify-center`}>
                  {isCameraInRoute && (
                    <span className="text-[8px] font-extrabold text-white font-sans">
                      {routeIndex + 1}
                    </span>
                  )}
                </div>

                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 -translate-y-2 bg-card border border-border p-2.5 rounded-md shadow-lg text-[10px] text-slate-600 w-44 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-30">
                  <div className="font-bold text-foreground flex justify-between">
                    <span>{camera.location_name}</span>
                    <span className="text-slate-400 font-mono">{camera.camera_id}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between border-t border-border pt-1">
                    <span>Limit: {camera.speed_limit_kmh} km/h</span>
                    <span className={camera.status === 'ACTIVE' ? 'text-success font-bold font-mono' : camera.status === 'OFFLINE' ? 'text-slate-500 font-mono' : 'text-amber-500 font-mono'}>
                      {camera.status}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {routePath.length > 0 && (
          <div className="absolute bottom-4 right-4 z-10 bg-card/95 border border-border p-3 rounded-md backdrop-blur text-xs font-mono text-primary max-w-sm shadow-md">
            <span className="text-foreground block font-bold uppercase tracking-wider text-[10px] text-slate-500 border-b border-border pb-1 mb-1.5">
              Active Tracking Route Path
            </span>
            <span className="text-slate-600 block">Route segments: {routePath.length} nodes</span>
            <div className="text-[10px] text-slate-500 mt-1 flex flex-col space-y-0.5">
              {routePath.map((rp, index) => (
                <div key={index} className="flex items-center gap-1">
                  <span className="text-primary font-bold">{index + 1}.</span>
                  <span className="text-slate-600">{rp.camera_id} ({new Date(rp.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="relative w-full h-full min-h-[500px] bg-background">
      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 space-y-3 bg-background z-10 rounded-xl">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
          <p className="text-xs font-medium text-slate-500">Initializing Google Maps Canvas...</p>
        </div>
      )}
      
      {hasApiKey && isApiConfigured ? (
        <div ref={mapRef} className="w-full h-full rounded-xl border border-border overflow-hidden shadow-md" />
      ) : (
        !loading && renderMockMap()
      )}
    </div>
  );
}
export default MapContainer;
