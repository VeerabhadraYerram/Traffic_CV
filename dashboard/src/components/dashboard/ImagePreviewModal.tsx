import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import type { VehicleEvent } from '@/types';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Calendar, Clock, Video, Gauge, ShieldAlert, MapPin } from 'lucide-react';

interface ImagePreviewModalProps {
  event: VehicleEvent | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ImagePreviewModal({ event, isOpen, onClose }: ImagePreviewModalProps) {
  const navigate = useNavigate();
  if (!event) return null;

  const date = new Date(event.entry_time);
  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = date.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });

  const handleTrackVehicle = () => {
    onClose();
    navigate(`/tracking?plate=${event.license_plate.toUpperCase()}`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl sm:max-w-5xl bg-card border border-border text-foreground rounded-xl shadow-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-3">
            <span>License Plate:</span>
            <span className="inline-block px-3 py-1 font-mono font-bold text-slate-800 bg-slate-100 border border-slate-300 tracking-widest rounded-md shadow-xs">
              {event.license_plate.toUpperCase()}
            </span>
          </DialogTitle>
          <DialogDescription className="text-muted-foreground text-xs mt-1">
            ANPR Camera Capture Log — Event ID: {event.event_id}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
          {/* Main CCTV Frame Image */}
          <div className="md:col-span-2 relative aspect-video rounded-lg overflow-hidden border border-border bg-black">
            <img 
              src={event.image_url} 
              alt="CCTV Frame Crop" 
              className="w-full h-full object-cover"
            />
            {/* Camera Overlay OSD */}
            <div className="absolute top-3 left-3 bg-black/60 px-2.5 py-1 rounded-md text-[10px] font-mono text-slate-200 backdrop-blur-sm border border-slate-700">
              VIGILANTEYE CCTV // {event.camera_id}
            </div>
            <div className="absolute bottom-3 right-3 bg-black/60 px-2.5 py-1 rounded-md text-[10px] font-mono text-slate-200 backdrop-blur-sm border border-slate-700">
              {dateStr} — {timeStr}
            </div>
          </div>

          {/* Telemetry metadata panel */}
          <div className="flex flex-col justify-between space-y-4 bg-muted/30 p-4 rounded-xl border border-border">
            <div className="space-y-3.5">
              <h4 className="text-sm font-semibold border-b border-border pb-2 uppercase tracking-wider text-muted-foreground">
                Telemetry Log
              </h4>
              
              <div className="flex items-center gap-3 text-sm">
                <Video className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-xs text-slate-500 leading-none">Location Node</p>
                  <p className="font-semibold text-foreground mt-1">{event.camera_name || event.camera_id}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Clock className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-xs text-slate-500 leading-none">Detection Time</p>
                  <p className="font-semibold text-foreground mt-1">{timeStr}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Calendar className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-xs text-slate-500 leading-none">Date Logged</p>
                  <p className="font-semibold text-foreground mt-1">{dateStr}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Gauge className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-xs text-slate-500 leading-none">Detected Speed</p>
                  <p className="font-semibold text-foreground mt-1">
                    {event.speed_kmh ? `${event.speed_kmh} km/h` : 'N/A'}
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3 pt-4 border-t border-border">
              {event.is_violation ? (
                <div className="flex items-center gap-2 text-xs font-semibold text-red-600 bg-red-50 border border-red-200 p-2.5 rounded-md">
                  <ShieldAlert className="h-4 w-4 shrink-0 text-red-500" />
                  <span>CRITICAL ALERT: Traffic Violation Logged!</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 p-2.5 rounded-md">
                  <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                  <span>No Speed/Watchlist Breaches</span>
                </div>
              )}

              <Button 
                onClick={handleTrackVehicle}
                className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-white font-semibold py-2 rounded-md shadow-xs cursor-pointer"
              >
                <MapPin className="h-4 w-4" />
                Track Vehicle
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
export default ImagePreviewModal;
