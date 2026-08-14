'use client';

import { useCallback } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { cn } from '@/lib/utils';
import { ShieldAlert, AlertCircle } from 'lucide-react';
import dynamic from 'next/dynamic';

const CorrelationHeatmap = dynamic(() => import('./correlation-heatmap'), { ssr: false, loading: () => <div className="h-[300px] bg-[#12121a] animate-pulse rounded-lg" /> });

export function RiskPage() {
  const riskFetcher = useCallback(() => api.getRisk(), []);
  const { data: risk, isMock } = useApiPolling(riskFetcher, 5000);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-display font-bold text-white tracking-tight">Risk Monitor</h2>
        <MockIndicator isMock={isMock} />
      </div>

      {/* Risk Limits */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <RiskGauge label="Risk Per Trade" used={risk?.risk_per_trade?.used ?? 0} max={risk?.risk_per_trade?.max ?? 2} suffix="%" />
        <RiskGauge label="Daily Loss" used={risk?.daily_loss?.used ?? 0} max={risk?.daily_loss?.max ?? 3} suffix="%" />
        <RiskGauge label="Weekly Loss" used={risk?.weekly_loss?.used ?? 0} max={risk?.weekly_loss?.max ?? 6} suffix="%" />
        <RiskGauge label="Portfolio Drawdown" used={risk?.portfolio_drawdown?.current ?? 0} max={risk?.portfolio_drawdown?.max ?? 15} suffix="%" />
        <RiskGauge label="Simultaneous Positions" used={risk?.simultaneous_positions?.current ?? 0} max={risk?.simultaneous_positions?.max ?? 10} suffix="" />
        <RiskGauge label="Correlated Exposure" used={risk?.correlated_exposure?.current ?? 0} max={risk?.correlated_exposure?.max ?? 60} suffix="%" />
      </div>

      {/* Circuit Breaker */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center gap-3">
          <div className={cn('w-4 h-4 rounded-full', risk?.circuit_breaker?.status === 'NORMAL' ? 'bg-emerald-500' : 'bg-red-500 animate-pulse')} />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-300">Circuit Breaker</span>
              <DataBadge variant={risk?.circuit_breaker?.status ?? 'NORMAL'} />
            </div>
            {risk?.circuit_breaker?.reason && (
              <p className="text-xs text-red-400 mt-0.5">{risk?.circuit_breaker?.reason}</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Risk Events Log */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-1.5"><ShieldAlert size={14} className="text-amber-400" /> Risk Events</h3>
          <div className="space-y-2 max-h-[350px] overflow-y-auto scrollbar-none">
            {(risk?.risk_events ?? []).map((e: any, i: number) => (
              <div key={i} className="flex items-start gap-2 py-2 border-b border-[#1a1a2e] last:border-0">
                <AlertCircle size={13} className={cn(
                  'mt-0.5 shrink-0',
                  e?.severity === 'CRITICAL' ? 'text-red-400' : e?.severity === 'WARNING' ? 'text-amber-400' : 'text-blue-400'
                )} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <DataBadge variant={e?.severity ?? 'INFO'} />
                    <span className="text-[10px] font-mono text-gray-500">{(e?.timestamp ?? '').slice(0, 16).replace('T', ' ')}</span>
                  </div>
                  <p className="text-xs text-gray-300 mt-0.5">{e?.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Correlation Matrix */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Position Correlation Matrix</h3>
          <CorrelationHeatmap matrix={risk?.correlation_matrix ?? { symbols: [], values: [] }} />
        </div>
      </div>
    </div>
  );
}

function RiskGauge({ label, used, max, suffix }: { label: string; used: number; max: number; suffix: string }) {
  const pct = max > 0 ? Math.min((used / max) * 100, 100) : 0;
  const color = pct > 80 ? 'text-red-400' : pct > 50 ? 'text-amber-400' : 'text-emerald-400';
  const barColor = pct > 80 ? 'bg-red-500' : pct > 50 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-medium">{label}</span>
        <span className={cn('text-xs font-mono font-bold', color)}>{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-2 bg-[#1a1a2e] rounded-full overflow-hidden mb-2">
        <div className={cn('h-full rounded-full transition-all duration-700', barColor)} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-gray-400">Used: {suffix ? used.toFixed(1) : used}{suffix}</span>
        <span className="text-[10px] font-mono text-gray-500">Max: {max}{suffix}</span>
      </div>
    </div>
  );
}
