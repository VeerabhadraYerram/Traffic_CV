import { useState, useMemo } from 'react';
import { useEvents } from '@/hooks/use-events';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, Clock } from 'lucide-react';
import type { VehicleEvent } from '@/types';

interface SearchPanelProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  nodes: { event: VehicleEvent; camera: any }[];
}

export function SearchPanel({ searchQuery, onSearchChange, nodes }: SearchPanelProps) {
  const { data: events = [] } = useEvents();
  const [inputValue, setInputValue] = useState(searchQuery);

  // Auto-suggest matched plates from history
  const suggestions = useMemo(() => {
    if (!inputValue || inputValue.length < 2) return [];
    
    // Extract unique license plates that match input
    const plates = Array.from(new Set(
      events
        .filter(e => e.license_plate.toUpperCase().includes(inputValue.toUpperCase()))
        .map(e => e.license_plate)
    )).slice(0, 5); // limit suggestions to 5

    return plates;
  }, [events, inputValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearchChange(inputValue);
  };

  const handleSelectSuggestion = (plate: string) => {
    setInputValue(plate);
    onSearchChange(plate);
  };

  return (
    <Card className="w-72 bg-card/95 border border-border backdrop-blur-md shadow-lg rounded-xl ">
      <CardHeader className="px-4 py-2 border-b border-border bg-muted/30">
        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Tracking Engine
        </CardTitle>
      </CardHeader>
      <CardContent className="p-2 flex flex-col space-y-4">
        {/* Search Input */}
        <form onSubmit={handleSubmit} className="relative">
          <Input
            placeholder="Search plate (e.g. KA03)"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            className="h-8 pr-8 bg-input border-border text-foreground placeholder-slate-400 text-[11px] font-mono focus-visible:ring-primary rounded-md"
          />
          <Button 
            type="submit" 
            size="icon" 
            variant="ghost" 
            className="absolute right-0 top-0 h-8 w-8 text-slate-500 hover:text-foreground rounded-md"
          >
            <Search className="h-3.5 w-3.5" />
          </Button>
        </form>

        {/* Suggestion list */}
        {suggestions.length > 0 && (
          <div className="bg-muted border border-border rounded-md overflow-hidden text-xs">
            <span className="block px-3 py-1 bg-muted/60 text-[9px] uppercase tracking-wider text-muted-foreground border-b border-border font-semibold">
              Suggested Matches
            </span>
            <div className="flex flex-col">
              {suggestions.map(plate => (
                <button
                  key={plate}
                  onClick={() => handleSelectSuggestion(plate)}
                  className="px-3 py-2 text-left hover:bg-accent font-mono text-slate-700 hover:text-foreground border-b border-border/50 last:border-0 transition-colors"
                >
                  {plate}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Node checklist if a search is conducted */}
        {searchQuery && (
          <div className="flex flex-col space-y-3">
            <div className="border-t border-border pt-3">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                Vehicle Trajectory Log
              </span>
              <p className="text-xs text-foreground font-semibold mt-1 font-mono">
                Plate: {searchQuery.toUpperCase()}
              </p>
            </div>

            {nodes.length === 0 ? (
              <p className="text-xs text-slate-500 py-2">
                No route points captured for this license plate.
              </p>
            ) : (
              <div className="flex flex-col space-y-2 border-l border-border pl-3.5 relative py-1">
                {nodes.map((node) => {
                  const date = new Date(node.event.entry_time);
                  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                  
                  return (
                    <div key={node.event.event_id} className="relative group py-1">
                      {/* Timeline dot */}
                      <span className="absolute -left-[19.5px] top-3 h-2 w-2 rounded-full bg-primary border border-background animate-pulse" />
                      
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-semibold text-foreground">
                          {node.camera.location_name}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5 text-[10px] font-mono text-slate-500">
                          <span className="flex items-center gap-0.5"><Clock className="h-3.5 w-3.5" />{time}</span>
                          {node.event.speed_kmh && (
                            <span className={node.event.is_violation ? "text-destructive font-bold" : ""}>
                              {node.event.speed_kmh} km/h
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
export default SearchPanel;
