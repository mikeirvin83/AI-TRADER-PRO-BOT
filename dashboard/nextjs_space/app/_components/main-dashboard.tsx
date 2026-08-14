'use client';

import { useCallback } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { MetricCard } from '@/components/dashboard/metric-card';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { DollarSign, TrendingUp, TrendingDown, Wallet, BarChart3, Target, Shield, Gauge } from 'lucide-react';
import { cn } from '@/lib/utils';

function formatCurrency(n: number | null | undefined): string {
  return `$${(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function formatPct(n: number | null | undefined): string {
  const v = n ?? 0;
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}
function formatPrice(n: number | null | undefined): string {
  const v = n ?? 0;
  return v >= 1000 ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : `$${v.toFixed(2)}`;
}

export function MainDashboard() {
  const accountFetcher = useCallback(() => api.getAccount(), []);
  const marketFetcher = useCallback(() => api.getMarketOverview(), []);
  const regimeFetcher = useCallback(() => api.getRegime(), []);
  const positionsFetcher = useCallback(() => api.getPositions(), []);
  const signalsFetcher = useCallback(() => api.getSignals(), []);
  const riskFetcher = useCallback(() => api.getRisk(), []);

  const { data: account, isMock: accountMock } = useApiPolling(accountFetcher, 5000);
  const { data: markets, isMock: marketMock } = useApiPolling(marketFetcher, 5000);
  const { data: regime, isMock: regimeMock } = useApiPolling(regimeFetcher, 10000);
  const { data: positions, isMock: posMock } = useApiPolling(positionsFetcher, 5000);
  const { data: signals, isMock: sigMock } = useApiPolling(signalsFetcher, 5000);
  const { data: risk, isMock: riskMock } = useApiPolling(riskFetcher, 5000);

  const dailyTrend = (account?.daily_pnl ?? 0) >= 0 ? 'up' : 'down';
  const weeklyTrend = (account?.weekly_pnl ?? 0) >= 0 ? 'up' : 'down';
  const monthlyTrend = (account?.monthly_pnl ?? 0) >= 0 ? 'up' : 'down';

  return (
    <div className="space-y-4">
      {/* Account Metrics */}
      <div className="flex items-center gap-2 mb-1">
        <h2 className="text-sm font-medium text-gray-400">Account Overview</h2>
        <MockIndicator isMock={accountMock} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <MetricCard label="Portfolio Value" value={formatCurrency(account?.portfolio_value)} icon={DollarSign} />
        <MetricCard label="Cash" value={formatCurrency(account?.cash)} icon={Wallet} />
        <MetricCard label="Buying Power" value={formatCurrency(account?.buying_power)} icon={BarChart3} />
        <MetricCard label="Daily P&L" value={formatCurrency(account?.daily_pnl)} subValue={formatPct(account?.daily_pnl_pct)} trend={dailyTrend} icon={dailyTrend === 'up' ? TrendingUp : TrendingDown} />
        <MetricCard label="Weekly P&L" value={formatCurrency(account?.weekly_pnl)} subValue={formatPct(account?.weekly_pnl_pct)} trend={weeklyTrend} />
        <MetricCard label="Monthly P&L" value={formatCurrency(account?.monthly_pnl)} subValue={formatPct(account?.monthly_pnl_pct)} trend={monthlyTrend} />
        <MetricCard label="Max Drawdown" value={formatPct(account?.max_drawdown)} trend="down" icon={Shield} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Market Overview */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Market Overview</h3>
            <MockIndicator isMock={marketMock} />
          </div>
          <div className="space-y-2">
            {(markets ?? []).map((m: any) => (
              <div key={m?.symbol} className="flex items-center justify-between py-1.5 border-b border-[#1a1a2e] last:border-0">
                <div>
                  <span className="text-sm font-mono font-medium text-white">{m?.symbol}</span>
                  <span className="text-[10px] text-gray-500 ml-2">{m?.name}</span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-mono text-white">{formatPrice(m?.price)}</span>
                  <span className={cn('text-xs font-mono ml-2', (m?.change_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {formatPct(m?.change_pct)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Market Regime */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Market Regime</h3>
            <MockIndicator isMock={regimeMock} />
          </div>
          <div className="mb-3">
            <p className="text-lg font-display font-bold text-blue-400">{regime?.current_regime ?? 'Unknown'}</p>
            <div className="flex items-center gap-4 mt-2">
              <div>
                <span className="text-[10px] text-gray-500 uppercase">Confidence</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="w-20 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${((regime?.confidence ?? 0) * 100)}%` }} />
                  </div>
                  <span className="text-xs font-mono text-gray-300">{((regime?.confidence ?? 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div>
                <span className="text-[10px] text-gray-500 uppercase">Duration</span>
                <p className="text-xs font-mono text-gray-300 mt-0.5">{regime?.duration_days ?? 0} days</p>
              </div>
            </div>
          </div>
          <div>
            <span className="text-[10px] text-gray-500 uppercase">Key Signals</span>
            <div className="mt-1 space-y-1">
              {(regime?.key_signals ?? []).map((s: string, i: number) => (
                <div key={i} className="text-xs text-gray-400 flex items-center gap-1.5">
                  <div className="w-1 h-1 rounded-full bg-blue-500" />
                  {s}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Risk Meter */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-300">Risk Summary</h3>
            <MockIndicator isMock={riskMock} />
          </div>
          <div className="space-y-3">
            <RiskBar label="Risk/Trade" used={risk?.risk_per_trade?.used ?? 0} max={risk?.risk_per_trade?.max ?? 2} />
            <RiskBar label="Daily Loss" used={risk?.daily_loss?.used ?? 0} max={risk?.daily_loss?.max ?? 3} />
            <RiskBar label="Weekly Loss" used={risk?.weekly_loss?.used ?? 0} max={risk?.weekly_loss?.max ?? 6} />
            <RiskBar label="Drawdown" used={risk?.portfolio_drawdown?.current ?? 0} max={risk?.portfolio_drawdown?.max ?? 15} />
            <RiskBar label="Positions" used={risk?.simultaneous_positions?.current ?? 0} max={risk?.simultaneous_positions?.max ?? 10} suffix="" />
            <RiskBar label="Correlation" used={risk?.correlated_exposure?.current ?? 0} max={risk?.correlated_exposure?.max ?? 60} />
          </div>
          {/* Circuit Breaker */}
          <div className="mt-3 pt-3 border-t border-[#1a1a2e] flex items-center gap-2">
            <div className={cn('w-2.5 h-2.5 rounded-full', risk?.circuit_breaker?.status === 'NORMAL' ? 'bg-emerald-500' : 'bg-red-500 animate-pulse')} />
            <span className="text-xs font-mono text-gray-400">Circuit Breaker:</span>
            <DataBadge variant={risk?.circuit_breaker?.status ?? 'NORMAL'} />
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300">Active Positions</h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-mono">{(positions ?? []).length} open</span>
            <MockIndicator isMock={posMock} />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-[#1a1a2e]">
                <th className="text-left py-2 font-medium">Symbol</th>
                <th className="text-left py-2 font-medium">Dir</th>
                <th className="text-right py-2 font-medium">Size</th>
                <th className="text-right py-2 font-medium">Entry</th>
                <th className="text-right py-2 font-medium">Current</th>
                <th className="text-right py-2 font-medium">Stop</th>
                <th className="text-right py-2 font-medium">Target</th>
                <th className="text-right py-2 font-medium">P&L</th>
                <th className="text-right py-2 font-medium">%</th>
                <th className="text-left py-2 font-medium pl-3">Strategy</th>
              </tr>
            </thead>
            <tbody>
              {(positions ?? []).map((p: any, i: number) => (
                <tr key={i} className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 transition-colors">
                  <td className="py-2 font-mono font-medium text-white">{p?.symbol}</td>
                  <td className="py-2"><DataBadge variant={p?.direction ?? 'LONG'} /></td>
                  <td className="py-2 text-right font-mono text-gray-300">{p?.size}</td>
                  <td className="py-2 text-right font-mono text-gray-300">{formatPrice(p?.entry_price)}</td>
                  <td className="py-2 text-right font-mono text-white">{formatPrice(p?.current_price)}</td>
                  <td className="py-2 text-right font-mono text-red-400/70">{formatPrice(p?.stop_loss)}</td>
                  <td className="py-2 text-right font-mono text-emerald-400/70">{formatPrice(p?.target)}</td>
                  <td className={cn('py-2 text-right font-mono font-medium', (p?.unrealized_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {formatCurrency(p?.unrealized_pnl)}
                  </td>
                  <td className={cn('py-2 text-right font-mono', (p?.pnl_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {formatPct(p?.pnl_pct)}
                  </td>
                  <td className="py-2 pl-3 text-gray-400">{p?.strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Signals */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300">Recent Signals</h3>
          <MockIndicator isMock={sigMock} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-[#1a1a2e]">
                <th className="text-left py-2 font-medium">Time</th>
                <th className="text-left py-2 font-medium">Symbol</th>
                <th className="text-left py-2 font-medium">Strategy</th>
                <th className="text-left py-2 font-medium">Dir</th>
                <th className="text-right py-2 font-medium">Score</th>
                <th className="text-left py-2 font-medium pl-3">Status</th>
                <th className="text-left py-2 font-medium pl-3">Reason</th>
              </tr>
            </thead>
            <tbody>
              {(signals ?? []).map((s: any, i: number) => (
                <tr key={i} className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 transition-colors">
                  <td className="py-2 font-mono text-gray-400">{(s?.timestamp ?? '').slice(11, 16)}</td>
                  <td className="py-2 font-mono font-medium text-white">{s?.symbol}</td>
                  <td className="py-2 text-gray-400">{s?.strategy}</td>
                  <td className="py-2"><DataBadge variant={s?.direction ?? 'LONG'} /></td>
                  <td className="py-2 text-right font-mono text-blue-400">{((s?.score ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-2 pl-3"><DataBadge variant={s?.status ?? 'EXECUTED'} /></td>
                  <td className="py-2 pl-3 text-gray-500 max-w-[200px] truncate">{s?.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function RiskBar({ label, used, max, suffix = '%' }: { label: string; used: number; max: number; suffix?: string }) {
  const pct = max > 0 ? Math.min((used / max) * 100, 100) : 0;
  const color = pct > 80 ? 'bg-red-500' : pct > 50 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[10px] text-gray-500 uppercase">{label}</span>
        <span className="text-[10px] font-mono text-gray-400">{used.toFixed(suffix ? 1 : 0)}{suffix} / {max}{suffix}</span>
      </div>
      <div className="w-full h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all duration-500', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
