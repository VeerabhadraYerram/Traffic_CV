import { useAnalytics } from '@/hooks/use-analytics';
import { Card, CardContent } from '@/components/ui/card';
import { ShieldAlert, Car, Video, BellRing } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StatCardsGrid() {
  const { stats, isLoading } = useAnalytics();

  const cards = [
    {
      title: 'Live Speed Violations',
      value: stats?.liveSpeedViolations ?? 0,
      icon: ShieldAlert,
      color: 'text-destructive',
      bgColor: 'border-border hover:border-destructive/40 bg-card',
      pulse: true
    },
    {
      title: 'Total Vehicles Today',
      value: stats?.totalVehiclesToday ?? 0,
      icon: Car,
      color: 'text-primary',
      bgColor: 'border-border hover:border-primary/40 bg-card',
      pulse: false
    },
    {
      title: 'Active Camera Feeds',
      value: stats?.activeCameras ?? 0,
      icon: Video,
      color: 'text-emerald-500',
      bgColor: 'border-border hover:border-emerald-500/40 bg-card',
      pulse: false
    },
    {
      title: 'Pending Alerts',
      value: stats?.pendingAlertsCount ?? 0,
      icon: BellRing,
      color: 'text-amber-500',
      bgColor: 'border-border hover:border-amber-500/40 bg-card',
      pulse: (stats?.pendingAlertsCount ?? 0) > 0
    }
  ];

  return (
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, index) => {
        const Icon = card.icon;
        return (
          <Card key={index} className={cn("transition-all duration-200 rounded-xl shadow-sm border", card.bgColor)}>
            <CardContent className="p-6 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{card.title}</p>
                {isLoading ? (
                  <div className="h-9 w-16 bg-slate-200 animate-pulse rounded mt-2" />
                ) : (
                  <h3 className="text-3xl font-extrabold tracking-tight text-foreground mt-1 font-mono">
                    {card.value.toLocaleString()}
                  </h3>
                )}
              </div>
              <div className="relative">
                {card.pulse && (
                  <span className="absolute -top-1 -right-1 flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                  </span>
                )}
                <div className={cn("p-3 rounded-lg bg-muted border border-border", card.color)}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
export default StatCardsGrid;
