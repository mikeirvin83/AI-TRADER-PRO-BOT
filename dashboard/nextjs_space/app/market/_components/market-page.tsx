'use client';

import { useCallback } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { cn } from '@/lib/utils';
import { Newspaper, CalendarDays, BarChart3, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import dynamic from 'next/dynamic';

const RegimeChart = dynamic(() => import('./regime-chart'), { ssr: false, loading: () => <div className="h-[200px] bg-[#12121a] animate-pulse rounded-lg" /> });

export function MarketPage() {
  const regimeFetcher = useCallback(() => api.getRegime(), []);
  const newsFetcher = useCallback(() => api.getNews(), []);
  const calFetcher = useCallback(() => api.getCalendar(), []);
  const volFetcher = useCallback(() => api.getVolatility(), []);

  const { data: regime, isMock: regMock } = useApiPolling(regimeFetcher, 10000);
  const { data: news, isMock: newsMock } = useApiPolling(newsFetcher, 30000);
  const { data: calendar, isMock: calMock } = useApiPolling(calFetcher, 60000);
  const { data: volatility, isMock: volMock } = useApiPolling(volFetcher, 10000);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-display font-bold text-white tracking-tight">Market Intelligence</h2>
        <MockIndicator isMock={regMock} />
      </div>

      {/* Regime History Chart */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Regime History (30 Days)</h3>
        <div className="h-[200px]">
          <RegimeChart data={regime?.regime_history ?? []} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Volatility Panel */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-1.5"><BarChart3 size={14} className="text-amber-400" /> Volatility</h3>
            <MockIndicator isMock={volMock} />
          </div>
          <div className="space-y-3">
            <div>
              <span className="text-[10px] text-gray-500 uppercase">VIX Proxy</span>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-display font-bold text-white">{(volatility?.vix ?? 0).toFixed(2)}</span>
                <span className={cn('text-xs font-mono', (volatility?.vix_change ?? 0) < 0 ? 'text-emerald-400' : 'text-red-400')}>
                  {(volatility?.vix_change ?? 0) < 0 ? '' : '+'}{(volatility?.vix_change ?? 0).toFixed(2)}
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[#0d0d14] rounded-lg p-3 border border-[#1a1a2e]">
                <span className="text-[9px] text-gray-500 uppercase">30D Hist Vol</span>
                <p className="text-sm font-mono text-white mt-0.5">{(volatility?.hist_vol_30d ?? 0).toFixed(1)}</p>
              </div>
              <div className="bg-[#0d0d14] rounded-lg p-3 border border-[#1a1a2e]">
                <span className="text-[9px] text-gray-500 uppercase">Vol Percentile</span>
                <p className="text-sm font-mono text-white mt-0.5">{volatility?.vol_percentile ?? 0}th</p>
              </div>
            </div>
            <div className="bg-[#0d0d14] rounded-lg p-3 border border-[#1a1a2e]">
              <span className="text-[9px] text-gray-500 uppercase">IV Rank</span>
              <div className="flex items-center gap-2 mt-0.5">
                <div className="flex-1 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: `${volatility?.iv_rank ?? 0}%` }} />
                </div>
                <span className="text-xs font-mono text-gray-300">{volatility?.iv_rank ?? 0}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* News Feed */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-1.5"><Newspaper size={14} className="text-blue-400" /> News Feed</h3>
            <MockIndicator isMock={newsMock} />
          </div>
          <div className="space-y-2 max-h-[350px] overflow-y-auto scrollbar-none">
            {(news ?? []).map((n: any, i: number) => (
              <div key={i} className="flex items-start gap-3 py-2.5 border-b border-[#1a1a2e] last:border-0">
                <div className="mt-0.5">
                  {n?.sentiment === 'BULLISH' ? <TrendingUp size={14} className="text-emerald-400" /> :
                   n?.sentiment === 'BEARISH' ? <TrendingDown size={14} className="text-red-400" /> :
                   <Minus size={14} className="text-gray-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-200 font-medium">{n?.headline}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <DataBadge variant={n?.sentiment ?? 'NEUTRAL'} />
                    <span className="text-[9px] font-mono text-gray-500">{n?.source}</span>
                    <span className="text-[9px] font-mono text-gray-600">{(n?.timestamp ?? '').slice(11, 16)}</span>
                    <div className="flex gap-1">
                      {(n?.assets ?? []).map((a: string) => (
                        <span key={a} className="text-[9px] font-mono text-blue-400/70 bg-blue-500/10 px-1 rounded">{a}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-[9px] text-gray-500 uppercase">Relevance</span>
                  <p className="text-xs font-mono text-blue-400">{((n?.relevance ?? 0) * 100).toFixed(0)}%</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Economic Calendar */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-1.5"><CalendarDays size={14} className="text-purple-400" /> Economic Calendar</h3>
          <MockIndicator isMock={calMock} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-[#1a1a2e]">
                <th className="text-left py-2 font-medium">Date/Time</th>
                <th className="text-left py-2 font-medium">Event</th>
                <th className="text-left py-2 font-medium">Impact</th>
                <th className="text-right py-2 font-medium">Expected</th>
                <th className="text-right py-2 font-medium">Previous</th>
                <th className="text-right py-2 font-medium">Actual</th>
              </tr>
            </thead>
            <tbody>
              {(calendar ?? []).map((c: any, i: number) => (
                <tr key={i} className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 transition-colors">
                  <td className="py-2 font-mono text-gray-400">{(c?.date ?? '').slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-2 text-gray-200 font-medium">{c?.event}</td>
                  <td className="py-2"><DataBadge variant={c?.impact ?? 'LOW'} /></td>
                  <td className="py-2 text-right font-mono text-gray-300">{c?.expected ?? '—'}</td>
                  <td className="py-2 text-right font-mono text-gray-400">{c?.previous ?? '—'}</td>
                  <td className="py-2 text-right font-mono text-white font-medium">{c?.actual ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
