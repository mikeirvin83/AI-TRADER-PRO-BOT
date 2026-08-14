'use client';

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts';

const REGIME_COLORS: Record<string, string> = {
  'Strong Bullish Trend': '#22c55e',
  'Weak Bullish': '#86efac',
  'Ranging': '#facc15',
  'Weak Bearish': '#fca5a5',
  'Strong Bearish Trend': '#ef4444',
};

export default function RegimeChart({ data }: { data: Array<{ date: string; regime: string; confidence: number }> }) {
  if (!data?.length) return <div className="flex items-center justify-center h-full text-xs text-gray-500">No regime data</div>;

  const chartData = (data ?? []).map((d: any) => ({
    date: (d?.date ?? '').slice(5),
    confidence: ((d?.confidence ?? 0) * 100),
    regime: d?.regime ?? 'Unknown',
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <XAxis dataKey="date" tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
        <YAxis tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} domain={[0, 100]} />
        <Tooltip
          contentStyle={{ backgroundColor: '#12121a', border: '1px solid #1e1e2e', borderRadius: '8px', fontSize: 11 }}
          labelStyle={{ color: '#9ca3af' }}
          formatter={(value: any, _: any, props: any) => [`${value?.toFixed?.(0) ?? value}%`, props?.payload?.regime ?? 'Regime']}
        />
        <Bar dataKey="confidence" radius={[3, 3, 0, 0]}>
          {chartData.map((entry: any, index: number) => (
            <Cell key={index} fill={REGIME_COLORS[entry?.regime] ?? '#6b7280'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
