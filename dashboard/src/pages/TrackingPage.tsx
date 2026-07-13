import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCameras } from '@/hooks/use-cameras';
import { useTracking } from '@/hooks/use-tracking';
import { MapContainer } from '@/components/tracking/MapContainer';
import { SearchPanel } from '@/components/tracking/SearchPanel';
import { LastSeenCard } from '@/components/tracking/LastSeenCard';
import { CameraDetailsCard } from '@/components/tracking/CameraDetailsCard';
import type { Camera } from '@/types';

export function TrackingPage() {
  const { data: cameras = [] } = useCameras();
  const [searchParams, setSearchParams] = useSearchParams();
  const searchPlate = searchParams.get('plate') || '';
  const setSearchPlate = (val: string) => {
    setSearchParams(val ? { plate: val.toUpperCase() } : {});
  };
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);

  // Get tracking data for the searched plate
  const { nodes, routePath, lastSeen } = useTracking(searchPlate);

  const [selectedNode, setSelectedNode] = useState<{ event: any; camera: any } | null>(null);

  const handleNodeClick = (node: { event: any; camera: any }) => {
    setSelectedNode(node);
  };

  return (
    <div className="relative w-full h-[calc(100vh-100px)] rounded-xl border border-border overflow-hidden bg-background shadow-md">
      {/* Background Interactive Google Maps layer */}
      <MapContainer
        cameras={cameras}
        routePath={routePath}
        selectedNode={selectedNode || lastSeen}
        onNodeClick={handleNodeClick}
        onCameraClick={setSelectedCamera}
      />

      {/* Floating Left Search Panel */}
      <div className="absolute top-4 left-4 z-10 max-h-[calc(100%-32px)] overflow-y-auto">
        <SearchPanel
          searchQuery={searchPlate}
          onSearchChange={setSearchPlate}
          nodes={nodes}
        />
      </div>

      {/* Floating Right HUD Card - Camera Details (Top Right) */}
      {selectedCamera && (
        <div className="absolute top-4 right-4 z-10">
          <CameraDetailsCard 
            camera={selectedCamera} 
            onClose={() => setSelectedCamera(null)} 
          />
        </div>
      )}

      {/* Floating Right HUD Card - Last Seen (Bottom Right) */}
      <div className="absolute bottom-4 right-4 z-10">
        <LastSeenCard lastSeen={lastSeen} />
      </div>
    </div>
  );
}
export default TrackingPage;
