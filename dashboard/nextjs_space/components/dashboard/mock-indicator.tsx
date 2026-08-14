'use client';

import { Database } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export function MockIndicator({ isMock }: { isMock: boolean }) {
  if (!isMock) return null;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400/70 text-[9px] font-mono border border-amber-500/20">
            <Database size={9} />
            MOCK
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="bg-[#1a1a2e] text-gray-300 border-[#2a2a3e] text-xs">
          Using simulated data — backend unavailable
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
