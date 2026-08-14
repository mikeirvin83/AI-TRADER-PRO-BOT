'use client';

import { useCallback, useState } from 'react';
import { useApiPolling } from '@/hooks/use-api-polling';
import { api } from '@/lib/api-client';
import { DataBadge } from '@/components/dashboard/data-badge';
import { MockIndicator } from '@/components/dashboard/mock-indicator';
import { KillSwitchModal } from '@/components/dashboard/kill-switch-modal';
import { cn } from '@/lib/utils';
import { Settings, AlertTriangle, Wifi, WifiOff, Shield, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

const MODE_ORDER = ['PAPER', 'SHADOW', 'LIVE', 'EMERGENCY_STOP'];
const MODE_COLORS: Record<string, string> = {
  PAPER: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  SHADOW: 'border-purple-500/30 bg-purple-500/10 text-purple-400',
  LIVE: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  EMERGENCY_STOP: 'border-red-500/30 bg-red-500/10 text-red-400',
};

export function SystemPage() {
  const statusFetcher = useCallback(() => api.getSystemStatus(), []);
  const modeFetcher = useCallback(() => api.getModeTransitions(), []);
  const logsFetcher = useCallback(() => api.getSystemLogs(), []);
  const configFetcher = useCallback(() => api.getConfig(), []);

  const { data: status, isMock: statusMock } = useApiPolling(statusFetcher, 5000);
  const { data: modeData, isMock: modeMock } = useApiPolling(modeFetcher, 5000);
  const { data: logs, isMock: logsMock } = useApiPolling(logsFetcher, 5000);
  const { data: config, isMock: configMock } = useApiPolling(configFetcher, 30000);

  const [killOpen, setKillOpen] = useState(false);
  const [transitioning, setTransitioning] = useState(false);

  const currentMode = modeData?.current ?? 'PAPER';
  const validTransitions = modeData?.valid_transitions ?? [];

  const handleTransition = async (targetMode: string) => {
    if (!confirm(`Transition from ${currentMode} to ${targetMode}?`)) return;
    setTransitioning(true);
    try {
      await api.transitionMode(targetMode);
      toast.success(`Transitioning to ${targetMode}`);
    } catch {
      toast.error('Mode transition failed');
    } finally {
      setTransitioning(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-display font-bold text-white tracking-tight">System Control</h2>
        <MockIndicator isMock={statusMock} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Mode Control */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-1.5"><Settings size={14} className="text-blue-400" /> Mode Control</h3>
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            {MODE_ORDER.map((mode) => (
              <div key={mode} className={cn('px-3 py-1.5 rounded-lg text-xs font-mono font-bold border', mode === currentMode ? MODE_COLORS[mode] : 'border-[#1e1e2e] bg-[#0d0d14] text-gray-600')}>
                {mode}
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {validTransitions.map((target: string) => (
              <button
                key={target}
                onClick={() => handleTransition(target)}
                disabled={transitioning}
                className={cn(
                  'w-full flex items-center justify-between px-4 py-2.5 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50',
                  target === 'EMERGENCY_STOP'
                    ? 'border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20'
                    : 'border-[#2a2a3e] bg-[#1a1a2e] text-gray-300 hover:bg-[#222238]'
                )}
              >
                <span>Transition to {target}</span>
                <ArrowRight size={13} />
              </button>
            ))}
          </div>
          {/* Transition History */}
          <div className="mt-4 pt-3 border-t border-[#1a1a2e]">
            <span className="text-[10px] text-gray-500 uppercase mb-2 block">Recent Transitions</span>
            {(modeData?.history ?? []).map((h: any, i: number) => (
              <div key={i} className="flex items-center gap-2 py-1.5 text-xs">
                <span className="font-mono text-gray-500">{(h?.timestamp ?? '').slice(0, 10)}</span>
                <DataBadge variant={h?.from ?? 'PAPER'} />
                <ArrowRight size={10} className="text-gray-600" />
                <DataBadge variant={h?.to ?? 'PAPER'} />
                <span className="text-gray-500 text-[10px] truncate">{h?.reason}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Kill Switch + Connection */}
        <div className="space-y-4">
          {/* Kill Switch */}
          <div className="bg-[#12121a] border border-red-500/20 rounded-lg p-4">
            <h3 className="text-sm font-medium text-red-400 mb-3 flex items-center gap-1.5"><AlertTriangle size={14} /> Emergency Stop</h3>
            <p className="text-xs text-gray-400 mb-3">Immediately halt all trading activity and cancel open orders.</p>
            <button
              onClick={() => setKillOpen(true)}
              className="w-full py-3 rounded-lg bg-red-600 text-white text-sm font-bold hover:bg-red-700 transition-colors glow-red"
            >
              ACTIVATE KILL SWITCH
            </button>
          </div>

          {/* Alpaca Connection */}
          <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3">Alpaca Connection</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">API Status</span>
                <div className="flex items-center gap-1.5">
                  {status?.api_connected ? <Wifi size={13} className="text-emerald-400" /> : <WifiOff size={13} className="text-red-400" />}
                  <span className={cn('text-xs font-mono', status?.api_connected ? 'text-emerald-400' : 'text-red-400')}>
                    {status?.api_connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Last Heartbeat</span>
                <span className="text-xs font-mono text-gray-400">{(status?.last_heartbeat ?? '').slice(11, 19)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">System Health</span>
                <DataBadge variant={status?.system_health === 'HEALTHY' ? 'NORMAL' : 'WARNING'} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Uptime</span>
                <span className="text-xs font-mono text-gray-400">{(status?.uptime_hours ?? 0).toFixed(1)}h</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-1.5"><Shield size={14} className="text-blue-400" /> Configuration (Read-Only)</h3>
          <MockIndicator isMock={configMock} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {[
            { label: 'Risk Per Trade', value: `${config?.risk_per_trade ?? 0}%` },
            { label: 'Daily Loss Limit', value: `${config?.daily_loss_limit ?? 0}%` },
            { label: 'Weekly Loss Limit', value: `${config?.weekly_loss_limit ?? 0}%` },
            { label: 'Max Drawdown', value: `${config?.max_drawdown ?? 0}%` },
            { label: 'Max Positions', value: String(config?.max_positions ?? 0) },
            { label: 'Max Corr. Exposure', value: `${config?.max_correlated_exposure ?? 0}%` },
            { label: 'Min Signal Score', value: `${((config?.min_signal_score ?? 0) * 100).toFixed(0)}%` },
            { label: 'Signal Expiry', value: `${config?.signal_expiry_minutes ?? 0}min` },
            { label: 'Cooldown', value: `${config?.cooldown_minutes ?? 0}min` },
          ].map((item) => (
            <div key={item.label} className="bg-[#0d0d14] rounded-lg p-3 border border-[#1a1a2e]">
              <span className="text-[9px] text-gray-500 uppercase">{item.label}</span>
              <p className="text-sm font-mono font-medium text-white mt-0.5">{item.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* System Logs */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-300">System Logs</h3>
          <MockIndicator isMock={logsMock} />
        </div>
        <div className="space-y-1 max-h-[400px] overflow-y-auto scrollbar-none font-mono text-[11px]">
          {(logs ?? []).map((l: any, i: number) => (
            <div key={i} className="flex items-start gap-2 py-1 border-b border-[#1a1a2e]/30">
              <span className="text-gray-600 shrink-0">{(l?.timestamp ?? '').slice(11, 19)}</span>
              <DataBadge variant={l?.level ?? 'INFO'} className="shrink-0" />
              <span className="text-gray-500 shrink-0 w-28 truncate">[{l?.source}]</span>
              <span className="text-gray-300">{l?.message}</span>
            </div>
          ))}
        </div>
      </div>

      <KillSwitchModal open={killOpen} onClose={() => setKillOpen(false)} />
    </div>
  );
}
