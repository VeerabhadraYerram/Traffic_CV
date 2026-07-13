import type { Camera } from '@/types';
import { X, ShieldAlert, Cpu, Eye, Radio } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface CameraDetailsCardProps {
  camera: Camera;
  onClose: () => void;
}

export function CameraDetailsCard({ camera, onClose }: CameraDetailsCardProps) {
  const isOnline = camera.status === 'ACTIVE';
  const statusColor = 
    camera.status === 'ACTIVE' ? 'bg-success' : 
    camera.status === 'OFFLINE' ? 'bg-slate-500' : 'bg-amber-500';

  return (
    <div className="w-80 bg-card/95 border border-border rounded-xl p-4 backdrop-blur-md shadow-lg animate-fade-in text-foreground flex flex-col gap-3.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-2">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-primary animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Node Telemetry</span>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-6 w-6 text-slate-400 hover:text-foreground hover:bg-accent rounded-md" 
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Camera Identity */}
      <div>
        <h4 className="font-bold text-sm text-foreground">{camera.location_name}</h4>
        <div className="flex items-center gap-2 mt-1.5">
          <Badge className="font-mono bg-sky-50 border border-sky-100 text-primary text-[10px] px-1.5 py-0 rounded-md">
            {camera.camera_id}
          </Badge>
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className={`h-2 w-2 rounded-full ${statusColor} animate-pulse`} />
            <span className="capitalize">{camera.status.toLowerCase()}</span>
          </div>
        </div>
      </div>

      {/* Live HUD Viewport */}
      {isOnline ? (
        <div className="relative aspect-video rounded-md border border-border bg-slate-950 overflow-hidden flex flex-col justify-between p-2 font-mono text-[9px] text-success">
          {/* Scanning animation */}
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_50%,rgba(0,230,118,0.08)_50%)] bg-[size:100%_4px] pointer-events-none" />
          <div className="absolute inset-0 opacity-10 bg-[radial-gradient(ellipse_at_center,transparent_20%,#000000_100%)] pointer-events-none" />
          <div className="absolute top-0 left-0 w-full h-[1px] bg-success/50 animate-[scan_2.5s_ease-in-out_infinite]" />

          {/* Viewport content */}
          <div className="flex justify-between items-start z-10">
            <span>SYS.LIVE // {camera.ip_address}</span>
            <span className="flex items-center gap-1">
              <Eye className="h-3 w-3 animate-pulse text-destructive" />
              REC
            </span>
          </div>

          <div className="flex flex-col z-10 opacity-70">
            <span>GPS: {camera.latitude.toFixed(6)} N, {camera.longitude.toFixed(6)} E</span>
            <span>LIMIT: {camera.speed_limit_kmh} KM/H</span>
          </div>
        </div>
      ) : (
        <div className="aspect-video rounded-md border border-border bg-slate-50 flex flex-col items-center justify-center text-center p-3 text-slate-400">
          <ShieldAlert className="h-8 w-8 text-slate-400 mb-1.5" />
          <p className="text-xs font-semibold text-slate-600">FEED OFFLINE</p>
          <p className="text-[10px] text-slate-400 mt-0.5">Camera is currently in {camera.status.toLowerCase()} mode</p>
        </div>
      )}

      {/* Specs / Grid info */}
      <div className="grid grid-cols-2 gap-2 text-xs border-t border-border pt-3">
        <div className="bg-muted/30 p-2 rounded-md border border-border/40">
          <p className="text-[10px] text-slate-500">Speed Limit</p>
          <p className="font-bold mt-0.5 text-slate-800 font-mono">{camera.speed_limit_kmh} km/h</p>
        </div>
        <div className="bg-muted/30 p-2 rounded-md border border-border/40">
          <p className="text-[10px] text-slate-500">IP Connection</p>
          <p className="font-mono font-semibold mt-0.5 text-slate-600 truncate">{camera.ip_address}</p>
        </div>
      </div>

      {/* Action Footer */}
      {isOnline && (
        <div className="flex items-center gap-2 border-t border-border pt-3">
          <Cpu className="h-4 w-4 text-success" />
          <span className="text-[10px] text-slate-500 font-medium">OCR capture stream active</span>
        </div>
      )}
    </div>
  );
}
