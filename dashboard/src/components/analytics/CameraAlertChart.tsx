import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface CameraAlertChartProps {
  data: { name: string; count: number }[];
  isLoading: boolean;
}

export function CameraAlertChart({ data, isLoading }: CameraAlertChartProps) {
  return (
    <Card className="rounded-xl shadow-sm border border-border bg-card">
      <CardHeader className="p-5 border-b border-border">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground m-0">
          Camera-wise Alert Counts
        </CardTitle>
        <CardDescription className="text-slate-500 text-[10px] uppercase">
          Top 5 reporting nodes ranked by violation volume
        </CardDescription>
      </CardHeader>
      <CardContent className="p-6 h-72">
        {isLoading ? (
          <div className="h-full w-full bg-slate-200 animate-pulse rounded-lg" />
        ) : data.length === 0 ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs">
            No camera violations logged yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 10, right: 10, left: 15, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis 
                type="number" 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                allowDecimals={false}
                className="font-mono"
              />
              <YAxis 
                type="category" 
                dataKey="name" 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                width={100}
                className="font-mono"
              />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--popover)', borderColor: 'var(--border)', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                labelStyle={{ color: 'var(--muted-foreground)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}
                itemStyle={{ color: 'var(--foreground)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}
              />
              <Bar 
                dataKey="count" 
                name="Violations"
                fill="var(--primary)" 
                radius={[0, 4, 4, 0]} 
                barSize={16}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
export default CameraAlertChart;
