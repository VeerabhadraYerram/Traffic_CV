import type { Violation } from '@/types';
import { useAcknowledgeViolation } from '@/hooks/use-violations';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ShieldAlert, Check, AlertTriangle, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface AlertCardProps {
  violation: Violation;
}

export function AlertCard({ violation }: AlertCardProps) {
  const acknowledgeMutation = useAcknowledgeViolation();

  const handleAcknowledge = () => {
    acknowledgeMutation.mutate(
      { violationId: violation.violation_id, status: 'ACKNOWLEDGED' },
      {
        onSuccess: () => {
          toast.success(`Alert acknowledged for plate ${violation.license_plate}`);
        },
        onError: () => {
          toast.error('Failed to acknowledge alert');
        }
      }
    );
  };

  const handleEscalate = () => {
    acknowledgeMutation.mutate(
      { violationId: violation.violation_id, status: 'ESCALATED' },
      {
        onSuccess: () => {
          toast.warning(`Alert escalated for plate ${violation.license_plate} to highway patrol!`);
        },
        onError: () => {
          toast.error('Failed to escalate alert');
        }
      }
    );
  };

  // Severity config
  const severityStyles = {
    CRITICAL: {
      border: '',
      badge: 'bg-destructive/10 text-destructive border border-destructive/20 rounded-md',
      icon: ShieldAlert
    },
    HIGH: {
      border: '',
      badge: 'bg-primary/10 text-primary border border-primary/20 rounded-md',
      icon: AlertTriangle
    },
    MEDIUM: {
      border: '',
      badge: 'bg-amber-500/10 text-amber-600 border border-amber-500/20 rounded-md',
      icon: AlertTriangle
    },
    LOW: {
      border: '',
      badge: 'bg-blue-500/10 text-blue-600 border border-blue-500/20 rounded-md',
      icon: AlertTriangle
    }
  };

  const style = severityStyles[violation.severity_level];
  const time = new Date(violation.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  return (
    <Card className={cn("bg-card border border-border rounded-lg shadow-sm hover:shadow-md transition-shadow", style.border)}>
      <CardContent className="p-4 flex flex-col space-y-3">
        <div className="flex items-center justify-between">
          <Badge className={cn("font-semibold px-1.5 py-0.5", style.badge)}>
            {violation.violation_type}
          </Badge>
          <span className="text-[10px] text-slate-500 font-mono">{time}</span>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <div className="inline-block px-2 py-0.5 font-mono font-bold text-xs text-slate-800 bg-slate-100 border border-slate-300 tracking-wider rounded-md leading-none">
              {violation.license_plate.toUpperCase()}
            </div>
            {violation.recorded_value > 0 && (
              <span className="text-xs text-red-600 font-semibold font-mono">
                ({Math.round(violation.recorded_value)} km/h in {violation.zone_limit} zone)
              </span>
            )}
          </div>
          
          <p className="text-xs text-muted-foreground mt-1.5">
            {violation.violation_type === 'BLACKLISTED' 
              ? 'Watchlisted vehicle flagged in monitoring area.' 
              : violation.violation_type === 'SPEEDING' 
                ? 'Speed limit breach detected.' 
                : 'Traffic violation logged by camera.'
            }
          </p>
        </div>

        {violation.status === 'UNRESOLVED' && (
          <div className="flex gap-2 pt-1">
            <Button 
              size="sm" 
              variant="outline" 
              onClick={handleAcknowledge}
              disabled={acknowledgeMutation.isPending}
              className="flex-1 text-xs border-border bg-secondary hover:bg-accent text-secondary-foreground rounded-md"
            >
              <Check className="h-3 w-3 mr-1" />
              Ack
            </Button>
            <Button 
              size="sm" 
              onClick={handleEscalate}
              disabled={acknowledgeMutation.isPending}
              className="flex-1 text-xs bg-red-50 text-red-600 border border-red-200 hover:bg-red-600 hover:text-white rounded-md"
            >
              <ArrowRight className="h-3 w-3 mr-1" />
              Escalate
            </Button>
          </div>
        )}

        {violation.status !== 'UNRESOLVED' && (
          <div className="text-xs text-slate-500 font-medium pt-1 flex items-center gap-1.5 font-mono">
            <span className={cn(
              "h-1.5 w-1.5 rounded-full",
              violation.status === 'RESOLVED' ? "bg-success" :
              violation.status === 'ESCALATED' ? "bg-destructive" : "bg-blue-400"
            )}></span>
            <span className="uppercase text-[10px] tracking-wider">
              {violation.status}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
export default AlertCard;
