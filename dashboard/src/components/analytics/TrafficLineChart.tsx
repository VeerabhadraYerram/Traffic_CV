import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface TrafficLineChartProps {
  data: { name: string; count: number }[];
  isLoading: boolean;
}

export function TrafficLineChart({ data, isLoading }: TrafficLineChartProps) {
  return (
    <Card className="rounded-xl shadow-sm border border-border bg-card">
      <CardHeader className="p-5 border-b border-border">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground m-0">
          Total Traffic Over Time
        </CardTitle>
        <CardDescription className="text-slate-500 text-[10px] uppercase">
          Cumulative vehicle detections across all nodes
        </CardDescription>
      </CardHeader>
      <CardContent className="p-6 h-72">
        {isLoading ? (
          <div className="h-full w-full bg-slate-200 animate-pulse rounded-lg" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="trafficGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis 
                dataKey="name" 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                className="font-mono"
              />
              <YAxis 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                allowDecimals={false}
                className="font-mono"
              />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--popover)', borderColor: 'var(--border)', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                labelStyle={{ color: 'var(--muted-foreground)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                itemStyle={{ color: 'var(--foreground)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}
              />
              <Area 
                type="monotone" 
                dataKey="count" 
                name="Vehicles"
                stroke="var(--primary)" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#trafficGradient)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
export default TrafficLineChart;
