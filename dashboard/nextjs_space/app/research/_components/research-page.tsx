'use client';

import { useCallback } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { cn } from '@/lib/utils';
import { FlaskConical, CheckCircle, XCircle, Clock, Brain } from 'lucide-react';

export function ResearchPage() {
  const hypFetcher = useCallback(() => api.getHypotheses(), []);
  const btFetcher = useCallback(() => api.getBacktests(), []);
  const kFetcher = useCallback(() => api.getKnowledge(), []);
  const { data: hypotheses, isMock: hypMock } = useApiPolling(hypFetcher, 15000);
  const { data: backtests, isMock: btMock } = useApiPolling(btFetcher, 15000);
  const { data: knowledge, isMock: kMock } = useApiPolling(kFetcher, 15000);

  const totalHyp = (hypotheses ?? []).length;
  const passedHyp = (hypotheses ?? []).filter((h: any) => h?.status === 'PASSED').length;
  const passRate = totalHyp > 0 ? ((passedHyp / totalHyp) * 100).toFixed(0) : '0';

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-display font-bold text-white tracking-tight">Research Lab</h2>
        <MockIndicator isMock={hypMock} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <FlaskConical size={15} className="text-blue-400 mb-1" />
          <p className="text-[10px] text-gray-500 uppercase">Total Hypotheses</p>
          <p className="text-xl font-display font-bold text-white">{totalHyp}</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <CheckCircle size={15} className="text-emerald-400 mb-1" />
          <p className="text-[10px] text-gray-500 uppercase">Pass Rate</p>
          <p className="text-xl font-display font-bold text-emerald-400">{passRate}%</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <Clock size={15} className="text-amber-400 mb-1" />
          <p className="text-[10px] text-gray-500 uppercase">In Testing</p>
          <p className="text-xl font-display font-bold text-white">{(hypotheses ?? []).filter((h: any) => h?.status === 'TESTING').length}</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <XCircle size={15} className="text-red-400 mb-1" />
          <p className="text-[10px] text-gray-500 uppercase">Failed</p>
          <p className="text-xl font-display font-bold text-red-400">{(hypotheses ?? []).filter((h: any) => h?.status === 'FAILED').length}</p>
        </div>
      </div>

      {/* Hypothesis Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Hypotheses</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-[#1a1a2e]">
              <th className="text-left py-2 font-medium">ID</th>
              <th className="text-left py-2 font-medium">Title</th>
              <th className="text-left py-2 font-medium">Status</th>
              <th className="text-right py-2 font-medium">Confidence</th>
              <th className="text-left py-2 font-medium">Assets</th>
              <th className="text-left py-2 font-medium">TF</th>
              <th className="text-left py-2 font-medium">Regime</th>
              <th className="text-right py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {(hypotheses ?? []).map((h: any, i: number) => (
              <tr key={i} className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 transition-colors">
                <td className="py-2 font-mono text-blue-400">{h?.id}</td>
                <td className="py-2 text-gray-300 max-w-[300px] truncate">{h?.title}</td>
                <td className="py-2"><DataBadge variant={h?.status ?? 'TESTING'} /></td>
                <td className="py-2 text-right font-mono text-gray-300">{((h?.confidence ?? 0) * 100).toFixed(0)}%</td>
                <td className="py-2 text-gray-400 font-mono text-[10px]">{(h?.assets ?? []).join(', ')}</td>
                <td className="py-2 font-mono text-gray-400">{h?.timeframe}</td>
                <td className="py-2 text-gray-400">{h?.regime}</td>
                <td className="py-2 text-right font-mono text-gray-500">{h?.created}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Backtests */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Recent Backtests</h3>
            <MockIndicator isMock={btMock} />
          </div>
          <div className="space-y-2">
            {(backtests ?? []).map((b: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-[#1a1a2e] last:border-0">
                <div>
                  <p className="text-xs font-medium text-white">{b?.strategy}</p>
                  <p className="text-[10px] font-mono text-gray-500">{b?.date}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-[10px] text-gray-500">Sharpe</p>
                    <p className={cn('text-xs font-mono', (b?.sharpe ?? 0) >= 1 ? 'text-emerald-400' : 'text-red-400')}>{(b?.sharpe ?? 0).toFixed(2)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-gray-500">WR</p>
                    <p className="text-xs font-mono text-gray-300">{(b?.win_rate ?? 0).toFixed(1)}%</p>
                  </div>
                  <DataBadge variant={b?.status ?? 'PASSED'} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Knowledge Feed */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-1.5"><Brain size={14} className="text-purple-400" /> Knowledge Memory</h3>
            <MockIndicator isMock={kMock} />
          </div>
          <div className="space-y-3">
            {(knowledge ?? []).map((k: any, i: number) => (
              <div key={i} className="border-l-2 border-purple-500/30 pl-3 py-1">
                <p className="text-xs text-gray-300">{k?.entry}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[9px] font-mono text-gray-500">{(k?.timestamp ?? '').slice(0, 16).replace('T', ' ')}</span>
                  <span className="text-[9px] text-purple-400/70">{k?.source}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
