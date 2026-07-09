import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface ViolationBarChartProps {
  data: any[];
  isLoading: boolean;
}

export function ViolationBarChart({ data, isLoading }: ViolationBarChartProps) {
  return (
    <Card className="rounded-xl shadow-sm border border-border bg-card">
      <CardHeader className="p-5 border-b border-border">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground m-0">
          Violation Density Profile
        </CardTitle>
        <CardDescription className="text-slate-500 text-[10px] uppercase">
          Chronological density log sorted by offence type
        </CardDescription>
      </CardHeader>
      <CardContent className="p-6 h-72">
        {isLoading ? (
          <div className="h-full w-full bg-slate-200 animate-pulse rounded-lg" />
        ) : data.length === 0 ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs">
            No violation data logs recorded.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
              <Legend 
                verticalAlign="bottom" 
                height={24}
                iconType="rect"
                iconSize={8}
                formatter={(value) => <span className="text-[10px] text-slate-600 font-medium">{value}</span>}
              />
              <Bar dataKey="Speeding" stackId="a" fill="var(--destructive)" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Red Light" stackId="a" fill="#eab308" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Blacklisted" stackId="a" fill="var(--primary)" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Unauthorized Entry" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
export default ViolationBarChart;
