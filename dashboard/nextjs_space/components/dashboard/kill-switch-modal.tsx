'use client';

import { AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';
import { useState } from 'react';

export function KillSwitchModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [confirming, setConfirming] = useState(false);

  if (!open) return null;

  const handleKill = async () => {
    setConfirming(true);
    try {
      await api.killSwitch();
      toast.error('EMERGENCY STOP activated');
    } catch {
      toast.error('Failed to activate kill switch');
    } finally {
      setConfirming(false);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-[#12121a] border border-red-500/30 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-full bg-red-600/20 flex items-center justify-center">
            <AlertTriangle size={24} className="text-red-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-red-400">Emergency Stop</h2>
            <p className="text-xs text-gray-400">This will immediately halt ALL trading activity</p>
          </div>
        </div>
        <div className="bg-red-900/20 border border-red-500/20 rounded-lg p-3 mb-5">
          <ul className="text-xs text-red-300/80 space-y-1">
            <li>• All open orders will be cancelled</li>
            <li>• No new signals will be processed</li>
            <li>• System will enter EMERGENCY_STOP mode</li>
            <li>• Manual intervention required to resume</li>
          </ul>
        </div>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg bg-[#1a1a2e] text-gray-300 text-sm font-medium hover:bg-[#222238] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleKill}
            disabled={confirming}
            className="flex-1 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-bold hover:bg-red-700 transition-colors disabled:opacity-50 glow-red"
          >
            {confirming ? 'STOPPING...' : 'CONFIRM KILL'}
          </button>
        </div>
      </div>
    </div>
  );
}
