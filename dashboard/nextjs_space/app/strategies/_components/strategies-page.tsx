'use client';

import { useCallback, useState } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { cn } from '@/lib/utils';
import dynamic from 'next/dynamic';

const AllocationChart = dynamic(() => import('./allocation-chart'), { ssr: false, loading: () => <div className="h-[250px] bg-[#12121a] animate-pulse rounded-lg" /> });

const PIPELINE_STAGES = ['RESEARCH', 'HYPOTHESIS', 'BACKTEST', 'OUT-OF-SAMPLE', 'WALK-FORWARD', 'MONTE CARLO', 'PAPER', 'SHADOW', 'LIVE'];

export function StrategiesPage() {
  const stratFetcher = useCallback(() => api.getStrategies(), []);
  const pipeFetcher = useCallback(() => api.getStrategyPipeline(), []);
  const { data: strategies, isMock } = useApiPolling(stratFetcher, 10000);
  const { data: pipeline } = useApiPolling(pipeFetcher, 30000);
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null);

  const allocationData = (strategies ?? []).filter((s: any) => (s?.allocation_pct ?? 0) > 0).map((s: any) => ({
    name: s?.type ?? 'Unknown',
    value: s?.allocation_pct ?? 0,
  }));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-display font-bold text-white tracking-tight">Strategy Portfolio</h2>
        <MockIndicator isMock={isMock} />
      </div>

      {/* Strategy Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-[#1a1a2e]">
              <th className="text-left py-2 font-medium">Name</th>
              <th className="text-left py-2 font-medium">Version</th>
              <th className="text-left py-2 font-medium">Status</th>
              <th className="text-right py-2 font-medium">Win Rate</th>
              <th className="text-right py-2 font-medium">Expectancy</th>
              <th className="text-right py-2 font-medium">PF</th>
              <th className="text-right py-2 font-medium">Sharpe</th>
              <th className="text-right py-2 font-medium">Max DD</th>
              <th className="text-right py-2 font-medium">Trades</th>
              <th className="text-right py-2 font-medium">Last Trade</th>
            </tr>
          </thead>
          <tbody>
            {(strategies ?? []).map((s: any, i: number) => (
              <tr
                key={i}
                className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 cursor-pointer transition-colors"
                onClick={() => setSelectedStrategy(s)}
              >
                <td className="py-2 font-medium text-white">{s?.name}</td>
                <td className="py-2 font-mono text-gray-400">{s?.version}</td>
                <td className="py-2"><DataBadge variant={s?.status ?? 'ACTIVE'} /></td>
                <td className="py-2 text-right font-mono text-gray-300">{(s?.win_rate ?? 0).toFixed(1)}%</td>
                <td className={cn('py-2 text-right font-mono', (s?.expectancy ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>{(s?.expectancy ?? 0).toFixed(2)}</td>
                <td className={cn('py-2 text-right font-mono', (s?.profit_factor ?? 0) >= 1 ? 'text-emerald-400' : 'text-red-400')}>{(s?.profit_factor ?? 0).toFixed(2)}</td>
                <td className={cn('py-2 text-right font-mono', (s?.sharpe ?? 0) >= 1 ? 'text-blue-400' : 'text-amber-400')}>{(s?.sharpe ?? 0).toFixed(2)}</td>
                <td className="py-2 text-right font-mono text-red-400">{(s?.max_dd ?? 0).toFixed(1)}%</td>
                <td className="py-2 text-right font-mono text-gray-300">{s?.total_trades}</td>
                <td className="py-2 text-right font-mono text-gray-400">{(s?.last_trade ?? '').slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Allocation Chart */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Capital Allocation</h3>
          <div className="h-[250px]">
            <AllocationChart data={allocationData} />
          </div>
        </div>

        {/* Pipeline View */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Promotion Pipeline</h3>
          <div className="space-y-3">
            {PIPELINE_STAGES.map((stage) => {
              const items = (pipeline ?? []).filter((p: any) => p?.stage === stage);
              return (
                <div key={stage} className="flex items-start gap-2">
                  <div className="w-28 shrink-0">
                    <span className="text-[9px] font-mono text-gray-500 uppercase">{stage}</span>
                  </div>
                  <div className="flex-1 flex flex-wrap gap-1.5 min-h-[20px]">
                    {items.map((item: any, idx: number) => (
                      <span key={idx} className="px-2 py-0.5 bg-blue-500/10 text-blue-400 text-[10px] font-mono rounded border border-blue-500/20">
                        {item?.name} <span className="text-gray-500">({item?.days_in_stage}d)</span>
                      </span>
                    ))}
                    {items.length === 0 && <span className="text-[10px] text-gray-600">—</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Strategy Detail Modal */}
      {selectedStrategy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setSelectedStrategy(null)}>
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-6 max-w-lg w-full mx-4 shadow-2xl" onClick={(e: any) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-display font-bold text-white">{selectedStrategy?.name}</h2>
              <DataBadge variant={selectedStrategy?.status ?? 'ACTIVE'} />
            </div>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <StatBox label="Win Rate" value={`${(selectedStrategy?.win_rate ?? 0).toFixed(1)}%`} />
              <StatBox label="Expectancy" value={(selectedStrategy?.expectancy ?? 0).toFixed(2)} />
              <StatBox label="Profit Factor" value={(selectedStrategy?.profit_factor ?? 0).toFixed(2)} />
              <StatBox label="Sharpe Ratio" value={(selectedStrategy?.sharpe ?? 0).toFixed(2)} />
              <StatBox label="Max Drawdown" value={`${(selectedStrategy?.max_dd ?? 0).toFixed(1)}%`} />
              <StatBox label="Total Trades" value={String(selectedStrategy?.total_trades ?? 0)} />
            </div>
            <div className="mb-3">
              <span className="text-[10px] text-gray-500 uppercase">Strategy Type</span>
              <p className="text-sm text-gray-300 mt-0.5">{selectedStrategy?.type}</p>
            </div>
            <div className="mb-3">
              <span className="text-[10px] text-gray-500 uppercase">Version</span>
              <p className="text-sm font-mono text-gray-300 mt-0.5">{selectedStrategy?.version}</p>
            </div>
            <button onClick={() => setSelectedStrategy(null)} className="w-full mt-2 px-4 py-2 rounded-lg bg-[#1a1a2e] text-gray-300 text-sm hover:bg-[#222238] transition-colors">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#0d0d14] rounded-lg p-3 border border-[#1a1a2e]">
      <span className="text-[9px] text-gray-500 uppercase">{label}</span>
      <p className="text-sm font-mono font-medium text-white mt-0.5">{value}</p>
    </div>
  );
}
