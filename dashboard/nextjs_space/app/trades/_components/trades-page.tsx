'use client';

import { useCallback, useState, useMemo } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { cn } from '@/lib/utils';
import { Download, ArrowUpDown } from 'lucide-react';
import dynamic from 'next/dynamic';

const EquityCurveChart = dynamic(() => import('./equity-curve-chart'), { ssr: false, loading: () => <div className="h-[250px] bg-[#12121a] animate-pulse rounded-lg" /> });
const MonthlyReturnsChart = dynamic(() => import('./monthly-returns-chart'), { ssr: false, loading: () => <div className="h-[250px] bg-[#12121a] animate-pulse rounded-lg" /> });

export function TradesPage() {
  const tradesFetcher = useCallback(() => api.getTrades(), []);
  const equityFetcher = useCallback(() => api.getEquityCurve(), []);
  const monthlyFetcher = useCallback(() => api.getMonthlyReturns(), []);

  const { data: trades, isMock } = useApiPolling(tradesFetcher, 10000);
  const { data: equity } = useApiPolling(equityFetcher, 30000);
  const { data: monthly } = useApiPolling(monthlyFetcher, 30000);

  const [sortField, setSortField] = useState('date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filterStrategy, setFilterStrategy] = useState('ALL');
  const [filterDirection, setFilterDirection] = useState('ALL');

  const strategies = useMemo(() => {
    const s = new Set((trades ?? []).map((t: any) => t?.strategy).filter(Boolean));
    return ['ALL', ...Array.from(s)] as string[];
  }, [trades]);

  const filteredTrades = useMemo(() => {
    let result = [...(trades ?? [])];
    if (filterStrategy !== 'ALL') result = result.filter((t: any) => t?.strategy === filterStrategy);
    if (filterDirection !== 'ALL') result = result.filter((t: any) => t?.direction === filterDirection);
    result.sort((a: any, b: any) => {
      const aVal = a?.[sortField] ?? '';
      const bVal = b?.[sortField] ?? '';
      if (typeof aVal === 'number' && typeof bVal === 'number') return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
      return sortDir === 'asc' ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
    });
    return result;
  }, [trades, filterStrategy, filterDirection, sortField, sortDir]);

  const handleSort = (field: string) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const exportCsv = () => {
    const headers = ['Date', 'Symbol', 'Strategy', 'Direction', 'Entry', 'Exit', 'P&L', 'P&L%', 'MAE', 'MFE', 'Regime', 'Slippage'];
    const rows = (filteredTrades ?? []).map((t: any) => [t?.date, t?.symbol, t?.strategy, t?.direction, t?.entry, t?.exit, t?.pnl, t?.pnl_pct, t?.mae, t?.mfe, t?.regime, t?.slippage].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'trades.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalPnl = (filteredTrades ?? []).reduce((sum: number, t: any) => sum + (t?.pnl ?? 0), 0);
  const wins = (filteredTrades ?? []).filter((t: any) => (t?.pnl ?? 0) > 0).length;
  const winRate = filteredTrades.length > 0 ? ((wins / filteredTrades.length) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-display font-bold text-white tracking-tight">Trade History</h2>
          <MockIndicator isMock={isMock} />
        </div>
        <button onClick={exportCsv} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 text-xs font-medium hover:bg-blue-600/30 transition-colors">
          <Download size={13} /> Export CSV
        </button>
      </div>

      {/* Performance Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Equity Curve</h3>
          <div className="h-[250px]">
            <EquityCurveChart data={equity ?? []} />
          </div>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Monthly Returns</h3>
          <div className="h-[250px]">
            <MonthlyReturnsChart data={monthly ?? []} />
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-3">
          <span className="text-[10px] text-gray-500 uppercase">Total Trades</span>
          <p className="text-lg font-display font-bold text-white">{filteredTrades.length}</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-3">
          <span className="text-[10px] text-gray-500 uppercase">Total P&L</span>
          <p className={cn('text-lg font-display font-bold', totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>${totalPnl.toFixed(2)}</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-3">
          <span className="text-[10px] text-gray-500 uppercase">Win Rate</span>
          <p className="text-lg font-display font-bold text-blue-400">{winRate}%</p>
        </div>
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-3">
          <span className="text-[10px] text-gray-500 uppercase">Winners</span>
          <p className="text-lg font-display font-bold text-white">{wins} / {filteredTrades.length}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={filterStrategy} onChange={(e) => setFilterStrategy(e.target.value)} className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500/50">
          {strategies.map((s: string) => <option key={s} value={s}>{s === 'ALL' ? 'All Strategies' : s}</option>)}
        </select>
        <select value={filterDirection} onChange={(e) => setFilterDirection(e.target.value)} className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500/50">
          <option value="ALL">All Directions</option>
          <option value="LONG">LONG</option>
          <option value="SHORT">SHORT</option>
        </select>
      </div>

      {/* Trades Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-[#1a1a2e]">
              {[
                { key: 'date', label: 'Date' },
                { key: 'symbol', label: 'Symbol' },
                { key: 'strategy', label: 'Strategy' },
                { key: 'direction', label: 'Dir' },
                { key: 'entry', label: 'Entry' },
                { key: 'exit', label: 'Exit' },
                { key: 'pnl', label: 'P&L' },
                { key: 'pnl_pct', label: '%' },
                { key: 'mae', label: 'MAE' },
                { key: 'mfe', label: 'MFE' },
                { key: 'regime', label: 'Regime' },
                { key: 'slippage', label: 'Slip' },
              ].map((col) => (
                <th key={col.key} className="text-left py-2 font-medium cursor-pointer hover:text-gray-300 select-none" onClick={() => handleSort(col.key)}>
                  <span className="flex items-center gap-0.5">{col.label} {sortField === col.key && <ArrowUpDown size={10} />}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredTrades.map((t: any, i: number) => (
              <tr key={i} className="border-b border-[#1a1a2e]/50 hover:bg-[#1a1a2e]/30 transition-colors">
                <td className="py-2 font-mono text-gray-400">{t?.date}</td>
                <td className="py-2 font-mono font-medium text-white">{t?.symbol}</td>
                <td className="py-2 text-gray-400">{t?.strategy}</td>
                <td className="py-2"><DataBadge variant={t?.direction ?? 'LONG'} /></td>
                <td className="py-2 font-mono text-gray-300">${(t?.entry ?? 0).toFixed(2)}</td>
                <td className="py-2 font-mono text-gray-300">${(t?.exit ?? 0).toFixed(2)}</td>
                <td className={cn('py-2 font-mono font-medium', (t?.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>${(t?.pnl ?? 0).toFixed(2)}</td>
                <td className={cn('py-2 font-mono', (t?.pnl_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>{(t?.pnl_pct ?? 0) >= 0 ? '+' : ''}{(t?.pnl_pct ?? 0).toFixed(2)}%</td>
                <td className="py-2 font-mono text-red-400/60">{(t?.mae ?? 0).toFixed(2)}%</td>
                <td className="py-2 font-mono text-emerald-400/60">{(t?.mfe ?? 0).toFixed(2)}%</td>
                <td className="py-2 text-gray-400 text-[10px]">{t?.regime}</td>
                <td className="py-2 font-mono text-gray-500">{(t?.slippage ?? 0).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
