import { useState, useMemo } from 'react';
import { useViolations } from '@/hooks/use-violations';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertCard } from './AlertCard';
import { Button } from '@/components/ui/button';
import { BellRing, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

export function AlertsPanel() {
  const { data: violations = [], isLoading } = useViolations();
  const [filter, setFilter] = useState<'UNRESOLVED' | 'ACKNOWLEDGED' | 'ALL'>('UNRESOLVED');

  const filteredViolations = useMemo(() => {
    // Show max 20 alerts
    let list = violations;
    if (filter === 'UNRESOLVED') {
      list = violations.filter(v => v.status === 'UNRESOLVED' || v.status === 'ESCALATED');
    } else if (filter === 'ACKNOWLEDGED') {
      list = violations.filter(v => v.status === 'ACKNOWLEDGED' || v.status === 'RESOLVED');
    }
    return list.slice(0, 20);
  }, [violations, filter]);

  return (
    <div className="flex flex-col h-full bg-card border border-border rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BellRing className="h-5 w-5 text-primary animate-pulse" />
          <h2 className="text-sm font-semibold text-foreground tracking-wider uppercase m-0">Recent Alerts</h2>
        </div>
        <span className="bg-destructive/15 text-destructive border border-destructive/30 px-2 py-0.5 rounded-md text-[10px] font-bold font-mono">
          {violations.filter(v => v.status === 'UNRESOLVED').length} Active
        </span>
      </div>

      {/* Filter Tabs */}
      <div className="flex border-b border-border bg-muted/40 p-1">
        {(['UNRESOLVED', 'ACKNOWLEDGED', 'ALL'] as const).map(tab => (
          <Button
            key={tab}
            variant="ghost"
            size="sm"
            onClick={() => setFilter(tab)}
            className={cn(
              "flex-1 text-[11px] font-semibold py-1 px-2 h-7 rounded-md hover:bg-accent",
              filter === tab ? "bg-accent text-primary font-bold shadow-xs" : "text-muted-foreground"
            )}
          >
            {tab === 'UNRESOLVED' ? 'Active' : tab === 'ACKNOWLEDGED' ? 'Resolved' : 'All Logs'}
          </Button>
        ))}
      </div>

      {/* Alerts list */}
      <ScrollArea className="flex-1 min-h-0 p-4">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-28 bg-slate-200 animate-pulse rounded-lg border border-border" />
            ))}
          </div>
        ) : filteredViolations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500 space-y-3">
            <Sparkles className="h-8 w-8 text-slate-600" />
            <p className="text-xs font-medium">All clear! No alerts matching filter.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredViolations.map(v => (
              <AlertCard key={v.violation_id} violation={v} />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
export default AlertsPanel;
