'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4'];

export default function AllocationChart({ data }: { data: Array<{ name: string; value: number }> }) {
  if (!data?.length) return <div className="flex items-center justify-center h-full text-xs text-gray-500">No allocation data</div>;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((_: any, index: number) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ backgroundColor: '#12121a', border: '1px solid #1e1e2e', borderRadius: '8px', fontSize: 11 }}
          itemStyle={{ color: '#e5e7eb' }}
          formatter={(value: any) => [`${value}%`, 'Allocation']}
        />
        <Legend verticalAlign="top" wrapperStyle={{ fontSize: 11, color: '#9ca3af' }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
