'use client';

import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import { Activity, AlertTriangle, Wifi, WifiOff, Clock } from 'lucide-react';
import { useCallback, useState } from 'react';
import { KillSwitchModal } from './kill-switch-modal';

const MODE_COLORS: Record<string, string> = {
  PAPER: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  SHADOW: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  LIVE: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  EMERGENCY_STOP: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const MARKET_COLORS: Record<string, string> = {
  Open: 'text-emerald-400',
  Closed: 'text-gray-500',
  Pre: 'text-amber-400',
  After: 'text-amber-400',
};

export function StatusBar() {
  const fetcher = useCallback(() => api.getSystemStatus(), []);
  const { data } = useApiPolling(fetcher, 5000);
  const [killOpen, setKillOpen] = useState(false);

  const status = data;
  const mode = status?.trading_mode ?? 'PAPER';
  const market = status?.market_status ?? 'Closed';
  const health = status?.system_health ?? 'UNKNOWN';
  const connected = status?.api_connected ?? false;

  return (
    <>
      <div className="h-11 bg-[#0d0d14]/90 backdrop-blur-sm border-b border-[#1a1a2e] flex items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-4">
          {/* Trading Mode */}
          <span className={cn('px-2.5 py-0.5 rounded text-xs font-mono font-bold border', MODE_COLORS[mode] ?? MODE_COLORS['PAPER'])}>
            {mode}
          </span>

          {/* Market Status */}
          <div className="flex items-center gap-1.5">
            <Clock size={13} className={MARKET_COLORS[market] ?? 'text-gray-500'} />
            <span className={cn('text-xs font-mono', MARKET_COLORS[market] ?? 'text-gray-500')}>
              Market {market}
            </span>
          </div>

          {/* Health */}
          <div className="flex items-center gap-1.5">
            <Activity size={13} className={health === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'} />
            <span className={cn('text-xs font-mono', health === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400')}>
              {health}
            </span>
          </div>

          {/* API Connection */}
          <div className="flex items-center gap-1.5">
            {connected ? <Wifi size={13} className="text-emerald-400" /> : <WifiOff size={13} className="text-red-400" />}
            <span className={cn('text-xs font-mono', connected ? 'text-emerald-400' : 'text-red-400')}>
              {connected ? 'API OK' : 'DISCONNECTED'}
            </span>
          </div>
        </div>

        {/* Kill Switch */}
        <button
          onClick={() => setKillOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1 rounded bg-red-600/20 border border-red-500/30 text-red-400 text-xs font-mono font-bold hover:bg-red-600/30 transition-colors"
        >
          <AlertTriangle size={13} />
          KILL SWITCH
        </button>
      </div>
      <KillSwitchModal open={killOpen} onClose={() => setKillOpen(false)} />
    </>
  );
}
