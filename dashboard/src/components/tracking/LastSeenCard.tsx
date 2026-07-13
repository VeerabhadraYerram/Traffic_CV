import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { VehicleEvent, Camera } from '@/types';
import { MapPin, Clock, Gauge, ShieldAlert } from 'lucide-react';

interface LastSeenCardProps {
  lastSeen: { event: VehicleEvent; camera: Camera } | null;
}

export function LastSeenCard({ lastSeen }: LastSeenCardProps) {
  if (!lastSeen) return null;

  const { event, camera } = lastSeen;
  const date = new Date(event.entry_time);
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = date.toLocaleDateString([], { day: '2-digit', month: 'short' });

  // OCR confidence color
  const ocrColor = 
    event.ocr_confidence >= 90 ? 'bg-success/10 text-emerald-600 border-success/20 rounded-md font-mono' :
    event.ocr_confidence >= 75 ? 'bg-amber-500/10 text-amber-600 border-amber-500/20 rounded-md font-mono' :
    'bg-destructive/10 text-destructive border-destructive/20 rounded-md font-mono';

  return (
    <Card className="w-80 bg-card/95 border border-border backdrop-blur-md shadow-lg rounded-xl">
      <CardHeader className="p-3 border-b border-border bg-muted/30 flex flex-row items-center justify-between">
        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground m-0">
          Last Seen Node Info
        </CardTitle>
        <Badge variant="outline" className={ocrColor}>
          OCR: {event.ocr_confidence}%
        </Badge>
      </CardHeader>
      
      <CardContent className="p-4 flex flex-col space-y-3">
        {/* Bounding Box Snap image */}
        <div className="relative aspect-video rounded-md overflow-hidden border border-border bg-black">
          <img 
            src={event.image_url} 
            alt="Last Seen CCTV Crop" 
            className="w-full h-full object-cover"
          />
          <div className="absolute top-2 left-2 bg-black/80 px-2 py-0.5 rounded-md text-[8px] font-mono text-slate-300 border border-border/50">
            {event.camera_id} LIVE SNAP
          </div>
        </div>

        {/* Telemetry rows */}
        <div className="space-y-2 border-t border-border pt-2.5 text-xs text-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-slate-500 flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" /> Camera Node</span>
            <span className="font-semibold text-foreground">{camera.location_name}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-500 flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Capture Time</span>
            <span className="font-mono text-slate-600">{dateStr}, {time}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-500 flex items-center gap-1.5"><Gauge className="h-3.5 w-3.5" /> Node Speed</span>
            <span className="font-semibold text-foreground font-mono">
              {event.speed_kmh ? `${event.speed_kmh} km/h` : 'N/A'}
            </span>
          </div>
        </div>

        {/* Watchlist warning */}
        {event.is_violation && (
          <div className="flex items-center gap-2 text-[10px] font-semibold text-destructive bg-destructive/10 border border-destructive/20 p-2 rounded-md">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-destructive" />
            <span>VIOLATION LOGGED AT THIS COORDINATE</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
export default LastSeenCard;
