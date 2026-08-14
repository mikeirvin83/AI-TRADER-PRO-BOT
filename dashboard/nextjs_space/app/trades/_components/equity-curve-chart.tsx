'use client';

import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

export default function EquityCurveChart({ data }: { data: Array<{ day: number; date: string; equity: number }> }) {
  if (!data?.length) return <div className="flex items-center justify-center h-full text-xs text-gray-500">No equity data</div>;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} interval="preserveStartEnd" />
        <YAxis tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          contentStyle={{ backgroundColor: '#12121a', border: '1px solid #1e1e2e', borderRadius: '8px', fontSize: 11 }}
          labelStyle={{ color: '#9ca3af' }}
          formatter={(value: any) => [`$${Number(value ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Equity']}
        />
        <Area type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} fill="url(#equityGrad)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
