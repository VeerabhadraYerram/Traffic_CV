import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface VehicleTypeDonutProps {
  data: { name: string; value: number }[];
  isLoading: boolean;
}

const COLORS = ['#0284c7', '#10b981', '#06b6d4', '#f59e0b', '#ef4444', '#a855f7', '#64748b'];

export function VehicleTypeDonut({ data, isLoading }: VehicleTypeDonutProps) {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Card className="rounded-xl shadow-sm border border-border bg-card">
      <CardHeader className="p-5 border-b border-border">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground m-0">
          Vehicle Composition
        </CardTitle>
        <CardDescription className="text-slate-500 text-[10px] uppercase">
          Classification breakdown of active fleet
        </CardDescription>
      </CardHeader>
      <CardContent className="p-6 h-72 flex flex-col justify-between">
        {isLoading ? (
          <div className="h-full w-full bg-slate-200 animate-pulse rounded-lg" />
        ) : data.length === 0 ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs">
            No vehicle composition data.
          </div>
        ) : (
          <div className="relative w-full h-full flex items-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="40%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {data.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => [`${value} (${((Number(value) / total) * 100).toFixed(1)}%)`, 'Count']}
                  contentStyle={{ backgroundColor: 'var(--popover)', borderColor: 'var(--border)', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                  itemStyle={{ color: 'var(--foreground)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}
                />
                <Legend 
                  layout="vertical" 
                  align="right" 
                  verticalAlign="middle"
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => {
                    const item = data.find(d => d.name === value);
                    const count = item ? item.value : 0;
                    return <span className="text-[11px] text-slate-700 font-medium font-sans">{value} <span className="font-mono">({count})</span></span>;
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            
            {/* Centered Stats Text */}
            <div className="absolute left-[28%] top-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Total</span>
              <span className="block text-2xl font-extrabold text-foreground leading-none mt-0.5 font-mono">{total}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
export default VehicleTypeDonut;
