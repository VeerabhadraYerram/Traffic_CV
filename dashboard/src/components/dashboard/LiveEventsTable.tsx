import { useState, useMemo } from 'react';
import { useEvents } from '@/hooks/use-events';
import { useCameras } from '@/hooks/use-cameras';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ImagePreviewModal } from './ImagePreviewModal';
import { Eye, ShieldAlert, Search } from 'lucide-react';
import type { VehicleEvent } from '@/types';

export function LiveEventsTable() {
  const { data: events = [], isLoading } = useEvents();
  const { data: cameras = [] } = useCameras();

  // Search/Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCamera, setSelectedCamera] = useState('ALL');
  const [selectedType, setSelectedType] = useState('ALL');
  const [page, setPage] = useState(1);
  const itemsPerPage = 8;

  // Selected event for full screen dialog preview
  const [selectedPreviewEvent, setSelectedPreviewEvent] = useState<VehicleEvent | null>(null);

  // Clear filters
  const resetFilters = () => {
    setSearchTerm('');
    setSelectedCamera('ALL');
    setSelectedType('ALL');
    setPage(1);
  };

  // Filtered Events
  const filteredEvents = useMemo(() => {
    return events.filter(e => {
      const matchSearch = e.license_plate.toUpperCase().includes(searchTerm.toUpperCase());
      const matchCamera = selectedCamera === 'ALL' || e.camera_id === selectedCamera;
      
      let matchType = true;
      if (selectedType !== 'ALL') {
        const type = e.vehicle_type.toLowerCase();
        if (selectedType === 'SPEEDING') {
          matchType = e.is_violation && e.speed_kmh !== undefined && e.speed_kmh > (cameras.find(c => c.camera_id === e.camera_id)?.speed_limit_kmh ?? 60);
        } else if (selectedType === 'BLACKLISTED') {
          matchType = e.is_violation && !e.speed_kmh;
        } else {
          matchType = type.includes(selectedType.toLowerCase());
        }
      }

      return matchSearch && matchCamera && matchType;
    });
  }, [events, searchTerm, selectedCamera, selectedType, cameras]);

  // Pagination
  const totalPages = Math.ceil(filteredEvents.length / itemsPerPage);
  const paginatedEvents = useMemo(() => {
    const startIndex = (page - 1) * itemsPerPage;
    return filteredEvents.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredEvents, page]);

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm p-5 flex flex-col space-y-4">
      {/* Search & Filter Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h3 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase m-0">
          Live Ingestion Logs
        </h3>
        
        {/* Reset button */}
        {(searchTerm || selectedCamera !== 'ALL' || selectedType !== 'ALL') && (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={resetFilters} 
            className="text-xs text-primary hover:text-primary/90"
          >
            Clear Filters
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Plate Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
          <Input
            placeholder="Search license plate..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
            className="pl-9 bg-input border-border text-foreground placeholder-slate-400 text-xs focus-visible:ring-primary rounded-md"
          />
        </div>

        {/* Camera Select */}
        <Select 
          value={selectedCamera} 
          onValueChange={(value) => { setSelectedCamera(value); setPage(1); }}
        >
          <SelectTrigger className="bg-input border-border text-foreground text-xs focus:ring-primary rounded-md">
            <SelectValue placeholder="Filter by Camera" />
          </SelectTrigger>
          <SelectContent className="bg-popover border-border text-foreground rounded-md shadow-md">
            <SelectItem value="ALL">All Cameras</SelectItem>
            {cameras.map(c => (
              <SelectItem key={c.camera_id} value={c.camera_id}>
                {c.camera_id} — {c.location_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Violation / Vehicle Type Select */}
        <Select 
          value={selectedType} 
          onValueChange={(value) => { setSelectedType(value); setPage(1); }}
        >
          <SelectTrigger className="bg-input border-border text-foreground text-xs focus:ring-primary rounded-md">
            <SelectValue placeholder="Filter by Class / Alert" />
          </SelectTrigger>
          <SelectContent className="bg-popover border-border text-foreground rounded-md shadow-md">
            <SelectItem value="ALL">All Event Types</SelectItem>
            <SelectItem value="SPEEDING">Speeding Breaches</SelectItem>
            <SelectItem value="BLACKLISTED">Blacklist Flags</SelectItem>
            <SelectItem value="Car">Car</SelectItem>
            <SelectItem value="Bike">Bike</SelectItem>
            <SelectItem value="Truck">Truck</SelectItem>
            <SelectItem value="Bus">Bus</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Main Table */}
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent border-b border-border">
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">Snapshot</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">License Plate</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">Location Node</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">In-Time</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">Out-Time</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">Vehicle Details</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans">Detected Speed</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-xs font-sans text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [1, 2, 3, 4, 5].map(i => (
                <TableRow key={i} className="border-b border-border">
                  <TableCell><div className="h-10 w-16 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-24 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-32 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-20 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-20 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-28 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-5 w-16 bg-slate-200 animate-pulse rounded" /></TableCell>
                  <TableCell><div className="h-8 w-16 bg-slate-200 animate-pulse rounded ml-auto" /></TableCell>
                </TableRow>
              ))
            ) : paginatedEvents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-slate-500 text-xs">
                  No camera logs matched the selected search filters.
                </TableCell>
              </TableRow>
            ) : (
              paginatedEvents.map((event) => {
                const formatTime = (isoString?: string) => {
                  if (!isoString) return null;
                  const date = new Date(isoString);
                  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                };

                const inTime = formatTime(event.entry_time);
                const outTime = formatTime(event.exit_time);

                return (
                  <TableRow key={event.event_id} className="hover:bg-accent border-b border-border text-foreground">
                    {/* Snap Preview */}
                    <TableCell>
                      <div 
                        className="relative h-10 w-16 rounded-md overflow-hidden border border-border cursor-zoom-in bg-black group"
                        onClick={() => setSelectedPreviewEvent(event)}
                      >
                        <img 
                          src={event.image_url} 
                          alt="Crop" 
                          className="h-full w-full object-cover transition-transform group-hover:scale-110" 
                        />
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                          <Eye className="h-4.5 w-4.5 text-white" />
                        </div>
                      </div>
                    </TableCell>

                    {/* Plate */}
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <div className="inline-block px-2.5 py-1 font-mono font-bold text-xs text-slate-800 bg-slate-100 border border-slate-300 tracking-widest rounded-md shadow-xs leading-none">
                          {event.license_plate.toUpperCase()}
                        </div>
                      </div>
                    </TableCell>

                    {/* Camera Name */}
                    <TableCell className="text-xs">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-800">{event.camera_name || event.camera_id}</span>
                        <span className="text-[10px] text-slate-500 font-mono">{event.camera_id}</span>
                      </div>
                    </TableCell>

                    {/* In-Time */}
                    <TableCell className="text-xs font-mono">{inTime}</TableCell>

                    {/* Out-Time */}
                    <TableCell className="text-xs font-mono">
                      {outTime ? (
                        outTime
                      ) : (
                        <span className="inline-block px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-md">
                          Inside
                        </span>
                      )}
                    </TableCell>

                    {/* Vehicle Details */}
                    <TableCell className="text-xs">{event.vehicle_type}</TableCell>

                    {/* Speed */}
                    <TableCell className="text-xs">
                      {event.speed_kmh ? (
                        <div className="flex items-center gap-1.5 font-mono">
                          <span className={event.is_violation ? "text-destructive font-bold" : "text-slate-700"}>
                            {event.speed_kmh} km/h
                          </span>
                          {event.is_violation && (
                            <ShieldAlert className="h-3.5 w-3.5 text-destructive" />
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-500 font-mono">N/A</span>
                      )}
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="text-right">
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => setSelectedPreviewEvent(event)}
                        className="text-xs text-primary hover:text-primary/90 hover:bg-accent rounded-md"
                      >
                        Inspect
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-between text-xs pt-2">
          <span className="text-slate-500">
            Showing {(page - 1) * itemsPerPage + 1} to {Math.min(page * itemsPerPage, filteredEvents.length)} of {filteredEvents.length} logs
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
              className="h-8 text-xs border-border bg-secondary hover:bg-accent text-secondary-foreground rounded-md"
            >
              Prev
            </Button>
            <span className="text-foreground font-medium">Page {page} of {totalPages}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={page === totalPages}
              onClick={() => setPage(page + 1)}
              className="h-8 text-xs border-border bg-secondary hover:bg-accent text-secondary-foreground rounded-md"
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Zoom Dialog Modal */}
      <ImagePreviewModal
        event={selectedPreviewEvent}
        isOpen={selectedPreviewEvent !== null}
        onClose={() => setSelectedPreviewEvent(null)}
      />
    </div>
  );
}
export default LiveEventsTable;
