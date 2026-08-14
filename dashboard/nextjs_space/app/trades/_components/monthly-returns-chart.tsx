'use client';

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts';

export default function MonthlyReturnsChart({ data }: { data: Array<{ month: string; returns: number }> }) {
  if (!data?.length) return <div className="flex items-center justify-center h-full text-xs text-gray-500">No returns data</div>;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <XAxis dataKey="month" tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
        <YAxis tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip
          contentStyle={{ backgroundColor: '#12121a', border: '1px solid #1e1e2e', borderRadius: '8px', fontSize: 11 }}
          labelStyle={{ color: '#9ca3af' }}
          formatter={(value: any) => [`${Number(value ?? 0).toFixed(1)}%`, 'Return']}
        />
        <Bar dataKey="returns" radius={[3, 3, 0, 0]}>
          {(data ?? []).map((entry: any, index: number) => (
            <Cell key={index} fill={(entry?.returns ?? 0) >= 0 ? '#22c55e' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
