import { useState } from 'react';
import { useAnalytics } from '@/hooks/use-analytics';
import { TrafficLineChart } from '@/components/analytics/TrafficLineChart';
import { VehicleTypeDonut } from '@/components/analytics/VehicleTypeDonut';
import { ViolationBarChart } from '@/components/analytics/ViolationBarChart';
import { CameraAlertChart } from '@/components/analytics/CameraAlertChart';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { CalendarDays, CalendarRange, Calendar } from 'lucide-react';

export function AnalyticsPage() {
  const [timeframe, setTimeframe] = useState<'day' | 'week' | 'month'>('day');
  
  const {
    isLoading,
    trafficChartData,
    vehicleCompositionData,
    violationDensityData,
    cameraAlertData
  } = useAnalytics(timeframe);

  return (
    <div className="flex flex-col space-y-6">
      {/* Filters control bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-card border border-border p-4 rounded-xl shadow-sm">
        <div>
          <h2 className="text-base font-bold text-foreground m-0">Platform Statistics</h2>
          <p className="text-xs text-slate-500 mt-1">Aggregated historical insights from ANPR node networks</p>
        </div>

        {/* Timeframe Toggles */}
        <div className="bg-muted p-1 border border-border rounded-lg flex items-center">
          <ToggleGroup 
            type="single" 
            value={timeframe} 
            onValueChange={(val) => { if (val) setTimeframe(val as any); }}
            className="flex gap-1"
          >
            <ToggleGroupItem value="day" className="data-[state=active]:bg-background data-[state=active]:text-primary px-3 py-1.5 h-8 text-xs font-semibold text-muted-foreground rounded-md shadow-xs">
              <CalendarDays className="h-3.5 w-3.5 mr-1.5" />
              Last 24h
            </ToggleGroupItem>
            <ToggleGroupItem value="week" className="data-[state=active]:bg-background data-[state=active]:text-primary px-3 py-1.5 h-8 text-xs font-semibold text-muted-foreground rounded-md shadow-xs">
              <CalendarRange className="h-3.5 w-3.5 mr-1.5" />
              7 Days
            </ToggleGroupItem>
            <ToggleGroupItem value="month" className="data-[state=active]:bg-background data-[state=active]:text-primary px-3 py-1.5 h-8 text-xs font-semibold text-muted-foreground rounded-md shadow-xs">
              <Calendar className="h-3.5 w-3.5 mr-1.5" />
              30 Days
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      {/* 2x2 Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Total traffic line chart */}
        <TrafficLineChart data={trafficChartData} isLoading={isLoading} />

        {/* Vehicle composition donut chart */}
        <VehicleTypeDonut data={vehicleCompositionData} isLoading={isLoading} />

        {/* Violation density stacked bars */}
        <ViolationBarChart data={violationDensityData} isLoading={isLoading} />

        {/* Camera-wise alerts horizontal bars */}
        <CameraAlertChart data={cameraAlertData} isLoading={isLoading} />
      </div>
    </div>
  );
}
export default AnalyticsPage;
