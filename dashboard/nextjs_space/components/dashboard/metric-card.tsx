'use client';

import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}

export function MetricCard({ label, value, subValue, icon: Icon, trend, className }: MetricCardProps) {
  return (
    <div className={cn(
      'bg-[#12121a] border border-[#1e1e2e] rounded-lg p-4 transition-all hover:border-[#2a2a3e]',
      className
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={15} className="text-gray-600" />}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-xl font-display font-bold text-white tracking-tight">{value}</span>
        {subValue && (
          <span className={cn(
            'text-xs font-mono font-medium mb-0.5',
            trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400'
          )}>
            {subValue}
          </span>
        )}
      </div>
    </div>
  );
}
