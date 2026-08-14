'use client';

import { cn } from '@/lib/utils';

const VARIANT_STYLES: Record<string, string> = {
  LONG: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  SHORT: 'bg-red-500/15 text-red-400 border-red-500/20',
  ACTIVE: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  WATCH: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  DEGRADED: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  SUSPENDED: 'bg-red-500/15 text-red-400 border-red-500/20',
  RETIRED: 'bg-gray-500/15 text-gray-400 border-gray-500/20',
  EXECUTED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  REJECTED: 'bg-red-500/15 text-red-400 border-red-500/20',
  EXPIRED: 'bg-gray-500/15 text-gray-400 border-gray-500/20',
  PASSED: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  FAILED: 'bg-red-500/15 text-red-400 border-red-500/20',
  OVERFITTING: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  TESTING: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  BULLISH: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  BEARISH: 'bg-red-500/15 text-red-400 border-red-500/20',
  NEUTRAL: 'bg-gray-500/15 text-gray-400 border-gray-500/20',
  NORMAL: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  TRIGGERED: 'bg-red-500/15 text-red-400 border-red-500/20',
  HIGH: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  EXTREME: 'bg-red-500/15 text-red-400 border-red-500/20',
  MEDIUM: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  LOW: 'bg-gray-500/15 text-gray-400 border-gray-500/20',
  INFO: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  WARNING: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/20',
  ERROR: 'bg-red-500/15 text-red-400 border-red-500/20',
};

export function DataBadge({ variant, className }: { variant: string; className?: string }) {
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold border uppercase',
      VARIANT_STYLES[variant] ?? 'bg-gray-500/15 text-gray-400 border-gray-500/20',
      className
    )}>
      {variant}
    </span>
  );
}
